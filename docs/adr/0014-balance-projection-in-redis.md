# ADR-0014: Balance projection in Redis

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided or proposed. Adds a cache under ADR-0006 decision 4 ahead of a
  measured problem, and implements part of the outbox planned in ADR-0001
  decision 3.
- **Date**: 2026-10-31

## Context

A balance is the sum of every posting into and out of an account for one
asset (ADR-0007). `GET bank/balance/{userId}` runs that sum in Postgres on
every request, so its cost grows with the account's history. Supply is the
same sum over a pool account (ADR-0009).

Reads that only show a user their balances need no transaction with the
write path. They can be served from a stored snapshot that is updated when a
transaction is posted. That saves two costs: the trip to Postgres, and
summing the history.

ADR-0006 decision 4 allows such a copy as a cache once a measured problem
needs it. Nothing has been measured; this ADR adds it ahead of that. Its
other conditions still hold: the copy is marked as a cache, can be rebuilt
from Postgres at any time, and never replaces it.

## Decision

### Decided

1. **Redis holds a projection of every account's balances.** User-facing
   balance reads are served from it. Postgres stays the source of truth: any
   balance read inside a write (overdraft checks, the supply that prices a
   mint or redeem) keeps reading Postgres, because a check against a stale
   copy could spend money twice (ADR-0001 decision 3).
2. **The projection is fed by a transactional outbox.** `Ledger.post` inserts
   an outbox row in the same database transaction as the postings, so a
   committed transaction always has its row and a rolled-back one never does.
   A projector in `market-service` reads pending rows and applies them to
   Redis. No Kafka for now; when another service needs these events, a relay
   publishes the same outbox to Kafka and the projector becomes a consumer.
3. **Read endpoints served from the projection**: a user's credits balance
   (the existing endpoint), their share holdings, what their open orders hold
   in escrow, and a share's supply.

### Proposed

4. **The outbox row is only a reference**: `ledger_outbox (transaction_id)`,
   primary key and foreign key to `ledger_transactions`. The projector reads
   the postings themselves, so nothing is stored twice. The table belongs to
   the ledger.
5. **One Redis hash per account**: key `balances:{accountId}`, field the
   asset id, value the balance in minor units. Applying a posting is
   `HINCRBY` of minus the amount on the from account and plus the amount on
   the to account. `HINCRBY` works on signed 64-bit integers, the same range
   as the ledger's `long`, so the arithmetic stays exact.
6. **Order of application does not matter.** Adding deltas commutes, so the
   projector applies pending transactions in any order. It needs no ordering
   column, and several projector instances can share the outbox by claiming
   rows with `FOR UPDATE SKIP LOCKED`.
7. **Applying a transaction is idempotent.** One Lua script, which Redis runs
   atomically, sets a marker `projected:{transactionId}` with `SET NX` and
   applies the postings only if the marker was new. A transaction delivered
   twice changes nothing the second time. The marker expires after a day; it
   is only needed between the Redis update and the deletion of its outbox
   row.
8. **The projector deletes an outbox row after Redis confirms it.** The
   outbox is delivery state, not a recorded fact, so it is the one ledger
   table with deletes; transactions and postings stay append-only. A crash
   between the Redis update and the delete redelivers the row, which
   decision 7 absorbs.
9. **Rebuild from Postgres.** The projector and the rebuild share a Postgres
   advisory lock, so they never run at once. In one `REPEATABLE READ`
   transaction the rebuild reads every account's balances and the pending
   outbox rows. It replaces the Redis hashes and sets the markers of the
   pending rows, because the balances it read already include them. It ends
   by setting `balances:ready`.
10. **Reads fall back to Postgres** while `balances:ready` is missing or
    Redis is unreachable. Redis runs with `maxmemory-policy noeviction`, so it
    never drops a key on its own. With `balances:ready` set, a missing hash
    therefore means an account with no postings, and its balances are zero.
11. **Wallets are cached aside in Redis**: `wallet:{userId}` holds the user's
    account and escrow account ids, filled from Postgres on the first read.
    A wallet row never changes after sign-up, so the cached copy cannot go
    stale and needs no invalidation. Without this, every balance read would
    still query `wallets` to find the account.
12. **Endpoints**:
    - `GET bank/balance/{userId}`: unchanged path, credits from the user's
      account hash.
    - `GET wallets/{userId}/holdings`: every share in the user's account hash.
    - `GET wallets/{userId}/escrow`: the user's escrow account hash, credits
      and shares.
    - `GET curve/shares/{shareId}/supply`: minus the pool's balance of that
      share. The pool's account id is the share id (`ShareService`), so no
      lookup is needed.

## Consequences

+ A balance read is one or two Redis lookups, whatever the account's history,
  and does not touch Postgres.
+ The projector knows only accounts, assets and amounts. Every current and
  future kind of transaction is projected without its own code.
+ The outbox is ready for Kafka: a relay can be added without changing what
  `Ledger.post` writes.
  − Reads lag behind writes. A user who deposits and immediately reads may see
  the old balance for up to one polling interval.
  − Redis is new infrastructure to run, and the projector a new moving part.
  Its failures make reads slower (Postgres fallback), never wrong.
  − Every `Ledger.post` writes one more row.
  − The outbox is the first ledger table with deletes.
  − The projection exists before any measured problem asked for it
  (ADR-0006 decision 4).

## Alternatives considered

- **Update Redis in an after-commit hook**: no outbox and no lag, but a crash
  or a Redis outage between the commit and the update leaves a balance wrong
  until a rebuild.
- **A balance table in Postgres** (ADR-0009: "balances are cached in the
  ledger"), updated in the same transaction as the postings: never stale, and
  could serve write-path checks too. Every read still queries Postgres.
- **Cache-aside on balances**: compute from history on a miss, invalidate on
  write. A miss still sums history, and a refill racing a write can store a
  stale balance.
- **Tailing `ledger_transactions` by `created_at`** in place of an outbox:
  transactions do not commit in `created_at` order, so a cursor can pass a
  transaction that commits late and never project it.
- **Kafka now**: no second consumer needs the events yet.

## Open points

1. **Polling interval and batch size.** A nudge after each commit could
   trigger the projector at once and cut the lag.
2. **Zero balances**: whether the script removes a field that returns to zero,
   so holdings do not list shares the user no longer owns.
3. **Reconciliation**: a periodic comparison of Redis against Postgres, later
   a job for `audit-service`.
4. **When a rebuild runs**: at startup when `balances:ready` is missing, on an
   admin command, or both.
