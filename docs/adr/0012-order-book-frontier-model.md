# ADR-0012: Reading the order book through per-level frontiers

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided or proposed. Builds on ADR-0011 decisions 11–13: the book stays
  derived, and this ADR decides how it is read and what orders are sorted by.
- **Date**: 2026-10-31

## Context

ADR-0011 derives what is left of each order from its trades (decision 12),
through the `open_orders` view. Reading the book means computing that view for
every order that crosses an incoming limit, including every order that was
filled or cancelled long ago. The cost of placing an order therefore grows with
the share's whole trading history.

The usual fixes store what is open: a table of open orders that rows are
deleted from, or an in-memory book. ADR-0006 allows a stored copy of a derived
value only as a cache justified by a measured problem (decision 4).

Matching itself offers a better shape. Orders are filled by price, then by
arrival (ADR-0011 decision 1), so within one price level they are filled
strictly in queue order.

## Decision

### Decided

1. **The book is read through one frontier per price level.** A level is a
   share, a side and a limit price. Because a level fills strictly in queue
   order:
   - its **frontier** is the most recently touched resting order: the latest
     in the queue that has been a maker in a trade;
   - every resting order before the frontier is closed, filled or cancelled;
   - every resting order after the frontier is untouched, so it is open unless
     it was cancelled;
   - the frontier itself is open while it has shares left. A frontier filled in
     several parts stays the frontier until it is fully filled; the next fill
     at that level makes the next order the frontier.

   Whether an order is filled is then a comparison against one order per
   level, which an index can answer. Orders closed by fills are never read.
   Nothing derived is stored and every row stays immutable.

2. **The book is indexed over the orders that rested**, not over all orders.
   The frontier rule holds only for orders that entered the book. A taker that
   fills completely on arrival is closed from its first moment, has no maker
   trade, and is never passed by a frontier. Indexed with the rest, every such
   taker at a level that never rests an order would be read again by every
   crossing order, forever. An order rests at most once, with one escrow hold
   (ADR-0011 decision 11), so the holds are the book's entries.

3. **An order's place in its queue is an arrival sequence**: a number taken
   from a Postgres sequence when the order is inserted. ADR-0011's per-share
   lock (decision 13) serialises inserts for a share, so the sequence strictly
   increases in arrival order within each share's book.
   - The frontier rule requires that a newer order never sorts before an older
     one at its level; otherwise an open order would count as closed. This is
     a correctness requirement, not only a fairness one.
   - The order id is not used: UUIDv7's time order is a property of the id
     generator, not of the order.
   - `created_at` is not used: equal timestamps (the manual dev clock gives
     every order the same one) or a clock stepping back can sort a newer order
     first.

4. **Orders keep `created_at`**, the time the order was posted. It is not a
   copy of a ledger time: no order references a ledger transaction, and the
   ledger records money movements, while an order's posting time is a trading
   fact. An order that moves no money (a future immediate-or-cancel order that
   matches nothing) is still posted at a time.

5. **Cancellations stay as they are.** A cancelled order after its level's
   frontier is skipped with one lookup in the cancellations table's unique
   index. The next fill at that level lands on a newer order and passes it for
   good. Only cancelled orders at the end of a level that never fills again
   keep being looked up, by orders whose limit spans that level.

### Proposed

6. **Escrow holds carry the order's level and queue position**: `share_id`,
   `side`, `limit_price` and the order's arrival sequence, copied from the
   order and tied to it by a composite foreign key
   `(order_id, share_id, side, limit_price, arrival_seq) → limit_orders`, so the
   copy cannot drift. Index: `escrow_holds (share_id, side, limit_price,
   arrival_seq)`. This is the technique ADR-0006 open point 2 proposes for
   market transaction subtypes, but it stores these four values twice, against
   ADR-0006 decision 1; see open point 1.
7. **Matching walks levels in price order.** For each crossing level: find the
   frontier, then read open orders after it in queue order until the incoming
   order is filled. A level with nothing open costs one frontier lookup.
8. **What is left of a visited order** stays as ADR-0011 derives it, its
   quantity minus the shares its trades moved. The sum now runs only over the
   few trades of the orders actually visited.

## Consequences

+ Placing an order costs in proportion to the open orders it reaches and the
  price levels it crosses, not to the share's history.
+ Nothing derived is stored; no table has deletes or updates; no cache to keep
  consistent.
+ The database stays the complete record, so an in-memory book can still be
  added later without changing it.
  − Correctness depends on levels filling strictly in queue order. Any future
  feature that fills out of order breaks the frontier rule: pro-rata matching,
  priority kept across an order change, or iceberg refills that keep their
  place. Such features must enter the queue as new orders, or this ADR is
  revisited.
  − Correctness also depends on the per-share lock: without it, arrival
  sequence order and the order in which orders rest can differ.
  − Matching runs more, smaller queries per order (per level) instead of one.
  − Cancelled orders at the end of a level that stops filling are looked up
  again by every order crossing it (decision 5).

## Alternatives considered

- **A table of open orders, deleted from on fill and cancel**: the standard
  shape, allowed as an ADR-0006 cache, but stores derived state the frontier
  rule makes unnecessary.
- **An in-memory book per share**, the design exchanges use: fastest, but
  needs one owner per share's book, a rebuild at startup, and partitioning
  (for example Kafka by share) once there is more than one instance. Remains
  the next step if the database cannot keep up.
- **Sorting by order id** or **by `created_at` with any tie-break**: see
  decision 3.
- **Indexing every order instead of the holds**: see decision 2.
- **Cancelling by a platform fill followed by a reversing trade**: makes the
  cancelled order the frontier, which wrongly closes every older open order
  when the cancel is not at the front of the queue. It is also a platform
  trade on the book, which Spec §3 and ADR-0010 rule out, it shows up as
  volume and a last price, and it posts two ledger transactions per cancel.

## Open points

1. **The copies on escrow holds** (decision 6) against ADR-0006 decision 1:
   accept key-enforced copies as the way an index reaches another table's
   columns, or find a shape that needs none.
2. **Finding the frontier**: walking a level's resting orders from the newest
   until one has a maker trade (cost: the level's open orders), or giving
   trades the maker's level and queue position by the same composite foreign
   key, so the frontier is one index lookup.
3. **Walking the levels**: a loop in the application with one query per level,
   or a single recursive query.
