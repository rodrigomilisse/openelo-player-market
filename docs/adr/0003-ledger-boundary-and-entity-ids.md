# ADR-0003: Ledger boundary, entity persistence and typed ids

- **Status**: Accepted (open points listed at the end)
- **Date**: 2026-10-07

## Context

The first market-service implementation modelled accounts and transactions as
JPA inheritance hierarchies (`UserAccount`/`PlatformAccount`, `Mint`/`Redeem`
as subtypes of `Transaction`). That coupled the ledger to users and to trading
rules, produced a package cycle (`market` ↔ `ledger`), and made ids easy to mix
up (account, asset, user and transaction ids were all bare `UUID`s).

ADR-0001 keeps the whole money core in one service and one database, and calls
for an append-only, double-entry ledger. ADR-0002 governs references between
entities. This ADR sets the structure that satisfies both.

## Decision

### 1. Modules and dependency direction

```
common/    BaseEntity, auditing and clock configuration
ledger/    generic double-entry core; depends on nothing in this service
user/      identity only; knows nothing about money
trading/   market logic, wallets, Mint, Redeem; depends on ledger and user
```

Dependencies point one way: `trading → ledger`, `trading → user`, and
everything may use `common`. `ledger` and `user` never import each other.

### 2. The ledger is generic

- Entities: `Account`, `Transaction` (postings stored as an `@ElementCollection`
  of an embeddable `Posting`).
- `Ledger.post(ITransaction)` accepts a description of postings
  (`ITransaction` exposes postings only), copies them into its own
  `Transaction`, saves it and returns its id. Callers never hand over entities.
- Invariants enforced by the ledger: the transaction is non-empty and postings
  sum to zero per asset. Postings are individual signed entries, not pairs, and
  zero amounts are allowed.
- `Mint` and `Redeem` are **not** ledger transactions. They are `trading`
  entities that implement `ITransaction` to supply their postings and store the
  id of the ledger transaction they produced. The ledger never learns what a
  mint is.
- Within one database transaction, `trading` posts first, then saves its own
  row that references the ledger transaction (FK order).

### 3. Accounts and ownership

- An account is an identity plus ledger-level policy (for example whether it
  may go negative). Enforcing that policy belongs in the ledger, because a
  check done by callers races under concurrency; choosing the policy per
  account belongs to the caller that creates it.
- Who owns an account is a `trading` concern: a `wallets` table
  (`user_id` nullable, `account_id`, `purpose`). The platform account is a
  wallet with no user, created at startup through `ledger.openAccount()`.
  There are no fixed or configured account UUIDs.

### 4. Entities and persistence

- `BaseEntity` is a `@MappedSuperclass` with a Hibernate-generated UUID v7 id.
  Ids are only given out after persistence, so there is no `Persistable` and
  no assigned-id handling.
- `createdAt` is filled by Spring Data auditing (`@CreatedDate`) from a `Clock`
  bean, so time is injectable in tests. Auditing is enabled in its own
  `@Configuration`, not on the application class.
- Fields are private with no setters. `updatable = false` is deliberately not
  used, because it would silently skip the `UPDATE` instead of failing.
- Ledger tables are append-only. This will be enforced in the database
  (revoked `UPDATE`/`DELETE` or a trigger), so a violation fails loudly;
  corrections are posted as reversing transactions. Postings carry no
  timestamp of their own: the transaction's time is the record time.

### 5. Typed ids

- Entity ids and other id columns are stored as raw `UUID`. JPA does not allow
  converters on `@Id`, and keeping every id column raw keeps repositories
  uniform: every repository method takes a `UUID`.
- Ids are typed at the API edge only: constructors, getters and service
  signatures use a typed `Id`, so a method taking an account id, an asset id and
  a user id cannot be called with them swapped. Callers unwrap with `.value()`
  when they query a repository.
- Where a concept has no entity (assets) or several implementations (users),
  the tag is a small public type or the interface itself.
- No `AttributeConverter` is needed for ids.

## Consequences

+ The ledger can be understood, tested and later extracted without users or
  trading rules; new transaction types need no ledger change.
+ Ledger invariants live in one place instead of in every caller.
+ No package cycles; the one-way rule can be checked mechanically.
+ Id mix-ups become compile errors at module boundaries.
+ ADR-0002 still holds: `wallets` and `Mint`/`Redeem` reference ledger rows by
  id, not by navigable relations.
  − `trading` needs a mapping lookup (`wallets`) to find a user's account.
  − Typed ids add wrapping and unwrapping at the edges.
  − Ledger entities can no longer be saved polymorphically; callers go through
    `Ledger`.

## Alternatives considered

- **Keep `Mint`/`Redeem` as ledger transaction subtypes**: simplest persistence,
  but the ledger must know every business transaction type or accept abstract
  entities from callers.
- **Owner column on accounts (`users.account_id` or `UserAccount`)**: makes
  `user` or `ledger` depend on the other and assumes one account per user.
- **`@EmbeddedId` / embedded id records, or converters on id columns**: legal for
  non-id columns, but require per-field column overrides, do not combine with
  generated ids, and add mapping risk.
- **`Persistable` with ids assigned in the constructor**: only needed for
  application-assigned ids, which the design no longer needs.
- **Raw `UUID`s everywhere**: the most common choice, but gives no protection
  against passing the wrong id.

## Open points

1. **Id representation**: one generic `Id<T>` (less boilerplate, tag is
   erased at runtime) versus one record per id type implementing a shared
   interface (distinct at runtime, room for per-type behaviour).
2. **`BaseEntity<T>` versus a non-generic `BaseEntity`** with a typed getter
   written only on entities whose ids leave their module. The raw accessor must
   not be named `getId()`, to avoid clashing with interface getters.
3. **Account tag**: public opaque `Account` (`Id<Account>`) versus a separate
   marker type. The simpler `Id<Account>` is preferred.
4. **Schema migration**: reset the local database and rewrite V1–V4 as one
   clean V1, or add V5. Either must create `wallets`, add `allowed_negative` to
   `accounts`, drop `user_accounts` and `platform_account`, and reshape `mints`
   and `redeems`.
5. **Append-only enforcement** (role permissions versus triggers) and the
   ledger-side balance check are planned, not yet built.
