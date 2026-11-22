# Features the frontend assumes

Everything below is mocked in `mock.js` / `api.js` today. Each item is what a screen needs from the backend;
the mechanics (fees, drain, pool, issuance) are placeholders to be replaced by the real rules.

## Accounts and money
- [ ] **Accounts and sign-in.** The wallet lives in `localStorage` (`openelo-play-wallet`). Needed: user accounts, sessions, one wallet per user.
- [ ] **Wallet balance, deposits, withdrawals.** Play money starts at 1,000 credits. Needed: real or play balances, top-ups, KYC hooks if real money.
- [ ] **Reset practice account** (Activity). Keep for a play-money mode.

## Trading (Trade, Browse)
- [ ] **Order book per player** (`getBook`): bids, asks, last price, new-share price.
- [ ] **Quotes** (`getQuote(id, side, amount)`): fills from fans, then new shares on the curve; fees; average price.
- [ ] **Order execution** (`recordTrade`): atomic fill, balance and position update, fee accounting. Today it trusts the quote.
- [ ] **Limit orders / open orders.** Not built: only market orders exist.
- [ ] **Price history** per player (trade chart, sparklines, "this week", "season").
- [ ] **Holders count** per player.
- [ ] **Market list** (`getMarket`) with search and sort server-side once it's large.

## Positions (Portfolio)
- [ ] **Positions with cost basis** (`positions[id] = { shares, cost, dividends }`). Selling reduces cost pro rata (average cost). Decide FIFO vs average.
- [ ] **Dividends received per position** and in total.
- [ ] **Valuation** at last price (or mid / best bid: decide).

## Dividends (Portfolio, Dividends)
- [ ] **Dividend engine**: pool balance, drain per day, inflows (fees, new-share money), payout per share = drain × pool × w / Σ held weight, w = 10^(rating/400) (ADR-0019).
- [ ] **Pool stats** (`getPool`): balance, drain, today's payout, total held weight, next payout time.
- [ ] **Projection** (`getProjection(positions)`): next payout if ratings stay as they are, per position and total, and the reader's share of held weight.
- [ ] **Projection range**: today ±14 rating points as "one typical match". Better: from the player's next fixture and his rating volatility.
- [ ] **Payout history** per user (Dividends, Activity). `simulatePayout()` fakes one; remove it when payouts are real.
- [ ] **Payout schedule**: daily at UTC midnight assumed (countdown). Decide the real cadence.
- [ ] **Share term / expiry** (3-year term recommended in the money-model notes). Not shown anywhere yet: positions need an expiry date and the UI a "matures on" column.

## Lists and feed
- [ ] **Watchlist** persistence (`toggleWatch`).
- [ ] **Activity feed**: trades, payouts, later deposits and withdrawals.
- [ ] **Alerts**: price or rating moves on held and watched players (not built).

## Data
- [ ] **Daily rating snapshots** so payouts use the rating at payout time.
- [ ] **Fixtures** for the projection range and "plays next" hints.
- [ ] **Realtime updates** (prices, book, balance) via websocket or polling. Pages refresh on return (`pageshow-again`) only.
