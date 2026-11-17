# ADR-0019: Dividends: one pool, Elo-weighted payouts, and the stake split

- **Status**: Proposed. Each item is marked decided, leaning or open. Amends
  ADR-0009 decisions 2, 3 and 6 and ADR-0010 decisions 1, 5, 6 and 7, and
  answers ADR-0010 open point 6. Changes Spec §3 (calibrated start price,
  dividend split).
- **Date**: 2026-11-17

## Context

Spec §3 pegs dividends to OpenElo and funds them from one capped pool. Three
things were open: how a player's rating turns into a share of the pool, how the
pool is funded and paid out, and how much of a purchase stays redeemable.
ADR-0010 left the split within a player open (open point 6) and calibrated each
player's starting price from Elo and age.

The aim: a share's value depends on its player's Elo, payouts can never exceed
what was paid in, and the market settles itself without the operator owing
anything.

## Decision

### Decided

1. **One starting price and one curve for every player.** No Elo and no age in
   any price. The market discovers each player's value by minting and P2P
   trading. Replaces the per-player calibrated start of Spec §3, ADR-0009 and
   ADR-0010 decision 1.

2. **Payout per share = payout × weight(player) ÷ Σ over all shares held of
   weight(their player).** A holder's dividend is his share of the total Elo
   weight held, across the whole market. Every share of a player earns the
   same; owning more shares earns proportionally more. This answers ADR-0010
   open point 6:
   - A player's slice is not divided by his own supply, so the first holder of
     a thin player gets no windfall, and unheld players need no rule.
   - Crowding is penalised through price: minting a popular player costs more
     (curve and heat), so each unit paid earns less.
   - Shares stay fungible.
   - Buying more of a player does not raise his per-share payout; it slightly
     lowers everyone's. No price-to-payout loop.

3. **Weight = 10^(rating ÷ S), S between 400 and 500.** Weights compare like Elo
   odds: at S = 400, 400 points = 10×, about 120 points = 2×; Kane (2,426)
   against a Braga regular (1,971) is about 14×. Moderately top-heavy, tuned by S.
   - Adding the same points to every rating changes nobody's payout, so pool
     drift and the absolute level of the scale do not matter.
   - A rating move changes a share's payout by the same percentage at every
     level.

4. **No promised multiples.** A share's multiple on what it paid in depends on
   what everyone else holds: Kane's multiple is his weight ÷ the average weight
   held, so it falls toward 1× if everyone holds Kane and rises above his
   weight ratio if most hold weak players. Promising fixed multiples would make
   the platform the counterparty (the Football Index failure). The app shows
   each player's current payout rate per share, computed from the pool and the
   holdings, like a tote board.

5. **Funding: everything non-redeemable goes to the pool.** Every credit paid for
   a share that is not redeemable, and every P2P fee, goes to the one dividend
   pool. The platform's cut is 0%; a later cut is taken from the pool's inflow,
   announced in advance. No outside income: payouts never depend on an
   investment of the reserve. Interest on a reserve could be added later as
   another inflow, but nothing may depend on it.

6. **Payout is a fixed fraction of the pool's balance.** Each payout is a fixed
   share of what the pool holds, so every unit paid in is eventually paid out,
   busy periods are spread over the following ones, and nobody can time a
   payout around a large mint. The rate is fast relative to careers (about 10% a
   month pays 72% in a year), so money paid in during a player's prime is
   mostly paid out during it.

### Leaning, not decided

- **Daily payout with a dividend index.** Pay the fraction daily, by that day's
  rating snapshot. This replaces payout periods, rating averaging and
  time-weighted eligibility: holding 10 days collects 10 payouts. Each day,
  dividend-service adds that day's payout per share to a running index per
  player; market-service settles a holder's dividends to the ledger only when
  his balance changes or he claims (the reward-per-token pattern of staking
  contracts). Remainders stay in the pool. Shares in escrow earn for the order
  owner.

### Open

- **The stake split.** Three options:

  | Option | Redeemable base | To the pool |
  |---|---|---|
  | A | 0% (no redemption) | 100% |
  | B | 50% | 50% |
  | C | 90% or more | heat and a small fee (ADR-0010) |

  **Returns are mathematically equivalent.** Dividends depend only on what is in
  the pool and the weight held, so a position under B or C earns what a smaller
  position under A earns; the base is money held aside. A trader can reproduce
  any split by sizing. The base is redeemed at the curve price at exit, so it
  carries supply risk; it is not risk-free cash.

  The options differ only in how users protect themselves from total loss:
  with a redeemable base, or by investing less. The split is to be set by which
  of the two works better for users once the market is running.

  What each option changes:
  - **A**: no reserve, no redeem, no per-player credit reserve; a share is a
    stream of dividends and its value falls toward zero by retirement (the age
    discount, with no age in the formula); the only exit is P2P, but the drain
    pays a holder's value out to him anyway.
  - **B, C**: a per-player credit reserve backs redemption (ADR-0009); the base
    floors P2P prices; earlier redeemers get more than later ones.
  - A large non-redeemable part with an illiquid P2P book locks holders in.

## How it behaves

- **Self-settling.** The platform owes nothing beyond the pool, and the pool can
  only pay out what it holds. If trading stopped, holders would keep receiving
  the fixed fraction of the remaining pool.
- **Payout per unit hardly depends on activity.** Volume grows the pool and the
  holdings together. Activity only moves money between traders: P2P fees go
  from traders to holders, and later minters pay more on the curve for the same
  weight.
- **Breakeven.** With equal prices, a share earns more than it paid in if its
  weight is above the average weight held. Because weights are exponential, the
  average sits above the median player: on a 77-player sample at S = 400 it was
  about 2,110 (Maxi Araújo), against a median of 1,989. Crowding into stars
  raises it.
- **Age.** A share's value is roughly its remaining payouts, so younger players
  at the same rating are worth more. Age is priced by the market, not the
  formula.
- **Rising players.** A cheap share of a player whose rating rises earns his
  higher weight on a low price. Transfers up, breakthroughs into the starting
  eleven and first call-ups create these moves.
- **Launch.** With one starting price, the highest-rated players are the best buy
  on day one. Heat limits how fast they are minted.

## Consequences

+ No liability beyond the pool; no promised payout; no number chosen by the
  operator settles money.
+ One payout rule; the rating's level and drift do not matter.
+ Age and expected development are priced by the market.
− Launch favours the fastest buyers of the best players.
− Returns for new buyers fall when many shares are held and little new money
  comes in; they recover as holders sell and shares change hands.
− A weight of 10^(rating ÷ S) is not bit-exact in floating point; the
  computation must be specified (see Notes).
− The split is unresolved, and with it whether redemption and the per-player
  credit reserve exist.

## Alternatives considered

- **A player's slice divided by his own supply** (ADR-0010 open point 6,
  first option): windfall for the first holder of a thin player, a rule
  needed for unheld players, and a payout that depends on how many others hold
  the same player.
- **Each share paid by weight with no normalisation, or fixed multiples by
  percentile**: insolvent when holders concentrate on top players.
- **Weight by percentile instead of rating**: bounded and scale-free, but a star
  climbing inside the top 1% barely moves, so calling star moves pays nothing.
- **Points above replacement (rating − 1,250)**: too flat, and a uniform shift of
  all ratings moves money between players.
- **Paying out the whole pool each period**: busy periods pay only whoever holds
  at that moment, which rewards timing.
- **Paying on money contributed rather than shares held**: shares bought at
  different prices pay differently, which breaks fungibility.
- **Elo or age in the starting price**: the operator would effectively set
  prices.

## Notes

- **Exact weights.** 2^(rating ÷ 120) is the same as S ≈ 400 ("doubles every 120
  points") and is exactly computable: an integer shift plus a published table
  for the fraction. Not adopted; noted for when the weight computation is
  specified.

## Open points

1. **The stake split** (above).
2. **S** within 400–500, and the drain rate.
3. **The P2P fee rate**: it decides how much trading, rather than new money,
   funds dividends.
4. **Retired players**: their rating slides to 1,250, where the weight is about
   1% of a 2,000 player's. Either keep paying it or stop at replacement level.
5. **Concentration check**: the share of the pool the top 1% and 10% of players
   would take at the chosen S, from current ratings.
