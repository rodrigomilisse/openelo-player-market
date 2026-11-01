# ADR-0015: Account rollover bounds balance reads

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided or proposed. Amends ADR-0014 decisions 11 and 12, and ADR-0009's
  rule that a share's id is its pool's account id.
- **Date**: 2026-11-01

## Context

A balance is the sum of an account's postings in one asset (ADR-0007), so
reading it costs as much as the account's history. Two write paths read
balances from Postgres:

- **User accounts**: the balance check before a user spends (ADR-0008), not
  built yet.
- **Pools**: supply and heat, read on every mint (ADR-0009, ADR-0010).

Postings have no index on their account columns today (V7 dropped it), so
each of these reads scans every posting in the system. With indexes, it
scans the account's own postings, which still grows without bound for an
active trader or a popular share.

A running balance stored on each entry would make the read constant, but it
stores derived values, and was rejected as not normalised. Updating a
balance column in place either loses the old value or copies it elsewhere.

## Decision

### Decided

1. **Busy accounts roll over.** A new account is opened, and one transaction
   carries every balance of the old account forward. The old account ends at
   zero and receives nothing again. The carry-forward is a recorded fact; no
   derived value is stored.
2. **No column is updated.** Which account is active is recorded as new rows.
   The active account is the owner's newest row by `created_at`, the source of
   truth for time (ADR-0013). `UNIQUE (owner, created_at)` makes the newest row
   unique.
3. **The trigger is the posting count.** The query that sums a balance also
   counts the postings it summed. Past a threshold, the account rolls over.
4. **Each rollover is its own market transaction**, like a deposit or a mint,
   with `UNIQUE (from_account_id)`. An account is carried forward out of at
   most once. A second, concurrent rollover of the same account fails and
   rolls back whole, so it cannot carry the same balances into two accounts.
5. **Pools roll over too, triggered on mints.** When a pool rolls over (by
   count, by period, or both) is set after the heat calculation is reworked;
   its 30-day cliff is to be replaced.
6. **Escrow and pool balances are assertions, not checks.** Neither is read
   in the write path:
   - A trade or cancellation releases from escrow an amount fixed by the
     order, which its hold put in (ADR-0011).
   - A redeem pays the curve back from a reserve that holds the full
     redemption value of the supply (ADR-0009).

   Both should always hold. A failure is an application bug, not a request to
   reject.
7. **Escrow accounts do not roll over for now.** Following decision 6, nothing
   reads their balances in the write path, so a count trigger would never
   fire.
8. **The Redis wallet cache stays, and the projector updates it on
   rollover.** This amends ADR-0014 decision 11, which assumed a user's
   account ids never change.

### Proposed

9. **The wallet splits into two tables, replacing `wallets`**:
   `wallet_accounts (user_id, account_id, created_at)` and
   `wallet_escrow_accounts (user_id, escrow_account_id, created_at)`, each with
   `UNIQUE (user_id, created_at)` and a unique account id. Main and escrow
   accounts change at different times, so one row would copy the unchanged
   one. Sign-up inserts the first row of each; a migration copies today's
   wallets with their `created_at`. The unique index also finds the newest row
   per user in one descent, so no other index is needed.
10. **`share_pools (share_id, account_id, created_at)`**, with
    `UNIQUE (share_id, created_at)` and a unique account id. A share keeps the
    id of its first pool, so existing shares keep their ids. Finding the
    active pool becomes one lookup instead of none.
11. **`account_rollovers (id, from_account_id)`**: `id` references
    `market_transactions`; `from_account_id` references `accounts` and is
    unique. The new account is not stored here: it is the newest wallet or
    pool row, written in the same transaction.
12. **A per-user lock**: the balance check, any rollover and the posting run
    under a transaction-scoped advisory lock on the user id, the same pattern
    as the book lock in `P2pVenue`. Pools already run under the per-player
    lock (ADR-0009). The lock serialises check-then-post; decision 4 is the
    backstop if a path forgets it.
13. **Roll over before posting.** The check reads the balance and the count;
    at or past the threshold it rolls over first, then posts to the new
    account. Placeholder threshold: 10,000 postings.
14. **Carry-forward direction**: a positive balance posts from the old
    account to the new one; a negative one (a pool's issued shares) posts from
    the new to the old. Heat counts only pool outflows that do not go to the
    share's previous pool, so a carry-forward is not counted as minted. To be
    reviewed with the heat rework.
15. **The cache update is applied with the carry-forward, in one step.** The
    ledger defines an interface the projector calls for each transaction to
    get extra Redis writes; trading implements it. For a rollover it returns
    `wallet:{userId}` or `pool:{shareId}` pointing to the new account. The
    projector applies the postings and those writes in the same Lua script, so
    no read sees the balances moved while the cache still points to the old,
    now empty, account. The ledger still depends on nothing (trading
    implements the ledger's interface, not the reverse). Reads that fill the
    cache from Postgres use `SET NX` and the projector overwrites, so a fill
    that read Postgres before a rollover cannot replace the newer value.
16. **`GET curve/shares/{shareId}/supply` reads the active pool** through
    `pool:{shareId}`, amending ADR-0014 decision 12, which needed no lookup.

## Consequences

+ A balance check reads one index entry and at most a threshold's worth of
  postings, however long the account has been in use.
+ A mint's supply and heat reads are bounded by one pool period.
+ Nothing derived is stored and no column is updated. Full history stays in
  the ledger, spread over the owner's accounts.
+ A double rollover fails in the schema, not only in code.
  − Depends on indexes on the postings' account columns, which are deferred.
  Without them every read still scans all postings, however small the
  account.
  − Every posting path must resolve the account through the newest row at
  posting time. Nothing in the schema stops a posting to a rolled-over
  account if code keeps an old id.
  − An account statement spans several accounts.
  − A share's id is no longer its pool's id, and heat must exclude the
  carry-forward.
  − `from_account_id` restates the owner's previous row, which can be derived
  from the ordering; it is stored because the unique constraint needs a
  column.

## Alternatives considered

- **A running balance on each entry, pinned by constraints**: a constant-time
  read, and concurrent spends rejected by the primary key, but every entry
  stores a derived value. Rejected as not normalised.
- **A balance column updated in place**: loses history or copies it.
- **A `deactivated_accounts` table as the source of truth**: finding the
  active account checks every account the user ever had, and it restates "the
  user has a newer account".
- **A per-user generation number** to order accounts: a second column ordering
  the same thing as `created_at` (ADR-0013).
- **Rollover by period for users**: a heavy trader can still pile up postings
  within one period.

## Open points

1. **The threshold value.**
2. **The pool rollover rule**, after the heat rework (decision 5).
3. **How assertions are verified** (decision 6): as asserts in the write
   path, by a periodic reconciliation (ADR-0009, later `audit-service`), or
   both.
4. **The platform account** receives every fee from every share. It is never
   checked, so it never rolls over under decision 3; its history only grows.
