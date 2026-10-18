# ADR-0008: Overdraft policy moves from the ledger to trading

- **Status**: Accepted, not yet implemented. Resolves ADR-0006 open point 3.
  Supersedes the parts of ADR-0003 §3 and ADR-0007 §3 that say the ledger
  enforces `allowed_negative`, and the non-negative-balance exception in
  ADR-0006 decision 3.
- **Date**: 2026-10-19

## Context

ADR-0003 §3 made `allowed_negative` an account-level policy that the ledger
enforces, because a check done by callers races under concurrency. ADR-0006
decision 3 then listed that rule as the one exception to the DKNF target: it
spans many postings, cannot be expressed by keys, and is enforced in code.

ADR-0006 open point 3 observed that overdraft may belong to the transaction
rather than the account: the platform may let a user owe credits when it
initiates a movement, but never when the user does. That decision depends on
who is acting and why, which is a trading concern. The ledger does not know
what a mint, a redeem or an initiator is (ADR-0003 §2).

A hybrid, where the caller passes a flag per transaction and the ledger
enforces it, was considered and rejected (see Alternatives).

## Decision

1. **The ledger has no overdraft concept.** It neither stores nor enforces a
   limit on balances. Every balance is legal to the ledger, and `post()` keeps
   its current signature: it receives postings only.
2. **`accounts.allowed_negative` is removed.** An account is an identity and
   nothing else in `ledger`. A later migration drops the column; `Account`,
   `Ledger.openAccount` and `SignUp` lose the flag.
3. **`trading` owns the rule.** Before it posts a transaction, `trading`
   checks that the postings would not take an account below zero, unless the
   transaction type or its initiator permits it. Today the user's wallet
   account must stay at or above zero and the platform account is exempt, as
   it is under ADR-0003.
4. **The check and the post happen in one database transaction**, so the
   balance read and the write cannot be separated by a concurrent post.
5. **The ledger stays purely structural.** Its remaining invariants (ADR-0007)
   follow from table shape, so ADR-0006's exception for the ledger no longer
   exists. The non-negative rule remains an exception, now listed under
   `trading`.

Proposed, not decided:

- **Concurrency control in `trading`.** `trading` takes a row lock on the
  user's `wallets` row (`SELECT ... FOR UPDATE`, or a pessimistic lock in JPA)
  before reading the balance, so two posts for the same user serialize.
  Alternatives are serializable isolation with retries, or an advisory lock
  per account. Not chosen.
- **How `trading` knows an account is a platform account.** Today `Market`
  keeps its id in memory. The planned `platform_accounts` table (ADR-0003 §3)
  would answer it.

## Consequences

+ `ledger` no longer depends on any policy, and can be tested and extracted
  without it (ADR-0003 goal).
+ ADR-0006's DKNF exception leaves the ledger; the schema has one fewer
  stored flag.
+ The rule can depend on the initiator and transaction type, which the ledger
  could not see.
  − The ledger can no longer detect an overdrawn user. A bug in `trading`
  would produce a negative balance that nothing downstream flags.
  − The concurrency guard moves to `trading` and must be built there. Until
  it exists, nothing prevents overdrafts (this is also true today, as the
  ledger check was never built).
  − Existing code and the schema change: drop `accounts.allowed_negative`,
  `Account`, `openAccount(boolean)` and the `SignUp` constant.

## Alternatives considered

- **Hybrid: per-transaction flag, enforced by the ledger.** Keeps one guard in
  the ledger, but the ledger must then receive the flag, and either store it
  (a new column on `ledger_transactions`) or act on it without recording it.
  It also keeps the DKNF exception in the ledger, which this ADR removes.
- **Keep the per-account flag (ADR-0003).** Simple and race-safe in one place,
  but it cannot express "allowed when the platform initiates".
- **Stored balance with a `CHECK (balance >= 0)`.** Makes the database enforce
  the rule, but needs a stored balance, which ADR-0006 decision 4 allows only
  as a measured cache.
