# ADR-0007: Postings move value from one account to another

- **Status**: Accepted, not yet implemented. Amends ADR-0003 §2 (signed
  postings, and the check that a transaction is non-empty).
- **Date**: 2026-10-17

## Context

ADR-0001 calls for a double-entry ledger, and ADR-0003 stores each ledger
transaction as any number of signed postings `(account, asset, amount)` that
must sum to zero per asset. The reason for that shape was flexibility: a
transaction is not fixed to two legs, so a trade can also pay a fee, feed a
dividend pool, and so on.

Under ADR-0006 that shape has a problem. Because the postings of a transaction
must sum to zero per asset, one amount per asset is always derivable from the
others, whatever the number of legs. The balance holds because the stored legs
happen to agree, not because of the table's structure, and the ledger has to
check it in code. The `postings` table also has no primary key.

Double-entry is a principle (every movement leaves one account and enters
another), not a storage format. It can equally be stored as one row per
movement with a source and a destination account. That is the shape of
TigerBeetle's transfers and of Formance's postings.

## Decision

1. **A posting is one movement**: `from_account_id`, `to_account_id`,
   `asset_id`, `amount`. The amount is non-negative (`amount >= 0`; zero is
   allowed, as in ADR-0003); direction comes from the two account columns.
2. **A ledger transaction is a group of any number of postings**, including
   zero, possibly in several assets. Arbitrary legs remain possible. A trade
   with a fee:

   ```
   buyer  → seller    credits  495
   buyer  → platform  credits    5
   seller → buyer     SHARE_X    5
   ```

3. **Zero-sum holds by construction.** Each posting's single amount leaves one
   account and enters another, so no per-asset sum check is needed.
   A transaction with no postings, like a posting with a zero amount, is
   meaningless but harmless, so ADR-0003's non-empty check is dropped. The
   ledger still enforces account policy such as `allowed_negative`
   (ADR-0003).
4. **Names stay**: the row is a *posting*, the group is a *transaction*
   (`postings`, `ledger_transactions`). "Transfer" is not used, so a
   transaction is not "several transfers".
5. **`from = to` is allowed.** Such a posting nets to zero and breaks nothing,
   so no constraint is added.
6. **A balance is derived** (ADR-0006): the sum of postings into the account
   minus the sum of postings out of it, per asset. Indexing stays deferred
   (V7).

Proposed, not decided:

- **Postings get their own `id`** and become a JPA entity instead of an
  `@ElementCollection` embeddable. That gives the table a primary key and lets
  JPQL query postings directly, without joining through the transaction.
  Alternative: a composite key `(transaction_id, line_number)`.
- **Indexes, once needed**: `(to_account_id, asset_id)` and
  `(from_account_id, asset_id)`, each `INCLUDE (amount)` so the balance query
  can be answered by index-only scans.

## Consequences

+ No stored amount is derivable from others; the zero-sum rule leaves code
  and becomes part of the table's shape (ADR-0006 decision 3).
+ The ledger records who paid whom, which signed postings did not.
+ Transactions keep any number of legs.
  − The balance query reads two sides (incoming and outgoing), and needs two
  indexes instead of one once indexing is added. Complexity is unchanged:
  O(log N + k) indexed, where k is the number of postings touching the account.
  − When several accounts pay several others in the same asset, a pairing has
  to be chosen, and it can be arbitrary. None of the current flows (trades,
  fees, mints, redeems) need this.
  − Migration of `postings`, and changes to `Posting`, `IPosting`,
  `Ledger.post` and the balance query.

## Alternatives considered

- **Keep signed postings (ADR-0003)**: one index and a single scan per account
  statement, and no pairing to choose; but one redundant amount per asset per
  transaction, and zero-sum checked in code.
- **One row per trade with buyer and seller**: puts trading concepts into the
  ledger, which ADR-0003 rules out.
- **Call the row a transfer**: TigerBeetle's term, but then a transaction would
  be several transfers; "posting" keeps the existing names.
