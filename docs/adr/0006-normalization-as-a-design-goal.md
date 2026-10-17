# ADR-0006: Normalization as a design goal

- **Status**: Accepted (open points listed at the end)
- **Date**: 2026-10-17

## Context

Several earlier decisions already lean towards a strictly normalized schema
without stating the goal behind them: ADR-0003 forbids nullable columns,
postings lost their own `created_at` because it duplicated the transaction's
(V3), and ADR-0005 has the database enforce every reference it can.

Questions that keep coming back need one shared answer instead of a verdict per
case: should a trade store its price when the postings already determine it,
should balances be stored, should the ledger store amounts that its own
invariant makes derivable (see ADR-0007)?

Normal forms, briefly, as used below:

- **1NF–BCNF** remove redundancy caused by dependencies between columns of a
  row (repeating groups, partial and transitive dependencies). BCNF is the
  usual industry target.
- **4NF/5NF** remove redundancy from independent multi-valued facts and from
  facts that can be rebuilt by joining smaller ones. Modelling one fact per
  table normally satisfies them.
- **DKNF** asks that every constraint on a table follow from its column
  domains and keys alone, so any row that satisfies them is a legal row. It is
  the only normal form that also covers rules spanning several rows. Like the
  others it is defined per table; no standard normal form covers constraints
  between tables (academic work such as inclusion dependency normal form
  exists, but is not used in practice).
- **6NF** gives every attribute its own table, so attributes can change and be
  historised independently and nulls never occur.

## Decision

1. **Every fact is stored once.** Schemas reach BCNF at least, and 4NF/5NF by
   giving each table exactly one kind of fact.
2. **Derived values are not stored.** The test is whether a value can be
   recomputed deterministically from stored facts and business rules:
   - **Yes** (balances, a trade's price, which asset was the currency and which
     the product): it is derived, by a query or a view.
   - **No** (anything the stored facts do not pin down): it is a fact, stored
     once in the module that owns it (ADR-0003). Ledger-agnostic facts never go
     into ledger tables.
   The test is applied the same way to every value; how easy a value is to
   compute does not change the verdict.
3. **DKNF, applied to the whole database, is the target.** Every constraint
   follows from column domains, keys, and foreign keys that reference keys.
   Classic DKNF is judged per table, which would let a rule escape it by being
   split across tables; applying it database-wide closes that gap. When two
   shapes hold the same facts, prefer the one whose invariants follow from
   these over one that needs code to check them. Any other constraint is an
   exception, listed here and enforced in code:
   - **Non-negative balances** (temporary, see open points). An account with
     `allowed_negative = false` must keep a balance of at least zero. This rule
     spans many postings and cannot be expressed without storing balances; the
     ledger enforces it (ADR-0003, not yet built).

   The ledger reaches the target, apart from the exception above, once
   ADR-0007 is implemented. `trading` is work in progress; its known gaps are
   listed as open points.
4. **Caches are optimizations, not part of the model.** A stored copy of a
   derived value (for example a balance with an `updated_at`) may be added when
   a measured performance problem needs it. It is marked as a cache, can be
   rebuilt from the source of truth at any time, and never replaces it.
5. **No nullable columns** (unchanged from ADR-0003): an optional relationship
   gets its own table.
6. **Immutable rows are not split into a table per column.** Rows are recorded
   once, with their own `created_at` or a foreign key to a row that has one,
   and never updated. No attribute changes on its own, so 6NF's per-attribute
   tables would gain nothing; the no-nulls rule already gives its other
   benefit.
7. **Normalization applies to stored data, not to query results.** Repeated
   values in a join result are expected and are not redundancy.

Proposed, not decided:

- If an attribute ever becomes changeable (for example `username` or
  `allowed_negative`), it moves to its own timestamped table
  (`user_id, username, created_at`) instead of being updated in place. That is
  6NF applied only where an attribute changes independently.

## Consequences

+ One rule settles every "store it or derive it" question; derived values
  cannot drift from the facts they come from.
+ Business rules move from code into the schema where a structural shape
  exists (ADR-0007 is the first application).
+ Full history follows from immutability without per-column tables.
  − Reads that need derived values (balances, prices, charts) cost a query
  instead of a column lookup, until a cache is justified.
  − Some invariants can only be made structural by changing table shapes,
  which means migrations.

## Alternatives considered

- **Store derived values for read speed** (price on the trade, a balance column
  on accounts): faster reads, but every copy can drift and needs code to keep
  it consistent. Kept available only as a cache (decision 4).
- **Stop at 3NF/BCNF**: the common target, but leaves invariants spanning rows,
  such as zero-sum transactions, to application code.
- **Full 6NF**: no benefit for immutable rows, and many more tables and joins.

## Open points

1. **Exact derivability of prices** relies on integer amounts in minor units
   and on allowed trade sizes (tick and lot sizes), so that
   `credits = quantity × price` has no rounding. These are not specified yet.
2. **Known DKNF gaps in `trading`** (as of V7):
   - `market_transactions.ledger_transaction_id` is not `UNIQUE`, so two
     market transactions can reference the same ledger transaction.
   - Subtypes are not exclusive: a market transaction can have both a `mints`
     and a `redeems` row. A `kind` column with `UNIQUE (id, kind)` and a
     composite foreign key from each subtype table would enforce "at most one";
     "at least one" cannot be enforced by keys.
   - `mints.user_account_id` and `redeems.user_account_id` are derivable from
     the postings of the referenced ledger transaction (decision 2).
   - `market_transactions.created_at` may duplicate the ledger transaction's
     time, by the same reasoning that removed `created_at` from postings (V3).
3. **Overdraft may belong to the transaction, not the account.** A user might
   be allowed to owe credits when the platform initiates a movement, but never
   on their own initiative. That would replace the per-account
   `allowed_negative` flag with a decision the caller makes per transaction.
   The ledger would then neither store nor enforce it: every balance would be
   legal to the ledger, and the rule, with its exception, would move to
   `trading`. Not decided; the per-account exception stands until then.
