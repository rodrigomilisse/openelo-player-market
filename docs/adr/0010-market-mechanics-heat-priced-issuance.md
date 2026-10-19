# ADR-0010: Market mechanics: heat-priced issuance and peer-to-peer trading

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided, leaning (the current preference, not final), proposed (not
  decided) or open. Amends ADR-0009 decision 3 (the pool keeps k × cost),
  decision 6 (k stays) and its "Order pricing" section, and resolves
  ADR-0009 open points 5 and 6. Changes how the curve in Spec §3 works
  (decision 1).
- **Date**: 2026-10-20

## Context

ADR-0009 settled where the curve's money lives: supply is the balance of one
pool account per player, and the formula lives in `pricing`. It left open how
the market behaves: how orders are priced, how users trade with each other,
how the curve and that trading relate, and who pays what.

The design was worked out against these goals:

- Reward users who spot a player early.
- Never lock out users who spot a player later. They pay more (a higher price,
  a scarcer share) but always have a way to buy.
- Shares are minted while a player is new, traded between users for most of a
  career, and redeemed at the end.
- No number that settles money is chosen by the operator (Spec §3). The
  market's behaviour follows from its mechanics, not from rules that switch
  parts of it on and off.

A plain curve fails these goals. If minting costs the curve price and
redeeming pays the curve price, every peer-to-peer (P2P) trade has to happen in
the narrow band between the two. Rising demand is met by minting instead of by
holders selling higher, and holders cannot profit from a rise unless the curve
moves. The P2P price is pinned to the curve the way an ETF's exchange price is
pinned to its holdings by creation and redemption.

## Decision

### Decided

1. **Issuance is priced with heat.** Each newly minted share costs

   ```
   mint price = curve(supply) × (1 + heat)
   ```

   - `curve(i)` is ADR-0009's base curve: the price of the share that takes
     supply from i to i + 1, with a starting point calibrated once per player.
   - Every minted share adds `step ÷ (supply + s₀)` to that player's heat,
     where supply is the supply when the share is minted.
   - Heat halves every `τ`, continuously.
   - `step`, `s₀` (a virtual supply) and `τ` are public constants, the same
     for every player.

   Heat measures recent demand for new shares: buying adds it and time removes
   it. Minting never closes; it only becomes more or less expensive. The curve
   stays permanently two-sided, as Spec §3 requires. What changes in Spec §3 is
   that the mint price also depends on recent minting, and redeem no longer
   pays a fixed fraction of the mint price.

2. **Heat is derived, not stored.** It is a function of the player's mint
   history (quantities, the supply at each mint, timestamps) and the current
   time, computed in `pricing`. There is no state table, trigger or scheduled
   job (ADR-0006 decision 2).

3. **Only minting moves heat.** Redeems and P2P trades do not change it, and
   nothing makes it cool faster than `τ`.

4. **An order pays heat share by share.** Each share in an order pays the heat
   left by the share before it, so a large order costs the same as buying the
   same shares one at a time at the same moment. Splitting an order at the
   same moment must change neither its cost nor the heat it adds. This
   replaces the "lump total" of ADR-0009, which only summed the base curve.

5. **Redeem pays the base curve, with no fee and no heat.** Redeeming n shares
   at supply s pays curve(s − n) + … + curve(s − 1). The pool keeps exactly the
   base curve price of every share it issues, so it always holds what
   redeeming every outstanding share pays (ADR-0009). Heat never enters the
   pool.

6. **The premium and the mint fee go to the fee account.** A mint of n shares
   is one ledger transaction:

   ```
   user → pool   credits   sum of base curve prices    backs redemption
   user → fees   credits   sum of base curve × heat    issuance premium
   user → fees   credits   mint fee                    announced in advance
   pool → user   share     n
   ```

   The premium is Spec §3's "profit from primary issuance". The mint fee is
   charged on mint only. It may change over time, announced in advance, and a
   holder's exit never depends on it. This replaces ADR-0009 decision 3 (the
   pool keeps k × cost) and decision 6 (k stays fixed): there is no k, which
   also settles ADR-0009 open points 5 and 6.

7. **One dividend pool for the whole market.** All fees and premiums fund one
   pool per period, split between players by Elo only. A player's payout never
   depends on trading or minting in that player, which keeps Spec §3's rule
   that no payout is pegged to the market's own activity.

8. **The platform's cut starts at 0%.** Everything in the fee account funds
   dividends. A later cut is a business decision, announced in advance.

9. **The platform never trades on the book.** It places no orders and holds no
   inventory. Its only liquidity is the curve, quoted by the public formula,
   and the curve's quotes are shown as depth so that thin markets still show
   real, executable prices. The book is anonymous: nobody sees who owns an
   order or who they traded with.

10. **Retirement changes nothing in `market-service`.** The curve and heat keep
    working. Dividends fade through rating-service's Elo decay for retired
    players (Spec §2). There is no buyback and no final settlement price, and
    `market-service` has no concept of retirement.

11. **No forced sales.** Holders keep their shares however long they are
    inactive. Minting is always available at some price, so an inactive holder
    cannot block a buyer.

12. **Trading does not pause during matches.** Users trade against each other
    or against the formula, never against an operator quoting on the news. The
    curve cannot be picked off, because its price depends on supply and
    minting, not on news.

### Leaning, not decided

- **24/7 continuous trading.** Stock markets close for reasons that do not
  apply here: human floor traders, overnight settlement batches, and official
  closing prices that funds and derivatives settle on.
- **A continuous limit order book for P2P trading**, matched by best price,
  then earliest arrival, as on NYSE or LSE. Alternatives: periodic auctions,
  direct offers.
- **Separate venues.** The book knows nothing about the curve. How an order
  reaches the better venue is open (open point 2).
- **Escrow postings for open orders.** Placing an order posts the credits or
  shares from the user to an escrow account, fills pay out of escrow, and a
  cancel posts the rest back. The ledger shows every hold, and ADR-0008's
  balance check applies unchanged.
- **A taker-only P2P fee**, lower than the cost of minting. Only the order
  that executes against a resting order pays. Resting orders, which thin books
  need, are free.

### Proposed, not decided

- **Order types.** Limit orders with a time-in-force: good-till-cancelled,
  immediate-or-cancel or fill-or-kill. A market order is an
  immediate-or-cancel limit order with an automatic price collar, so it cannot
  sweep a thin book and the amount to escrow is known. The client declares
  side, quantity and limit price; the server computes every amount from the
  formula and the book (Spec §3). This settles ADR-0009 open point 7.
- **Iceberg and hidden orders** later, for holders who want to hide size.
- **Choosing the constants from a target**, for example "a star trading at
  twice its base curve grows its supply by at most N% a year", solved for
  `step` and `τ` and checked by simulation in `research/`.
- ADR-0009's proposed `player_shares` table stands unchanged.

## How it behaves

**A burst of demand.** If a player's market price jumps to (1 + h) × the base
curve, buyers mint until heat reaches h. From then on, minting is no longer
cheaper than buying from holders. A jump therefore creates about
h × (supply + s₀) ÷ step new shares, and the rest of the rise happens in P2P
prices, which holders capture.

**Lasting popularity.** Heat cools, so the mint price dips below the market
and a little minting refills it. In steady state the mint price follows the
market price, and supply grows by about h × ln 2 ÷ (step × τ) of
(supply + s₀) per unit of time. New shares are then sold at about the market
price, never as a bargain, like a company's at-the-market offering.

**Quiet players.** Heat cools to 0 and minting returns to the base curve. At
supply 0 the curve is back at its starting price, so a forgotten player can
always be revived.

**Early and late spotters.** The first buyers pay the base curve with no heat,
the cheapest shares there will be. Later buyers pay more: either the heated
mint price, or a P2P price set by early holders.

**Small supplies.** `s₀` keeps the first shares from producing extreme heat.
With s₀ = 100 and step = 50, the first share adds 0.5 heat, so the next buyer
pays 1.5 × the curve: a premium, not a lockout. pump.fun's virtual reserves and
Uniswap v3's virtual liquidity use virtual amounts for the same reason.

**Two dials.** `step` sets how much supply a burst creates. `τ` sets how much
supply lasting popularity creates and how long a hype premium lasts. When
step × τ is near 0 the market behaves like a plain curve; when it is very large
it behaves as if minting were closed.

**Cases checked.**

| Case | Outcome |
|---|---|
| Mint, then redeem | Pays curve × (1 + heat) + fee, gets the curve back: always a loss, at least the mint fee. |
| Pushing heat up to price others out | Only possible by minting at rising prices, with the premium going to the dividend pool. That is buying, not manipulation. |
| Sniping on news during a match | A few shares near the old price, until the sniper's own minting heats the price. The platform loses nothing. |
| Mass redemption | Covered by the pool (decision 5). |
| A player who breaks out years after listing | A short burst of minting, bounded by `step`, then the rise happens in P2P prices. |
| Retirement | Holders redeem down the curve; earlier redeemers get more than later ones. |

Comparable mechanisms: Ethereum's EIP-1559 base fee (a price that rises when
usage is above target and falls when below), Paradigm's VRGDA (new tokens sold
on a target schedule), and at-the-market share offerings.

## Consequences

+ The goals follow from one formula. There are no open or close rules,
  triggers, reference prices or forced sales.
+ Minting is never cheaper than the market by more than one share's heat, and
  the gap closes itself.
+ Solvency is untouched. The pool holds the base curve only; heat and fees
  never enter it, so rounding never touches the reserve.
+ Moving the mint price means paying it. Nothing else changes heat.
+ `market-service` needs no concept of retirement, dormancy or market phases.
+ Dividends are funded by all trading and issuance and split by Elo only.
  − Every quote needs the player's mint history: a query per quote until it is
  cached (ADR-0006 decision 4).
  − Popular players see slow, continuous issuance at about the market price.
  Holders' scarcity is protected only as strongly as `step` and `τ` make it.
  − The constants must be chosen by analysis and simulation before launch.
  Wrong values make the market behave like a plain curve, or as if minting
  were closed.
  − The premium and percentage fees produce fractions of a minor unit and need
  a rounding rule (open point 4).
  − At listing, heat is 0, so the fastest buyers get the cheapest shares.
  − After retirement, earlier redeemers get more than later ones.
  − The order book, escrow and order lifecycle are the largest piece of work
  left in `market-service`.

## Alternatives considered

- **A plain curve with a narrow band** (redeem at the curve, mint fee only):
  P2P is pinned to the curve, and rising demand is minted instead of traded.
- **A fixed k as band width** (redeem at k × curve): widens the band by making
  the curve expensive for everyone, and keeps a fixed ceiling. It tunes a
  parameter instead of changing the mechanism.
- **A discovery phase, then minting closes**: locks out later spotters, and
  needs a closing rule that can be gamed or that misfires in quiet periods.
  Reopening at the curve price would sell below market, because curve-priced
  minting is only ever used when it is below market.
- **A minimum supply before minting closes**: keeps the cheap start of the
  curve open for latecomers.
- **A mint price that rises with time**: sells below market in a breakout, so
  it is a reopening rule under another name.
- **A mint price floored at the best bid**, with depth weighting, minimum
  resting time or caps: one large bid can block minting, and each protection
  patches the previous one.
- **Forced sale of inactive holders' shares** (a liveness check and an
  announced sale): unnecessary once minting is always available, and a legal
  and trust risk.
- **Platform orders to add liquidity or hide sellers**: breaks Spec §3's
  no-discretion rule, gives the platform an information advantage, and orders
  that give a false impression of supply or demand are market manipulation
  under EU MAR art. 12.
- **One dividend pool per player, or the premium kept in that player's pool**:
  ties a player's payout or redemption value to its own trading, the loop the
  Spec forbids.
- **Pausing trading during matches** (like Betfair's in-play delay): protects
  an operator quoting odds, and there is none here.
- **For the leanings**: periodic auctions or direct offers instead of a book;
  the curve inside the matching engine instead of separate venues; a computed
  available balance or ledger two-phase holds instead of escrow; no P2P fee, a
  fee on both sides, or maker-taker rebates.

## Open points

1. **Constants**: the base curve's shape, `step`, `s₀`, `τ`, the mint fee and
   the P2P fee.
2. **Routing**: a server-side router that splits each order between the book
   and the curve, a picker in the app, or neither.
3. **Escrow layout**: one shared escrow account, or one per user.
4. **Rounding**: the premium and percentage fees produce fractions; the
   direction of rounding is not set. The reserve is unaffected.
5. **Computing heat within an order**: an exact per-share sum or a continuous
   integral. Either must be unaffected by splitting an order at the same
   moment, and must not loop over every share.
6. **Dividends within a player**: whether a player's slice of the pool is
   divided by its supply, or each share earns by Elo alone. This decides who
   bears the dilution from new issuance.
7. **The mint fee's base**: a percentage of the base curve price, or of the
   price including heat.
8. **Listing rush**: bot prevention at listing. Not an architectural question.
9. **Declaring credits instead of shares** (ADR-0009 open point 8).
10. **Carried over from ADR-0009**: lot size (open point 2), finding and
    creating platform accounts (open point 3), and listing players with their
    start price (open point 4).
