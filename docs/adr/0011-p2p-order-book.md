# ADR-0011: P2P order book: matching, escrow and the taker fee

- **Status**: Accepted in part, implemented. Each item is marked decided or
  proposed (built this way, not yet confirmed). Moves three of ADR-0010's
  leanings to decided (a continuous limit order book, escrow postings for open
  orders, a taker-only P2P fee) and resolves ADR-0010 open point 3 (escrow
  layout). Settles the P2P part of ADR-0010 open point 4 (rounding) and of
  ADR-0006 open point 1 (tick sizes).
- **Date**: 2026-10-26

## Context

ADR-0010 leaned towards a continuous limit order book for trading between
users, open orders backed by escrow postings, and a fee paid only by the taker.
It left open where escrowed funds sit, and how percentage fees avoid fractions
of a minor unit.

ADR-0006 forbids storing values that can be derived, and names a trade's price
as one of them. ADR-0008 makes `trading` responsible for keeping balances from
going negative; that check is not built yet, for the curve or for the book.

`trading` is split into sub-packages by venue: `curve` (mint and redeem,
`CurveVenue`, `/curve`) and `p2p` (the order book, `P2pVenue`, `/p2p`), plus
`banking` (deposits and withdrawals), with wallets, sign-up and the platform
constants shared at its root.

## Decision

### Decided

1. **Orders match on arrival.** An incoming order that crosses resting orders
   trades with them at once, best price first, then earliest. Every trade
   happens at the resting order's price: a buy limited at 110 against a
   resting sell at 100 pays 100. Whatever is left rests on the book. There is
   no batching or auction.
2. **Only the taker pays a fee.** The incoming order is the taker, the resting
   order the maker. The maker always gets exactly their limit price; the book
   shows prices without the fee. Resting orders, which thin books need, cost
   nothing.
3. **The P2P fee is 5% of the trade value**, a placeholder like every constant
   in ADR-0010 open point 1, and below the mint fee as ADR-0010 requires.

       trade value = maker's limit price × shares traded
       fee         = trade value × fee rate ÷ fee scale

4. **Fees are exact, never rounded.** Limit prices must be multiples of a tick
   chosen so that the fee on any trade is a whole number of minor units.
5. **One escrow account per trader.** A user's escrow balance in the ledger is
   what their open orders have locked, per asset. A single shared escrow
   account would hide whose funds are whose; one account per order would open
   an account for every order.
6. **Order sides are a Postgres enum type** (`side`), not text or a number. It
   is validated by the database and readable in queries. Postgres has no
   one-byte enum: it takes 4 bytes, against 2 for a `SMALLINT`.

### Proposed

7. **The limit price is the price per share; the fee comes on top.** A taker
   buying at a limit of 100 may pay 100 per share plus the fee. This is how
   exchanges treat limit prices.
8. **The tick follows from the fee.** A price p gives a whole fee when
   p × fee rate is a multiple of the fee scale. The smallest such step is

       tick = fee scale ÷ gcd(fee scale, fee rate)

   With a 5% rate on a scale of 1000 the tick is 20. Changing the rate changes
   the tick.
9. **Escrow holds exactly what the rest of an order needs.** A resting buy
   locks limit price × remaining shares in credits; a resting sell locks the
   shares. As a maker it trades at its own limit and pays no fee, so the
   escrow always matches what a fill takes out. A taker pays from its wallet
   account directly.
10. **The escrow account is opened at sign-up**, next to the wallet account,
    and stored on the wallet. Exchanges give every client an available and a
    reserved balance from the start. Opening it on a user's first order instead
    would put a write inside a lookup and race when two first orders arrive
    together.
11. **An order is not a transaction.** `limit_orders` records what the user
    asked for. What happened to it is recorded as market transactions, each
    with its own ledger transaction:

    | Market transaction | Postings |
    |---|---|
    | `trades` (taker, maker) | taker buys: credits taker → maker, fee taker → platform, shares maker's escrow → taker. Taker sells: credits maker's escrow → taker (value − fee) and → platform (fee), shares taker → maker |
    | `escrow_holds` (order) | the locked amount, wallet → escrow |
    | `order_cancellations` (order) | the remaining locked amount, escrow → wallet |

    One ledger transaction per trade keeps each trade's quantity in its own
    postings, which decision 12 needs.
12. **What is left of an order is derived**, by the `open_orders` view
    (ADR-0006 decision 2):

        filled    = shares moved by the order's trades
        remaining = quantity − filled

    An order is open while something remains and it has no cancellation. A
    trade stores only its taker and maker orders: its price is the maker's
    limit price and its quantity is in its postings.
13. **One share's book is processed one order at a time.** Placing and
    cancelling take a transaction-scoped Postgres advisory lock keyed by the
    share, as an exchange runs one matching engine per instrument. Two orders
    can then neither fill the same resting order nor both rest while they
    cross. Row locks on resting orders alone would allow the second.

## Consequences

+ Every hold, trade and release is a ledger transaction; escrow balances can be
  checked against the book at any time.
+ No stored value can drift from the trades: remaining quantities and trade
  prices are derived.
+ Fees never round, so no rounding rule is needed for P2P.
+ A share's book can never be left crossed.
  − Reading the book costs an aggregate over trades and postings per order,
  until a cache is justified (ADR-0006 decision 4).
  − All orders for one share wait for each other. Shares whose lock keys
  collide also wait for each other.
  − The tick is tied to the fee rate: a new rate can leave resting orders off
  the new tick.
  − Orders are not checked against balances yet (ADR-0008), so a user can
  escrow credits or shares they do not have.

## Alternatives considered

- **Each order as one ledger transaction** holding its trades and its escrow:
  per-trade quantities could not be derived, and an order, which lives on
  after it is placed, is not a transaction.
- **A stored remaining quantity and stored trade price and quantity**: faster
  reads, but derived values (ADR-0006).
- **Row locks on resting orders**: stop double fills, but not two crossing
  orders arriving together and both resting.
- **Serializable isolation with retries**: correct, but every conflict becomes
  a failed request to retry.
- **An in-memory matching engine per share**, fed by a log such as Kafka
  partitioned by share: the standard design at exchange scale, not needed at
  this one.
- **Rounding the fee up or down** instead of a tick: needs a rounding rule, and
  rounding down lets small trades pay nothing.
- **Escrow opened on a user's first order**, or **one escrow account per
  share or per order**: see decisions 5 and 10.
- **Sides as text or as a number**: text is unvalidated without a check
  constraint; a number needs its mapping kept in two places.

## Open points

1. **Balance checks** (ADR-0008) before an order escrows or trades.
2. **Self-trade prevention**: a user's incoming order can match their own
   resting order and pays the fee for it. Exchanges cancel one side instead.
3. **Other order types** (ADR-0010 proposed: immediate-or-cancel,
   fill-or-kill, market orders with a price collar). Only resting limit orders
   are built.
4. **Routing between the curve and the book** (ADR-0010 open point 2).
5. **Changing the fee rate** when it changes the tick (decision 8).
