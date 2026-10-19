
# OpenElo Player Market — Design Spec

## App Description

A trading platform where users buy and sell tradeable positions ("shares") in individual professional footballers. Unlike existing "player stock market" products, the number that determines value is not a reported transfer fee, an analyst's opinion, or the platform's own trading activity — it's a fully open, deterministic rating (**OpenElo**) computed purely from public match results and player minutes. Anyone can independently recompute it by hand from the same raw data. The platform has two layers:

1. **The rating engine** — an Elo-style system that rates teams from match results, then derives individual player ratings from each player's presence/minutes contribution to their team's rating swings.
2. **The market layer** — a trading mechanism built on top, where share price is set by market mechanics (not the operator), and periodic dividends are pegged strictly to a player's OpenElo, never to his share's trading price.

The founding design constraint, learned from studying Football Index's 2021 collapse: **no number that settles money can be something the operator has discretion over, and no payout can be pegged to the market's own trading activity.** Every mechanic below exists to preserve that constraint somewhere.

---

## 1. Rating Engine (OpenElo)

**Team Elo**

- Standard Elo exchange between two teams per match, adjusted by goal difference, home/away, and two related but distinct weighting factors: **match importance** (competition stage — group stage vs. final) and **competition state** (whether the result still affects either side's competition objectives). These aren't the same thing and shouldn't be collapsed into one factor: a UCL semi-final second leg after a 6-0 first-leg result is maximally important by stage, but its competition state is close to irrelevant — neither side's real objective (progressing) is meaningfully affected by the score in that second leg, so a bad result there shouldn't be punished the same as a bad result in a genuinely live tie, and a good result against a team already coasting to qualification shouldn't be rewarded the same either. Note this is entirely separate from in-match game state (live score/win-probability during play) — that's irrelevant here since substitution timing and in-game moments are deliberately not modeled (see Player Elo).
- Comparable in spirit to clubelo.com and Opta's Power Rankings — both are legitimate reference implementations for sanity-checking against.
- Cross-league comparability requires bridge matches: UEFA Champions League, Europa League, Conference League, and the Club World Cup. These are sufficient to anchor separate domestic leagues onto one shared scale — no need to expand beyond these plus the domestic leagues themselves.

**Player Elo**

- Derived from team Elo swings, attributed to individual players by presence/minutes — never from opposition player data. The question being modeled is "how much did this player help his team beat that team," not "how good is he relative to their personnel."
- Weight by fractional minutes played (minutes / 90), not binary appearance.
- A player's rating is a blend of two components: his +/- relative to his own team's performance, and his +/- relative to a "team without him" baseline. That baseline ages and decays the longer he goes without missing games — the model progressively loses information about what his team looks like in his absence, so it should progressively weight the team-relative component more heavily and the baseline-relative component less, rather than treating the baseline as permanently fresh.
- Do **not** attribute specific goals to specific substitution windows or credit individual scoring events to whoever was on the pitch at that moment. Substitution timing is chosen *because of* the scoreline (reverse causality), and per-substitution windows are too small a sample to separate skill from variance. Use season-aggregated on/off splits instead if a low-minutes, high-efficiency player ("supersub") profile needs to be captured — this is safer and already sufficient.
- Match-importance weighting (already part of the team-Elo formula) should be inherited into player attribution, since it naturally rewards players who are decisive in high-stakes matches without needing a separate mechanism for that.
- **Minutes-played bonus**: consistent selection under pressure (a manager continuing to start a player despite team inconsistency) is a costly, information-revealing signal worth crediting. Structure it as a *redistribution within the squad's fixed Elo pool* (starters draw a small share from bench players), not an external injection — otherwise it breaks conservation. Known confound to watch for: sunk-cost bias (clubs over-selecting expensive signings regardless of form) and thin-squad effects (undisputed starters with no alternative) can produce identical minutes patterns to genuine quality — worth testing for in back-tests, though the effect is likely concentrated in only the highest-fee/highest-wage players per squad.
- **Collinearity problem this needs to solve**: if two players are almost always fielded together in the same combination — a center-back pairing that's never split, for instance — the model has no independent variation to attribute credit between them individually; their ratings are forced to move together, correctly, but that also means real quality differences between them (if any exist) can go undetected indefinitely at the club level alone. This is the same "separating event" requirement from the convergence section (§2) — the model can only resolve individual contribution when something breaks up the usual grouping.
- **National team performance**: this is one of the most reliable sources of exactly that separating event, precisely because NT squads reshuffle players into different partners, different systems, and different roles far more than club sides do. Feed it in as NT-Elo predicted from the sum of player club-Elo, then use the residual against actual NT performance as a calibration signal back into personal Elo — this uses international results to test and refine club-derived ratings, rather than treating international football as a separate, competing measurement of "true" ability.
- **Cross-position comparison**: an attacker's observable value swings faster and more visibly upward than a defender's, because scoring is a discrete, instantly observable event while defending well is a slow accumulation of prevented non-events — there's no equivalent single moment that announces "a chance was prevented." This isn't a bug, it's just a difference in how fast the underlying quality can be observed, the same way some real assets are simply more volatile than others without that volatility being an error to correct — you don't flatten a growth stock's price swings to make it look like a utility stock's, you leave the volatility alone and build any comparison as a separate layer on top. The same asymmetry also runs in the other direction on the downside, and is worth designing for explicitly: a defender's value can swing down quickly through a short run of high-profile individual errors, while an attacker going a few games without scoring is comparatively unremarkable. So the two positions don't just differ in swing *size*, they differ in swing *shape* — attackers realize value quickly on the upside and lose it slowly, defenders realize value slowly and can lose it quickly — and neither profile needs to be normalized to match the other. If cross-position comparison is ever needed, build it as a separate downstream layer (e.g., percentile/z-score within position group), never as a modification of the raw number.

**Known, accepted limitation**: two players who are *always* fielded together with zero separating events (no injury, no rotation, no differing NT role) cannot be split by this model, and shouldn't be — there's no information to split them with. This is correct behavior, not a bug to chase.

---

## 2. Convergence & Validation Philosophy

- Validate on a small number of well-documented individual players with rich longitudinal histories, plus broad team-level coverage for the comparison/opposition side (team Elo doesn't need many *tracked* players, just many *tracked teams*).
- If the model doesn't converge sensibly on a modest test set (~100 players), the core design is unsound — this must be checked before building any trading infrastructure, cheaply, using public data only.
- Target is **near-guaranteed eventual convergence**, not fast convergence. Speed can be supplied by the market itself anticipating a future resolution (the same logic that makes any forward-looking market work), *provided* a real resolution event is actually guaranteed to eventually arrive. It doesn't have to be a transfer specifically — any separating context works (injury absence, cup rotation, suspension, differently-structured national team role, loan). Back-test how long, on average, before every tracked player generates at least one separating event of *any* kind; that interval is the real convergence-speed bound.
- Zero-sum conservation should be treated like actuarial reserving, not a physical law: aim for it through deliberate design (careful minutes redistribution, NT-Elo residual adjustment, calibrated debutant seeding, an explicit decay rule for retired/inactive players), but if some leakage remains after cleanup, measure its rate empirically and size the dividend pool with margin against it rather than assuming perfect conservation. (Chess Elo/FIDE is real-world proof that even a long-running, carefully curated Elo system can drift over decades — mainly from exactly these two levers: debutant seeding and unresolved exits.)
- If the interpretable/additive approach ever genuinely plateaus and a more complex (ML) model is considered: preserve reproducibility by freezing and permanently archiving the exact model version used to settle any real position, never retrain against live open trades, and publish full training data provenance. Prefer extending the additive model with more transparent, individually-justified terms before reaching for this — most of the richer data (tracking/positional) that would make ML meaningfully better isn't public anyway, so the realistic uplift is smaller than it looks, while the trust cost of going opaque is large.

---

## 3. Monetization & Market Mechanics

Details and reasoning: [ADR-0009](adr/0009-bonding-curve-pool-accounts.md) (where the curve's money lives) and [ADR-0010](adr/0010-market-mechanics-heat-priced-issuance.md) (how the market behaves).

**Revenue**: two kinds of income — a fee on peer-to-peer (P2P) trades, and profit from issuing new shares (the heat premium plus a mint fee, see below). The platform's cut starts at **0%**: while the platform grows, everything collected funds dividends. A later cut is a business decision, announced in advance.

**Dividends**

- Paid from **one capped pool for the whole market**, funded by that period's collected fees and issuance premiums (pari-mutuel structure) — payout can never exceed what's actually been collected.
- Split between players by their *current* OpenElo level only (like a steady dividend-paying equity), never by a share's trading price or by how much a player is traded. This is the single most important fix relative to Football Index: it removes the self-referential loop where price and payout inflate each other. One shared pool keeps it that way — a per-player pool would tie each player's payout to its own trading activity.
- How a player's slice is split per share (divided by that player's supply, or per share by Elo alone) is still open; it decides who bears the dilution from new issuance.
- When a player retires, dividends fade through the Elo decay rule (§2). The market itself doesn't change: no buyback, no final settlement price.

**Pricing system: calibration sets the starting point, the curve and its heat set everything after**

- The nominal (displayed) price a new player enters the market at should be scaled to resemble a real transfer fee for intuitiveness — set via a one-time calibration function fit by regressing historical (Elo-at-transfer, age) pairs against real transfer fees. This calibration only ever sets the *first point* on that player's pricing curve (supply = 0); it isn't touched again afterward.
- From that starting point onward, a public, fixed, monotonically increasing **base curve** gives each share a price as a function of supply — same formula and shape for every player, only the calibrated starting point differs. Redeeming pays this base curve back down: redeeming n shares at supply s pays the base prices of positions s−n … s−1, with no fee.
- **New shares cost the base curve × (1 + heat).** Heat measures recent demand for new shares: every share minted adds to it (less per share the larger the supply, with a small virtual supply so the first shares don't explode it), and it halves over a fixed period. The constants are public and the same for every player. The effect, with no extra rules: the earliest buyers pay the bare curve and are rewarded most; later buyers are never locked out but pay more, either a heated mint price or a P2P price set by earlier holders; a sudden breakout creates only a little new supply before the rise moves to P2P prices; and a forgotten player cools back to the bare curve and can be revived.
- Nobody, including the operator, picks a price or a quantity — the base curve and heat do. This is what removes operator discretion (and the resulting conflict of interest) over who gets a favorable price as demand comes in.
- Nominal price must be clearly disclosed as **not** a legal claim on, or convertible into, any real transfer — this needs to be explicit and repeated in-product, not just in terms of service.

**Issuance and redemption (the curve)**

- The curve is **permanently two-sided** (mint and redeem, always available, never closed). This guarantees a counterparty always exists, solving the illiquidity problem for thinly-traded/obscure players — the curve is a backstop of last resort, not the primary venue. Heat keeps minting from being the cheap way in while a player is in demand, so P2P trading carries most of a popular player's career: shares are minted when a player is new, traded between users, and redeemed at the end.
- Each player's curve holds exactly the base-curve price of every share it has issued, so it can always pay for redeeming every outstanding share — a full simultaneous mass redemption is covered whatever the curve's shape. The heat premium and the mint fee never enter it. This reserve is separate from the dividend pool; keep the two liabilities from blending.
- An order is priced share by share, heat included, so a large order can't buy every share at the first share's price, and a mint-then-redeem round trip always costs at least the mint fee.
- Every quote the operator honors must come from the public formula only — never a blended or discretionary "market price" — or the solvency guarantee and the no-discretion property both break at once.

**Trading between users (P2P)**

- The platform never trades on the book: no orders, no inventory, no "simulated" liquidity. Its only liquidity is the curve, whose quotes are shown as depth so thin markets still show real prices. The book is anonymous.
- P2P trades pay a smaller fee than minting, since matched trades don't require the operator to carry inventory or adverse-selection risk.
- Trading does not pause during matches: users trade against each other or against the formula, never against an operator quoting on the news.
- Inactive holders are never forced to sell; minting is always available at some price, so they can't block buyers.
- Current leanings, not final: 24/7 trading, a continuous limit order book, the curve and the book as separate venues, open orders backed by escrow postings, and a taker-only P2P fee.

---

## 4. Regulatory & Legal Posture

- Don't try to architecturally prevent insider trading (e.g., club staff trading on non-public team news) — handle it the same way betting platforms already do: contractually prohibited, KYC/ID-verified accounts, prosecuted and banned after the fact if caught. Not an engineering problem to solve upfront.
- Get an actual regulatory classification opinion (gambling product vs. financial derivative, and per-jurisdiction) before building the trading/payments layer. This ambiguity is specifically what caused Football Index's regulatory failure — neither UK regulator had a clean claim on the product, and that gap is what let a structurally unsound design run for six years.
- Validate rating convergence via back-testing on public historical data before ever touching payments or accepting a deposit — this is cheap and carries no regulatory exposure, and should come first.

---

## 5. Architecture (as currently planned)

- **Database**: PostgreSQL — the domain is inherently relational (players, teams, matches, competitions, shares, trades, dividends), and anything touching real money (share ledger, dividend payouts) needs ACID transactional guarantees.
- **Backend**: Java, Spring Boot + Spring Data JPA + Hibernate. Core domain logic (rating, pricing, dividend math) is written as plain Java against standard `jakarta.persistence` annotations, with a thin Spring web layer around it, so the framework stays replaceable.
- **Service decomposition**: microservices with boundaries drawn along consistency boundaries — see [ADR-0001](adr/0001-service-decomposition.md). The money core (ledger, wallets, bonding curve, trading) lives in a single `market-service` and is never split across services. Other services: `rating-service`, `ingestion-service`, `dividend-service`, `audit-service`, `gateway`; identity via Keycloak (OAuth2/OIDC).
- **Messaging**: Kafka as the event transport, fed by the transactional outbox pattern. PostgreSQL remains the source of truth for balances; Kafka is not.
- **Rating engine status**: mocked behind a `RatingProvider` interface while the backend is built; the real formula is validated offline in `research/` first (see §2, §4).
- Keep the Elo computation itself as application-layer service logic (reads raw match/minutes data, writes new rating snapshot rows) — not database stored procedures.
- Rough entity sketch: `Player`, `Team`, `Competition`, `Match`, `PlayerMatchStat`, `EloSnapshot` (rating-service); `Share`, `Trade`, ledger entries, `DividendPayout` (market-service).
- **Live data dependencies** (match results, player minutes): legitimate licensed APIs only (e.g., football-data.org, API-Football). For static dependencies ie. the ones we just check roughly to build model you can download Transfermarkt, CIES and OPTA scrapers from github.
- **Team Elo sanity-check reference**: Opta Power Rankings (free for top-flight clubs) and clubelo.com (fully open methodology) — run both, use disagreements between them and OpenElo as a diagnostic.
- **Historical transfer-fee data** (for the one-time nominal-price calibration and convergence back-testing only, not a live dependency): manual collection from public reporting, or an existing pre-compiled research dataset. Deliberately kept out of the production data path.
