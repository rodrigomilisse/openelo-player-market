# ADR-0013: Order book queues ordered by `created_at`

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided or proposed. Amends ADR-0012 decision 3 (queue order) and
  decision 6 (what escrow holds copy), and resolves ADR-0012 open points 2
  and 3.
- **Date**: 2026-10-31

## Context

ADR-0012 orders each price level's queue by an arrival sequence, because the
frontier rule needs every order that sorts before a level's frontier to be
closed. A clock-based order seemed unable to promise that: equal timestamps
broken by an arbitrary rule, or a clock going backwards, could put a newer
order before the frontier.

Ties turn out to be harmless if the level is read from the frontier's
timestamp inclusively, so only a clock going backwards remains a problem.
`created_at` is already the record of when an order was posted.

Implementing ADR-0012 also settled its open points 2 and 3, and showed that
its cost claims depend on three lookups having indexes.

## Decision

### Decided

1. **A level's queue is ordered by the order's `created_at`**, the source of
   truth for when it was posted. Orders with equal `created_at` are broken by
   any deterministic rule that favours no user. There is no separate arrival
   sequence.
2. **Indexes that change a lookup's complexity are part of the design**:
   `trades (maker_order_id)`, `trades (taker_order_id)` and
   `postings (transaction_id)`. Without them every frontier lookup and every
   visited order's remaining scans a whole table, and reading the book grows
   with history again, which ADR-0012 exists to prevent. Indexes that only
   speed up a lookup that is already direct are not added for now.

### Proposed

3. **Ties are broken by order id.** It is deterministic and unrelated to the
   user; it carries no meaning beyond identity.
4. **A level is read from the frontier's timestamp, inclusively**: its open
   orders are those with `created_at` at or after the frontier's, read in
   queue order. An order stamped strictly earlier than the frontier sorted
   before it when the frontier was first filled, so it was already closed.
   Closed orders sharing the frontier's exact timestamp are read again and
   dropped; normally there are none.
5. **Escrow holds copy the order's `created_at`** as `order_created_at`, in
   place of ADR-0012's arrival sequence, under the same composite foreign key.
   The hold's own `created_at` is the time of the hold.
6. **The frontier is found by walking the level's holds from the newest** until
   one belongs to an order that has been a maker (ADR-0012 open point 2). Its
   cost is the level's open orders; trades carry no copies of the maker's
   level.
7. **Levels are walked by a loop in the application**, one query for the next
   level and one for its open orders (ADR-0012 open point 3).

## Consequences

+ One record of time: `created_at`, with no second column ordering the same
  thing.
+ Equal timestamps cost nothing in correctness.
  − Correctness depends on `created_at` never going backwards within a share's
  book. An order stamped earlier than its level's frontier counts as closed:
  it never matches, and its escrow stays locked until it is cancelled. A system
  clock stepped back (Java's system clock follows wall-clock time) can cause
  this. So can placing orders in the past in dev mode, which is intended: the
  manual clock's `--force` exists for it, with a warning while those mechanics
  are not worked out.
  − A clock that does not move (the manual dev clock) stamps every order alike,
  so each read covers the level's whole history. Advancing the manual clock by
  a microsecond per order avoids it, if needed.
  − Placing an order costs nothing for orders closed behind a level's frontier,
  but reads every open or cancelled order after the frontier at each level it
  crosses, and about two index lookups for each crossed level with nothing
  open. A level exists only at a price where an order once rested, and nothing
  records which levels are empty, so an order larger than everything open on
  the other side keeps walking dead levels up to its limit. A buy pays for the
  dead sell levels between the best ask and the highest price a sell ever
  rested at; a sell, for the dead buy levels between the best bid and the
  lowest price a buy ever rested at. Only an order that clears one whole side
  of a heavily traded share notices; a high limit on a share that never traded
  that high costs nothing extra.

## Alternatives considered

- **An arrival sequence** (ADR-0012 decision 3): correct whatever the clock
  does, at the cost of a second column that orders orders in time.
- **Reading strictly after the frontier in tie-break order**: wrong when a new
  order ties with the frontier and its tie-break sorts it first.

## Open points

1. **Orders placed in the past**: dev mode places them on purpose, and a
   production clock can step back. How the book treats an order stamped
   earlier than its level's frontier is not worked out; until then such an
   order can rest without ever matching.
