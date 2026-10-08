# ADR-0005: Foreign keys across module boundaries

- **Status**: Accepted
- **Date**: 2026-10-08

## Context

ADR-0002 maps references across module boundaries as plain id fields in Java,
with no JPA navigation. ADR-0003 sets the module dependency direction
(`trading → ledger`, `trading → user`). Neither says whether the database may
enforce those references.

Some tables already reference another module's tables, for example:

- `market_transactions.ledger_transaction_id` → `ledger_transactions`
- `wallets.account_id`, `mints.user_account_id`, `redeems.user_account_id` → `accounts`
- `wallets.user_id` → `users`

A common modular-monolith rule is to forbid foreign keys across modules, so any
module can be moved to its own database later. Doing so here would give up
enforced integrity now in exchange for a split that ADR-0001 does not plan
(the money core stays in one service and one database).

No design removes the cross-module reference itself: a mint has to be able to
find its ledger transaction. The only question is what guarantees that the
reference is valid.

## Decision

Cross-module references are always held by id (ADR-0002). How they are checked
depends on where the data lives, and is enforced on a best-effort basis:

1. **Same database: declare the foreign key.** When the referencing and
   referenced tables share a database, the reference gets a database foreign
   key constraint, across module boundaries as well as inside a module. The
   database enforces every constraint it can.
2. **Different databases: rely on construction and check periodically.** When a
   reference crosses a database boundary, no constraint is possible. Then:
   - **Valid by construction**: an id is only ever taken from the owning
     module's API (for example the return value of `Ledger.post`), never
     invented or copied from user input without a lookup.
   - **Checked by reconciliation**: when the risk justifies it, a periodic job
     asks the owning module whether every stored id still resolves, and raises
     an alert for any that do not. This detects bad references after they
     happen; it does not prevent them.
3. **Dependency direction still applies to the schema.** A foreign key may only
   point the same way as the code dependency (for example `trading` tables may
   reference `ledger` tables, never the reverse). When ownership would otherwise
   point the wrong way, the reference lives in a link table in the module that
   is allowed to know both sides (as `wallets` does for accounts and users,
   ADR-0003).
4. **Owning modules store no back-references for their callers.** A referenced
   module does not keep pointers or metadata to make callers' lookups possible
   (see ADR-0004).

## Consequences

+ Integrity of every reference inside `market-service` is enforced by
  PostgreSQL today, including across `trading`, `ledger` and `user`.
+ Java code is already independent of the constraints: references are plain ids
  obtained from module APIs, so a split changes the schema, not the domain code.
  − Modules share a schema and migration order: `trading` migrations depend on
  `ledger` and `user` tables existing.
  − Splitting a module into its own database requires a migration that drops
  the crossing constraints, plus reconciliation where needed. Integrity then
  becomes detection, not prevention.
  − Foreign keys block deleting referenced rows (for example a user who has a
  wallet). This is intended for the append-only ledger and must be handled
  explicitly for users.

## Alternatives considered

- **No foreign keys across modules, even in a shared database**: ready to
  split, but gives up enforced integrity now for a split that is not planned.
- **Link tables for every cross-module reference**: only useful when the
  reference would otherwise point against the dependency direction, or the
  relationship is many-to-many or optional. For a required one-to-one reference
  such as a mint's ledger transaction it adds a join and still needs a foreign
  key to the other module.
- **Store a reference to the caller on the referenced row** (for example the
  mint id on the ledger transaction): reverses the direction and makes the
  referenced module store callers' data. Rejected in ADR-0004.
