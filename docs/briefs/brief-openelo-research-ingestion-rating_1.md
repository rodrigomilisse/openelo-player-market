# Brief: OpenElo formula research, ingestion-service and rating calculation

You are picking up three connected pieces of work in this repository:

1. **Research** the OpenElo formula and validate it offline (`research/`).
2. **Design** `ingestion-service`, which brings match data in.
3. **Design** the rating calculation in `rating-service`, which turns that data
   into ratings using the formula from step 1.

This brief tells you what is already decided, what exists, what each phase must
produce and the house rules. Read it completely before starting.

---

## 0. Scope of this run

**This run: Phase 1 (research, with code), then Phase 2 and Phase 3 as ADRs
only. Then stop.** Write no code under `services/`, and do not change
`infra/compose.yml`.

The owner's process for design changes: the ADR is written first, the owner
reviews and commits it, and implementation comes later in a separate run after
the owner gives the go-ahead. So:

- Never run `git commit`, `git push` or anything that rewrites history.
- Don't stop mid-run to ask questions unless you are truly blocked. Record each
  open decision in the relevant ADR as an open point, with its options and your
  recommendation, and keep going.
- At the end, ask the owner the most important open decisions with the
  `AskUserQuestion` tool (§8).

**Model.** This run uses Claude Opus. Claude Fable is available but much more
expensive, so the bar for switching is high. If one specific decision would be
substantially better with a short stretch on Fable, say which decision, why
Opus is likely to get it wrong, and what the Fable session would cover, and ask
the owner. Don't ask for routine work, and carry on with the rest of the run
meanwhile. The owner expects this won't be needed.

**If Phase 1 fails its own pass criteria** (§4.5), say so plainly: per Spec §2
that is a valid and important result. Still write ADR-0017, since ingestion
barely depends on the formula. Write ADR-0018 only for the parts that don't
depend on the formula, and mark the rest as blocked on research.

### Read first

| File | Why |
|---|---|
| `docs/Spec.md` §1, §2, §5 | The rating requirements. They are the specification for Phase 1. |
| `docs/adr/0001-service-decomposition.md` | Services, event flow, outbox, idempotent consumers. |
| `docs/adr/0006-normalization-as-a-design-goal.md` | The rule for storing a value versus deriving it. You need it for rating snapshots. |
| `docs/adr/0003`, `0005` | Entity, id and foreign-key conventions the new services will follow. |
| `docs/adr/0016-read-api-and-read-side-boundary.md` | The most recent ADR. Copy its format exactly. |
| `research/*.py`, `research/README.md` | The existing validation tool you will extend. |
| `services/*/README.md`, `infra/compose.yml` | Current state of the other services and the infrastructure. |

---

## 1. The project in one page

A trading platform for positions ("shares") in professional footballers. What
sets a player's value is not a transfer fee, an analyst's opinion or the
platform's own trading activity. It is **OpenElo**: an open, deterministic
rating computed only from public match results and player minutes, which anyone
can recompute from the same raw data. Dividends are paid from one capped pool
and split between players by their current OpenElo, never by share price or
trading volume.

The founding constraint comes from studying Football Index's 2021 collapse:
**no number that settles money may be something the operator has discretion
over, and no payout may be pegged to the market's own trading activity.** The
rating's reproducibility is part of that constraint. If the operator could tune
ratings by hand, it would control the dividend split.

Three things read the rating (Spec §3), and the formula has to serve all of
them:

- **The dividend split** uses each player's current rating *level*.
- **Retirement**: a retired player's dividends fade only because his rating
  decays. The market has no other retirement mechanism.
- **Price calibration**: a new player's starting price comes from a one-time
  regression of (rating at transfer, age) against historical transfer fees.

Most of the work so far is the money core (`market-service`: ledger, bonding
curve with heat-priced issuance, P2P order book, Redis balance projection;
ADR-0003 to ADR-0016). The rating side has hardly been started.

---

## 2. Decided by the owner. Do not reopen

- **Research comes first.** The model must converge sensibly on a modest test
  set (about 100 players) before anything is built on top of it (Spec §2, §4).
- **rating-service is Java / Spring Boot**, like `market-service`. `research/`
  stays Python. The validated formula is ported to Java once, and a parity test
  checks the port against the Python reference. ADR-0001 says rating-service
  "may later be Python". Record this decision in your new ADR. Do not edit
  ADR-0001 (rule in §7).
- **Production rating maths uses exact integers**, the same rule as money:
  fixed-point integer arithmetic with a stated rounding direction, so anyone
  recomputes exactly the same numbers. Ratings decide how the dividend pool is
  split, so they settle money. Research may explore in floats, but the final
  candidate needs an exact integer implementation in `research/` (Python `int`
  is arbitrary precision). That implementation is the reference the Java parity
  test will use. Elo's expected score needs `10^(x/400)`, so how to compute it
  exactly is a real design question (§4.4).
- **The Spec §1 and §2 rating requirements.** They are listed as a checklist in
  §4.3.
- **Data sources** (Spec §5): live dependencies (results, minutes) come only
  from legitimately licensed APIs (football-data.org and API-Football are
  named). Scrapers from GitHub (Transfermarkt, CIES, Opta) are allowed only for
  static, offline research. Historical transfer-fee data is used for research
  and the one-time price calibration, and stays out of the production data
  path.
- **Event flow** (ADR-0001): `ingestion-service ──match.completed──▶
  rating-service ──rating.snapshot.published──▶ dividend-service,
  market-service`. Events are JSON with a `schemaVersion` field and are
  published through a transactional outbox to Kafka. Consumers deduplicate by
  event id. Dividends settle against an explicitly referenced snapshot id,
  never "the latest" snapshot.
- **The rating computation is application-layer service logic**: it reads raw
  match and minutes data and writes rating snapshot rows. No stored procedures
  (Spec §5).
- **Additive and interpretable, not ML.** Prefer extending the additive model
  with transparent terms, each one justified on its own (Spec §2).

The three items below were decided by the owner in design discussions after the
Spec was written. The Spec does not carry them yet. Treat them as decided, don't
edit the Spec, and list them as Spec gaps in the final report.

- **Opponent strength is corrected in hindsight; published snapshots are not.**
  A rating computed *today* comes from replaying the whole history, and in that
  replay each past opponent's strength is a corrected estimate that also uses
  the matches the opponent played *after* the meeting. Example: you beat a
  highly rated team, which then loses ten in a row. You probably caught it at
  the start of a slump, so today's replay credits that win less. This applies
  to team Elo, and player ratings inherit it through the team swings. A
  snapshot that was already published, and any dividend settled against it,
  never changes. The correction behaves like a new match: it moves the current
  rating and leaves past payouts alone. Two parts are open and belong to
  Phase 1 (§4.3): how far a correction propagates, and how its weight falls as
  the time between the two matches grows.
- **Input tiers.** Tier 1, in the model: results, goals and minutes. Tier 2,
  undecided and tested in Phase 1: the corner differential per match, and team
  card totals. Tier 3, out: shots, saves, possession, fouls, offsides, expected
  goals, progressive passes. The owner's line is that an input must be a match
  fact the referee awards, not a statistic a data provider defines by its own
  method. Cards are never charged to the individual player: a suspension
  already shows up as missing minutes, and a sending-off already shows in the
  result.
- **The rating tracks what the market would pay, not isolated skill.** A squad
  player on a dominant side rating high is accepted, because buyers price him
  the same way. Don't add terms that try to strip team or system effects out.

---

## 3. Current state

**`research/`** (Python, never deployed):

- `openelo.py` is a stub: `openelo(player_name, as_of) -> float` returns
  `10000.0`. Everything downstream is written against that signature. You may
  change it (for example to return a fixed-point `int`, or to take a player id);
  update its callers if you do.
- `players.py` is a curated list of 100 retired or veteran players (top level
  between 2004 and 2024), resolved to Transfermarkt ids.
- `tm_client.py` scrapes Transfermarkt search and the market-value JSON
  endpoint. `db.py` is a SQLite store, built on a scrape-once, read-forever
  pattern.
- `data/openelo_market.sqlite3` holds 3,638 market-value points for all 100
  players, dated 2004-10 to 2026-07. It has **no match or minutes data** yet.
- `openelo_market.py` provides the subcommands `scrape`, `list`, `compare`,
  `average` and `correlation` (a lagged cross-correlation of OpenElo against
  Transfermarkt value, to see whether a phase shift is needed).

**`services/ingestion-service`, `services/rating-service`**: a README each, no
code. Spec §5 mentions a mock `RatingProvider`. **It does not exist anywhere**,
and `market-service` has no reference to ratings at all.

**`services/market-service`**: Spring Boot 4.1.1, Java 21, Maven wrapper,
Flyway, JPA with `ddl-auto=validate`, Postgres, Redis. It is the reference for
conventions (§7).

**`infra/compose.yml`**: Postgres (one `market` database) and Redis. No Kafka,
and no databases for rating or ingestion.

---

## 4. Phase 1: research the formula (code in `research/`)

### 4.1 Prior art

Write a short survey covering what each reference solves among the §4.3
requirements, what it costs in reproducibility, and whether you adopt it. These
are starting points; verify them yourself:

- **World Football Elo (eloratings.net)**: weighting by match importance, a
  goal-difference multiplier, home advantage.
- **clubelo.com**: open club Elo methodology. Also one of the two
  sanity-check references (Spec §5).
- **Hvattum & Arntzen (2010)**, *Using ELO ratings for match result prediction
  in association football*: the standard way to judge a football Elo by its
  predictions.
- **Glicko / Glicko-2**: rating uncertainty that grows with inactivity.
  Relevant to the "team without him" baseline that ages (Spec §1).
- **TrueSkill**: infers each player's skill from team results, with an
  uncertainty per player. The standard mechanism for attributing a team result
  to individuals.
- **Filtering versus smoothing in state-space models** (the Kalman filter and
  the Rauch-Tung-Striebel smoother; fixed-lag smoothing; TrueSkill Through
  Time; Glickman's dynamic paired-comparison models). A filter estimates a
  rating from earlier matches only. A smoother also uses later ones. This is
  the standard machinery behind the hindsight correction (§2).
- **Plus-minus in football**: Sæbø & Hvattum on regression-based player
  ratings; Kharrat, McHale & Peña (2020), *Plus-minus player ratings for
  soccer*. Also basketball's regularised adjusted plus-minus (RAPM), which uses
  ridge regression to handle collinear lineups. Adjusted plus-minus (APM) rates
  a player by how the score changes while they are on the pitch, corrected for
  teammates and opponents.
- **FIDE rating drift**: what debutant seeding and players who leave
  unresolved do to a long-running Elo pool (Spec §2).

### 4.2 Data

**What the model needs**:

- Matches: date, competition, stage, home, away or neutral venue, score
  (decide how extra time and penalty shoot-outs count), and for two-legged ties
  which leg it is and the aggregate.
- Lineups with minutes for every player.
- National-team matches.
- Enough coverage for team Elo: every team in the covered competitions, not
  only the teams of the 100 tracked players. The bridge competitions are the
  Champions League, Europa League, Conference League and Club World Cup, plus
  the domestic leagues themselves (Spec §1).
- Corners and cards per team per match, for the tier-2 test only (§4.3).

**Candidate sources.** Verify licence, coverage and format before using any of
them; don't trust this list:

- `dcaribou/transfermarkt-datasets` (on Kaggle as "Football Data from
  Transfermarkt"): games, appearances with minutes and lineups, reportedly from
  about 2012.
- football-data.co.uk: CSVs of domestic league results with long history but
  no lineups. Possibly enough on its own for team Elo. Its CSVs reportedly also
  carry corners and cards per team, which would cover the tier-2 test.
- API-Football (licensed). The owner expects to pay for a tier to validate. If
  a key is present in the environment, it is a legitimate source for lineups
  and minutes; check how far back its lineups go. If no key is present, use the
  other sources and say so in the findings.
- clubelo.com's API: team Elo history. A comparison reference, not an input.
- Transfermarkt match sheets, through existing GitHub scrapers, for minutes
  before 2012 (allowed for static research, Spec §5).

**Coverage gap.** The 100 tracked players are older, and their careers start
around 2004. A dataset that starts in 2012 covers only the second half of their
careers. Choose one approach, record it in the findings and say why: extend
coverage, narrow the evaluation window, or add a second player set. If you add
a second set, the owner's diagnostic cases belong in it: players who moved from
a weaker league to a stronger one (they test the shared scale), low-minutes
players who later commanded large fees (Julián Álvarez at Manchester City
2022 to 2024, Gonçalo Ramos at Paris Saint-Germain 2023 to 2026), and starters
who almost never missed a game.

**Storage.** Follow the `db.py` pattern: fetch once into SQLite, and have
everything read from the local store, never the network. Put newly downloaded
or scraped raw data, and charts derived from it, under a path you add to
`.gitignore` (for example `research/data/raw/`). The repo is public, and it
already tracks a scraped Transfermarkt SQLite file that the owner plans to
purge from history, so don't add more scraped data to git. The owner has not
approved this layout: do it, name it in the final report, and ask at the end
whether to keep it (§8). Leave the files that are already tracked where they
are. Raw downloads are untrusted input, so parse them; never execute them.

**If the data can't be had** (no source with minutes that you can legitimately
download, or no network access), don't substitute synthetic data and don't
report results you could not produce. Build as far as team Elo allows, say
exactly which checklist items and validations are blocked and on what, and
carry on to the ADRs under the rule in §0.

### 4.3 The model: requirements checklist

**What "converge" means here.** The rating is deliberately simple and open, so
at any moment it lags what richer analysis (scouting, tracking data, a good
analyst) would conclude about a player. Converging means that it *eventually
catches up* with that conclusion: a player who is better than his rating shows
will, given time and enough information, see his rating rise to reflect it. This
is what makes the market work. Traders do their own analysis to get ahead of
the rating, the way stock investors price a company on where its earnings are
going rather than on today's earnings (today's rating plays the role of today's
earnings). That only pays off if they can trust the rating to get there in the
end. So speed is not required, reliability is: the risk is an identifiable
group of players whose rating never catches up.

**Why separating events exist.** While a player is on the pitch, his share of
each team swing is mostly the team's result. If he plays every game with the
same teammates, his +/- simply tracks his team's rating, because the data
contains no case of the team without him. His individual contribution only
becomes visible when something splits him from his usual context: an absence
through injury, rotation or suspension, a different role or different partners
for his national team, a loan or a transfer. These are **separating events**.
They are the only source of new information about him as distinct from his
team, so the time between them bounds how fast he can converge. Players always
fielded together move together, and that is accepted. The group at risk of
never converging is the one that never gets a separating event: an
ever-present starter with stable partners, a stable club and no different
national-team role.

**Sanity checks are directional, not targets.** The references are clubelo and
Opta for teams, and Transfermarkt value for players. They are flawed and on
different scales, and the system is meant to differ from them. The test is
whether OpenElo is sensible: when a player's Transfermarkt value rose
substantially, did his rating also rise within a wide enough window around it?
Agreement in direction over a window, not matching numbers. You may also build
a richer model of your own as an extra reference if you think it is worth it,
but that is heavy and optional, and a manual review of individual cases is
best left to the end.

In the findings, handle each item below or mark it explicitly as unresolved,
with the reason.

**Team Elo**

- [ ] Standard Elo exchange per match, adjusted for goal difference and for
  home or away.
- [ ] **Match importance** (competition stage) and **competition state**
  (whether the result still affects either side's objectives, for example the
  second leg after a 6-0 first leg) are separate factors and must not be
  collapsed into one. In-match game state is not modelled.
- [ ] A single shared scale across leagues, anchored by the bridge
  competitions.
- [ ] **Hindsight correction of opponent strength** (§2). Look first for one
  mechanism: a rating that carries an uncertainty, filtered forward and then
  smoothed backward, gives the time weighting without a hand-written decay,
  because a later result says less about an earlier date the more time lies
  between them. A later slump cannot tell "the team was overrated when we met"
  apart from "the team declined afterwards", so the correction is a weighted
  blend, never a full replacement. Decide and justify the propagation depth:
  one step (an opponent is corrected only by its own later matches) or a full
  refit of the connected history. Compare against the forward-only model on the
  pre-stated objective.
- [ ] **Tier-2 inputs** (§2). Test whether the corner differential, and
  separately team card totals, improve the pre-stated objective over goals
  alone, as an extra lower-weight signal of team strength inside the same
  exchange. Adopt one only on a clear out-of-sample gain. Report the result
  either way.

**Player Elo**

- [ ] Derived from team Elo swings and attributed by fractional minutes
  (minutes / 90). Never from opposition player data.
- [ ] A blend of two parts: the player's +/- relative to his own team, and his
  +/- relative to a "team without him" baseline. The baseline loses
  information, and therefore weight, the longer he goes without missing games.
  In the limit, a player who never misses a game tracks his team's rating. That
  is accepted.
- [ ] No attribution to substitution windows or individual scoring events
  (reverse causality, tiny samples). Low-minutes "supersub" profiles use
  season-aggregated on/off splits.
- [ ] Match importance carries over into player attribution.
- [ ] **Minutes-played bonus**: a redistribution within the squad's fixed pool
  (starters draw a small share from the bench), never an injection from
  outside. The owner's reasoning is that continued selection reveals what the
  manager knows and the public doesn't. Test it for the sunk-cost confound
  (expensive signings selected regardless of form) and the thin-squad confound
  (no alternative to the starter). The owner expects the sunk-cost effect to be
  confined to a squad's one or two most expensive players; test that claim
  directly.
- [ ] **Collinearity**: players who are always fielded together cannot be
  separated and must move together. This is accepted behaviour, not a bug.
- [ ] **National teams**: predict national-team Elo from the sum of the
  players' club Elo, and feed the residual against actual national-team results
  back into the personal rating as a calibration signal. International football
  is not a separate, competing measure of ability.
- [ ] **Positions**: leave the raw number alone. Attackers and defenders differ
  in swing size and shape, and that is real. Any cross-position comparison is a
  separate layer downstream (for example a percentile within position).

**Pool-level**

- [ ] Conservation is treated like actuarial reserving: designed for
  (minutes redistribution, the national-team residual, calibrated seeding of
  debutants, an explicit decay rule for retired and inactive players) and then
  measured, not assumed. Measure it under the hindsight replay too.

**How to design it.** The owner wants *systems, not rules*. For each
requirement, look first for one mechanism whose dynamics produce the behaviour.
For example, an uncertainty per player that grows with time since the last
separating event (in the style of Glicko or TrueSkill) can replace a
hand-written decay schedule for the baseline, and the same uncertainty, run
backward, can produce the hindsight correction. If a requirement really needs a
special-case rule, say so explicitly and explain why no mechanism works.

**Constants** (K factors, the scale, decay rates and so on) are chosen by an
objective stated before fitting, such as the predictive log loss on held-out
seasons. Never tune them until the charts look right. Fit on earlier seasons
and evaluate on later ones.

### 4.4 The exact integer form

Give the final candidate in exact integer arithmetic. Specify:

- The fixed-point scale of a rating.
- How the expected-score function is computed exactly. Lay out the options with
  their trade-offs: an integer lookup table over a bounded rating-difference
  range, a rational approximation with a stated maximum error, a fixed-point
  series, or a different expected-score curve that needs no exponent.
- The rounding direction at every division, and where any rounding residue goes
  (conservation).
- The processing order. The result must not depend on the order the input rows
  happen to arrive in, so say how matches on the same day are ordered or
  batched, and how a player who appears in two of them is handled.
- The "as-of" rule. Because of the hindsight correction, a rating is a function
  of every match known at the date it is computed. Define the computation so
  that the rating for date D, computed with only the matches up to D, is always
  the same number. The hindsight correction, including any uncertainty term,
  needs the same exact integer form as the rest.
- What the zero of the scale means. Elo only defines rating *differences*, but
  the dividend split uses the level (§1), so shifting every rating by a
  constant changes the split. State what the formula fixes about the level
  (the seed, the anchor) and report how sensitive a proportional split is to
  it. One option the owner has considered is splitting by standing relative to
  the pool (distance above the pool average, or percentile), which removes the
  dependence on the zero; report how it compares. Don't design the split
  itself; that belongs to dividend-service.
- A check that the integer version tracks the float version within a stated
  tolerance on the real data.

This is the reference implementation the Java port must later match exactly.

### 4.5 Validation

**Write the pass/fail criteria into the findings before running the
evaluation.** Then report each one:

- **No look-ahead.** The hindsight correction puts later results into earlier
  ratings. Score every prediction with the rating as it would have been
  published before the match (the as-of series). Report the hindsight series
  separately and never score predictions with it.
- **Team Elo prediction**: out-of-sample log loss and Brier score on match
  outcomes, against a plain-Elo baseline and against clubelo where available.
  Report rank correlation with clubelo (and Opta Power Rankings, if it can be
  obtained legitimately), and list the biggest disagreements as diagnostics.
- **Hindsight correction**: the as-of log loss with and without it. Also the
  size distribution of rating moves on days a team did not play, since holders
  will see those moves. And how much the rating for a given date still moves
  as each further week of later matches arrives, which informs the delayed
  freeze option (§6.7).
- **Tier-2 inputs**: the gain or loss on the objective for each, and whether
  you adopt it.
- **Players against Transfermarkt**: use the existing `compare`, `average` and
  `correlation` commands. The check is directional (§4.3): for substantial
  moves in Transfermarkt value, how often the rating moved the same way within
  a window around them. Report the window and lag that work best.
- **Convergence**: back-test how long it takes, on average, until every tracked
  player has at least one separating event of any kind (injury absence,
  rotation, suspension, a different national-team role, a loan, a transfer).
  That interval is the real bound on convergence speed. Report, per player,
  how long the rating takes to catch up with the direction of the references.
  The bar is reliability, not speed: a rating that catches up slowly for nearly
  everyone passes. If an identifiable group never catches up, that is the
  finding to report, with the group named.
- **Conservation**: the leakage rate per season, broken down by source
  (debutants, retirements, rounding, the bonus, the hindsight replay).
- **Collinearity**: list the pairs that never separate, and confirm they move
  together.
- **Minutes bonus**: the results of the confound tests.
- **Positions**: swing size and shape by position group, reported, not
  corrected.

### 4.6 Phase 1 deliverables

- Code in `research/`. The real formula replaces the `openelo()` stub; data
  loaders follow the existing style; update `research/requirements.txt` if you
  add dependencies.
- `research/FINDINGS.md`: the prior-art survey, data choices, the model with
  every checklist item, the exact integer form, the pre-stated criteria, the
  results, and plainly what failed or stayed open.
- Every number in the findings can be regenerated from the local store by a
  command listed in `research/README.md`. Reproducibility is the product's
  promise, so the research has to meet it too.
- Charts in the gitignored path (§4.2).

---

## 5. Phase 2: ADR-0017, ingestion-service (ADR only)

Restate the decided items briefly. Mark everything else *Proposed* or *Open*,
with options and a recommendation. The ADR must cover:

1. **Role.** An anti-corruption layer: external data is untrusted, gets
   validated, and is turned into domain events. It holds no rating logic.
2. **Runtime.** Java / Spring Boot, mirroring `market-service`. *Proposed*: the
   owner decided Java for rating-service, not yet for ingestion.
3. **Providers.** Compare football-data.org and API-Football (and any other
   licensed option you find): which competitions are covered, including the
   bridge competitions and national teams; whether lineups and minutes are
   included and on which tier; rate limits; cost. **Above all, the terms of
   use.** OpenElo promises that anyone can recompute it from the same raw data.
   Check whether the provider's licence allows publishing that raw data or the
   ratings derived from it. If not, that conflicts with the Spec's central
   promise. Raise it as a major open point; don't paper over it.
   The owner's notes from mid-2026, to verify and not to trust:
   football-data.org's free tier had results and standings for 12 competitions
   at 10 requests a minute and no lineups, which needed its tier at about €29 a
   month. API-Football's free tier allowed about 100 requests a day, and its
   paid tiers were about $19, $29 and $39 a month for 7,500, 75,000 and 150,000
   requests a day.
4. **Adapters.** One port (interface) with an adapter per provider, plus a mock
   adapter first (the README says "mocked for now").
5. **`match.completed` v1 schema.** Derive the fields from what the Phase 1
   formula actually consumes: competition, stage, leg and aggregate, venue,
   score and extra-time handling, and per-player team and minutes, with a flag
   for national-team matches. Corners and cards per team only if Phase 1 adopts
   a tier-2 input. JSON with `schemaVersion`.
6. **Identity mapping.** Provider ids have to map to catalog ids. ADR-0001 says
   rating-service owns the catalog. Who holds the mapping? *Open*.
7. **Validation rules.** What makes data invalid: implausible minutes, the
   wrong number of starters, duplicate players, unknown teams, inconsistent
   substitutions. What happens to rejected data: a quarantine table, an alert,
   and how it is replayed after a fix.
8. **Corrections and late data.** Providers revise data. Matches get abandoned,
   replayed or awarded. Decide how a correction is expressed (a new version of
   the same match, or a separate event) and what rating-service does with it.
   Each fact needs the time it became known, because rating-service must be
   able to replay "as known on date D" (§6.4).
9. **Delivery.** A transactional outbox relayed to Kafka. ADR-0001 lists no
   database for ingestion, but an outbox needs one, so propose it. Kafka is not
   yet in `infra/compose.yml`; list it as a prerequisite and don't add it.
10. **Schedule.** When to poll, how rate limits shape the schedule, and backfill.
11. **Production backfill.** Elo needs years of history to warm up. Static
    scraped data is barred from the production path, so the history must come
    from the licensed provider, or the ratings must start at a seed date with
    stated seeding. *Open*: lay out the options.
12. **Fixtures.** The owner's stated principle is that minting and redeeming a
    player's shares is suspended while his match is in play. That needs
    kick-off times before the match. Check whether an existing ADR already
    settles how market-service learns them. If none does, raise "does ingestion
    publish fixtures?" as an *Open* point and don't design it.
13. **Out of scope.** Transfer fees (research only).

---

## 6. Phase 3: ADR-0018, rating calculation in rating-service (ADR only)

1. **Decided.** Java / Spring Boot. Exact integer maths. Application-layer
   logic. Consumes `match.completed` idempotently, writes snapshot rows,
   publishes `rating.snapshot.published`. This amends ADR-0001's "may later be
   Python". Also decided (§2): opponent strength is corrected in hindsight, and
   published snapshots never change.
2. **Catalog model.** The Spec's sketch is `Player`, `Team`, `Competition`,
   `Match`, `PlayerMatchStat` and `EloSnapshot`. Check it against the schema
   rules in §7 (no nullable columns: an optional relationship gets its own
   table; native enums). For example, a player's position, or a match that has
   a second leg, are optional facts.
3. **Is a rating stored or derived?** Apply ADR-0006's test. A rating is a
   deterministic function of the ingested facts plus a constants version, so it
   is derived. But a snapshot that dividends settled against is a published,
   frozen value. The hindsight correction sharpens this: computing the rating
   for a past date later, with more matches known, gives a different number
   from the one published then. So a published snapshot can be regenerated
   only from the facts known at its date, not from all facts. Argue whether the
   snapshot is a fact or a cache, and what that means for the tables.
4. **Determinism and replay.** Replaying from the raw facts known at a
   snapshot's date reproduces that snapshot exactly. Kafka can deliver matches
   late or out of order, so the result must follow the processing order defined
   in §4.4, not the arrival order. Constants and the model are versioned and
   published. Any version that settled money is frozen and archived, and is
   never refitted against live positions (Spec §2).
5. **The formula** in the integer form from §4.4, presented by the formula
   rules in §7.
6. **Parity.** The Java implementation must reproduce the Python reference
   bit for bit on a fixture. Say where the fixture lives and how it is
   generated.
7. **Snapshot cadence.** Per match, per matchday or per dividend period?
   *Open*. Note that with the hindsight correction a player's rating can move
   on a day his team did not play. One option the owner wants evaluated: a
   provisional rating updated after every match for display only, with the
   snapshot that settles a dividend frozen later, after a window of further
   matches has corrected it (for example, the rating for the end of September,
   frozen at the end of October with October's matches, settles the October
   dividend). Once frozen it never changes. Weigh it against freezing
   immediately, and say what it means for the window length, the record date
   (who receives a dividend when a share changes hands in between) and the
   display.
8. **Corrections.** Recompute forward from the corrected match, write new
   snapshots, keep the old ones. A provider correction and the hindsight
   correction go through the same replay; say whether they are one mechanism
   in the design.
9. **Lifecycle.** Seeding debutants, decay for retired and inactive players,
   and national-team calibration, as concrete processing steps.
10. **Consumers.** How dividend-service and market-service read ratings
    (events; no synchronous calls in the money path). The `RatingProvider` mock
    the Spec mentions was never built. Say what replaces it.
11. **Infrastructure prerequisites.** A `rating` database and Kafka in compose.
    List them; don't add them.

---

## 7. House rules

**ADRs**

- Next numbers are 0017 and 0018 in `docs/adr/`. Copy ADR-0016's structure:
  title, Status, Date, Context, Decision split into *Decided* / *Proposed*,
  Consequences as `+` / `−` lines, Alternatives considered, Open points.
- **Never edit an older ADR.** A new ADR states what it amends ("Amends
  ADR-0001 …").
- **Separate decided from proposed.** Only what this brief lists as decided, or
  what the existing docs settle, is *Decided*. Your own design choices are
  *Proposed*, however confident you are.
- **The Spec's reasoning is not beyond question.** The owner considers it
  solid, so don't go looking for problems, but if the research turns up an
  actual error in it, say so plainly in the findings rather than silently
  working around it or silently complying with it, with what you'd change and
  why.
- Lead with the industry-standard solution, say why it is standard, name its
  cost honestly, and say why the alternatives lose. The project is partly for
  learning, so explain the mechanism, not just the conclusion.
- Spell out jargon and acronyms on first use (for example APM, RAPM, ACL).

**Formulas** (in findings, ADRs and code)

- At most 3 or 4 variables per equation. Compute anything more on an earlier
  line as a named intermediate value.
- Spell names out (`ratingDifference`, `expectedScore`, `minutesShare`), never
  single letters.

**Schema** (for the ADRs' table designs)

- Fully normalised, with no nullable columns. An optional relationship gets
  its own table.
- Enums are Postgres native `ENUM` types, mapped with
  `@Enumerated(EnumType.STRING)` + `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`. Never
  VARCHAR, never ordinals, and never pass an enum to a query as a string.
- Computed reads are database views mapped as `@Entity @Immutable
  @Synchronize(...)`. No native SQL strings in Java.
- Ids are UUID v7, generated by Hibernate (`BaseEntity`). Ids carry no meaning:
  never sort by id to get time order; use an explicit `created_at`. Ids are
  typed at the API edge (`Id<T>`) and raw `UUID` in repositories.
- Flyway migrations: once a migration has been applied anywhere, it is frozen.
  Add a new one; never edit it.
- An index only where it turns a scan into a direct lookup. No
  micro-optimisation.
- Foreign keys within a database; across databases, ids are valid by
  construction and checked by reconciliation (ADR-0005).

**Code** (for the research code now and the Java port later)

- Exact integers in the production rating path. Business arithmetic in Java
  goes through `Math.addExact`, `multiplyExact`, `subtractExact`,
  `divideExact` and `negateExact`. Plain operators are for loop counters,
  indices and comparisons only.
- Simple checks are private `requireX()` methods that throw.
- Public methods read as a list of named steps.
- Mirror the style of sibling classes in `market-service`.
- Interface naming: `I<Name>` for values, `Recorded<Self>` for persisted rows,
  `<Name>Request` / `<Name>Response` records nested in controllers. Everything
  a module returns is read-only.
- Comments only for non-obvious reasons. No restating the code, no narrating
  the task, no invented TODOs.

**Process**

- Build only what this brief scopes. If you think something extra is worth
  doing, propose it at the end; don't slip it in.
- **No silent changes.** Name every non-obvious choice (a signature change, a
  workaround, a gitignore entry) in your final report.
- Keep verification light for code; the research evaluation itself is the
  substantial check.

---

## 8. End of run

Finish with a report to the owner:

1. **The verdict**: pass or fail against each pre-stated criterion, in one
   table, and whether the model is fit to build on.
2. **Files** created or changed, with a note that all of it is uncommitted and
   left for the owner to review and commit.
3. **Choices you made** that the owner did not (§7 "no silent changes").
4. **Spec gaps**: the three decisions in §2 that the Spec does not carry yet,
   and anything else you found the Spec and this brief disagree on.
5. **Open decisions**, asked with `AskUserQuestion`: at most four per call,
   recommended option first, labelled "(Recommended)". Each option is a single
   decision, with no extra rules bundled in. Questions must stand on their own,
   and jargon is spelled out. Priority: the provider licence and
   recomputability conflict, production backfill, how far the hindsight
   correction propagates, the expected-score method, snapshot cadence, keeping
   raw data out of git. If the scale's zero turns out to move the dividend
   split materially (§4.4), that goes first.
