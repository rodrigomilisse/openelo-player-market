# ADR-0004: Idempotency is enforced at the API layer, not in the ledger

- **Status**: Accepted (not yet implemented; applies once the ledger is exposed over an API)
- **Date**: 2026-10-08

## Context

Today `trading` calls `Ledger.post` in-process, inside the same database
transaction that saves the `Mint` or `Redeem` (ADR-0003). Either both rows commit
or neither does, so a retry cannot post the same movement twice.

That stops being true as soon as a post crosses a network boundary (a ledger
controller, another service, a message relay). A client that times out cannot
tell whether its request was applied, and a retry can post the same movement
twice. Money systems need a defined answer to "what happens if this request
arrives twice".

A common way to solve this is to let callers attach a reference or metadata to
ledger transactions and deduplicate on it. That makes the ledger store values
that only mean something to its callers, and once one field is allowed, more
tend to follow.

## Decision

1. **The ledger domain stores only what its own invariants need.** Ledger tables
   carry no client references, back-pointers or metadata, including idempotency
   keys.
2. **Idempotency is a concern of the ledger's API layer**, following the
   `Idempotency-Key` pattern used by Stripe and common across payment APIs:
   - Clients send an `Idempotency-Key` header on every request that changes
     state.
   - The API layer owns an `idempotency_keys` table: the key (unique), a hash of
     the request, the stored response and a timestamp.
   - **The key row is written in the same database transaction as the ledger
     post.** A key saved separately (or only in a cache) can be lost or recorded
     without its post, and then the protection fails.
   - Same key with the same request: return the stored response without
     calling the ledger again.
   - Same key with a different request: reject it as a client error. It is never
     treated as a replay.
   - Same key while the first request is still running: the unique constraint
     serialises them, and the second request gets a conflict response.
   - Keys expire after a retry window (for example 24 hours). They protect
     against retries; they are not a permanent record.
3. **In-process calls need no idempotency key** while the caller's write and the
   ledger post share one database transaction.

## Consequences

+ The ledger stays generic and small. Duplicate protection does not leak into
  the domain model.
+ A well-known pattern that clients and reviewers will recognise.
+ Duplicate protection lives in one place for every state-changing endpoint, not
  per transaction type.
  − The API layer and the ledger must share a database (or the key table must
  live in the ledger's database) for the single-transaction rule to hold.
  − Stored responses take space until they expire, so a cleanup job is needed.
  − Clients must generate and keep keys across retries.

## Alternatives considered

- **Idempotency or reference column on ledger transactions**: simple, but the
  ledger stores client-owned values. It opens the way to arbitrary metadata on
  ledger rows.
- **Deduplicate in a cache (e.g. Redis) in front of the service**: cannot be
  committed together with the post, so it can lose keys or keep keys for posts
  that never happened. Acceptable only as an extra layer on top of the database
  table.
- **Rely on clients not retrying**: not acceptable for money movements; network
  timeouts make retries unavoidable.
