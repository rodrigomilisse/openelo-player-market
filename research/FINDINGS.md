# OpenElo formula research: findings

Phase 1 of the brief `docs/briefs/brief-openelo-research-ingestion-rating_1.md`.
Every number here is regenerated from the local store by the commands in
[README.md](README.md).

## 1. Pre-stated evaluation protocol and pass/fail criteria

Written on 2026-11-12, after the data was loaded and inspected and before any
model was fitted or scored. Nothing in this section was changed after results
were seen; later notes, if any, are marked as such.

### 1.1 Protocol

- **Data**: club matches from transfermarkt-datasets, 2012/13 to 2025/26
  (§3). National-team matches are not in the team pool (§4.2).
- **Seasons**: 2012/13 and 2013/14 are burn-in and never scored.
  2014/15 to 2018/19 are the **fit seasons**: every constant is chosen there.
  2019/20 to 2025/26 are the **test seasons**: held out, scored once per
  variant.
- **Scored matches**: club matches in which both teams have played at least 20
  earlier matches in the data, so cold starts are not scored. The same filter
  applies to every model.
- **Objective** (chosen before fitting): mean three-way log loss (natural log)
  of home win / draw / away win, with the result after extra time and a
  shoot-out counted as a draw. The Brier score (sum of squared errors over the
  three outcomes) is reported alongside.
- **From a rating difference to three probabilities**: an ordered logit on the
  pre-match rating difference (home advantage included), fitted on the fit
  seasons only and frozen for the test seasons (Hvattum & Arntzen, 2010).
- **No look-ahead**: every prediction uses the rating as it would have been
  published before the match (the as-of series). The hindsight series is
  never used to score a prediction.
- **Uncertainty**: differences between models are reported with a 95% paired
  bootstrap interval over scored matches (1,000 resamples).
- **Adopting a feature** (tier-2 inputs, match importance, competition state,
  the minutes bonus): only on an out-of-sample gain whose 95% interval
  excludes zero. Rejected features are reported with their numbers.

### 1.2 Criteria

| # | Criterion | Pass when |
|---|---|---|
| C1 | No look-ahead | The as-of rating for a date is bit-identical when every match after that date is removed from the input (checked on the integer reference for sampled dates). |
| C2 | Team prediction | The candidate's test log loss is lower than the plain-Elo baseline's, with the 95% interval of the difference below zero. |
| C3 | Agreement with clubelo | Test log loss within 0.010 nats of clubelo's on the matches both rate, and Spearman rank correlation with clubelo of at least 0.85 at every 1 June snapshot, over teams both rate. (clubelo has decades more history and is read from snapshots up to 15 days old; the tolerance allows for both.) |
| C4 | Hindsight correction does no harm | As-of test log loss with the correction is no worse than without it by more than 0.001 nats. |
| C5 | Tier-2 inputs | Not pass/fail. A decision rule: corners or cards are adopted only on a test gain of at least 0.001 nats with the interval excluding zero. |
| C6 | Player layer carries information | Predictions adjusted by the announced starting eleven's player ratings beat team-only predictions on the test seasons, with the interval excluding zero. Informative; it does not block the verdict. |
| C7 | Players against Transfermarkt | For substantial Transfermarkt moves (consecutive valuations differing by at least 25%, the larger at least €5M), the share where OpenElo moved the same way over the primary window, 6 months before to 6 months after the new valuation, is at least 60% and significantly above 50% (one-sided binomial test, p < 0.01). Checked for set A and set B separately. Other windows and lags are reported as a scan. |
| C8 | Convergence | (a) At least 90% of tracked players with a full covered season have a separating event within their first covered season. (b) No identifiable group of at least 5 tracked players sharing a profile catches up with Transfermarkt's direction in fewer than 40% of its substantial moves. A failing group is named. |
| C9 | Conservation is measured | In the integer reference, the change of the player pool equals the sum of the itemised sources exactly (zero unexplained residual), and each source's rate per season is reported. |
| C10 | Collinear pairs move together | For pairs that never separate, the correlation of their per-match rating changes is at least 0.99. Informative. |
| C11 | Integer tracks float | Largest absolute difference between the integer and float implementations at most 1 Elo point, for team and player ratings, over every snapshot on the real data. |
| C12 | Order independence | Shuffling the input rows gives bit-identical integer output. |

**Verdict rule**: the model is fit to build on if C1, C2, C7, C8, C9, C11 and
C12 pass. C3 to C6 and C10 inform the design and are reported either way.

## 2. Prior art

What each reference solves among the requirements (§4.3 of the brief), what it
costs in reproducibility, and whether it is adopted. Two methodology pages,
eloratings.net (rendered by JavaScript) and clubelo.com/System (refuses
automated reads), could not be read from here; what is said about them below
is their widely documented method, not re-verified on the day.

| Reference | Solves | Reproducibility cost | Adopted? |
|---|---|---|---|
| **World Football Elo** (eloratings.net) | Elo exchange per match; a margin multiplier (1, 1.5, then (11 + margin) ÷ 8); K by match importance (friendlies 20 up to World Cup finals 60); home advantage; a shoot-out counts as a draw | None: closed-form, published constants | Margin multiplier and shoot-out rule **adopted**. Importance by stage **tested, not adopted** (§4.3). Home advantage fitted (50 points, not 100). |
| **clubelo.com** | Open club Elo across Europe, one scale through European matches, promoted teams seeded from the teams they replace | None | Used as a **reference**, not an input (§4.6). Its seeding idea is adopted in the form "a new team starts below the mean of the league it enters". |
| **Hvattum & Arntzen (2010)**, *Using ELO ratings for match result prediction in association football* | How to judge a football Elo: an ordered logit from the rating difference to three outcome probabilities, scored against bookmakers | None | **Adopted** as the evaluation (§1.1); bookmakers are the upper reference (§4.6). |
| **Glicko / Glicko-2** (Glickman) | A rating deviation per player that grows with inactivity, so stale ratings move faster when evidence returns | Adds a variance per team; still closed-form | **Adopted** for teams in the form of an extended Kalman filter step (Szczecinski & Tihon's simplified Kalman filter for online rating, 2023): §4.2. |
| **TrueSkill** (Herbrich, Minka & Graepel, 2006) | Team performance as the sum of player skills, with a variance per player: the standard way to attribute a team result to individuals | Message passing; deterministic but heavier | **Not adopted** as such: the Spec builds players from team Elo swings, not the other way round. Its two ideas survive: attribution weighted by playing time, and players fielded together moving together. |
| **Filtering versus smoothing**: Kalman filter and Rauch–Tung–Striebel smoother (1965), fixed-lag smoothing, TrueSkill Through Time (Dangauthier et al., 2007), Glickman's dynamic paired comparisons | A filter rates from earlier matches only; a smoother also uses later ones. Running a variance-carrying rating forward then backward gives a time-weighted correction with no hand-written decay. Iterating (expectation propagation) lets corrections travel through the connected history | Needs a fixed lag and a fixed iteration count to stay exactly reproducible; costlier per day | **Adopted** as the hindsight correction (§4.4), with a fixed lag and a fixed number of iterations. |
| **Plus-minus in football**: Sæbø & Hvattum (regression-based player ratings, 2015, 2019); Kharrat, McHale & Peña (2020), *Plus-minus player ratings for soccer* | Rates a player by the team's goal difference while he is on the pitch, corrected for team-mates and opponents (adjusted plus-minus, APM) | A regression over all line-ups; reproducible but opaque to a lay reader | **Not adopted** directly. Its main lesson is confirmed here: an individual's on/off signal in football is weak and needs a prior (they use market values; OpenElo may only use match facts, so its prior is the team's rating, §5.1). |
| **Regularised adjusted plus-minus (RAPM)** (Sill, 2010, basketball) | Ridge regression to separate players who are usually on the court together | As above | The **idea is adopted**: shrinking every player towards his team's rating is the same move as shrinking towards a ridge prior (§5.1). |
| **FIDE rating drift** | A long-running Elo pool drifts with who enters and who leaves: debutants seeded below their real strength deflate the pool as they improve; players who leave take points out. FIDE cut its rating floor in steps and in March 2024 applied a one-off lift to every rating under 2000 (by 0.4 × (2000 − rating)) | — | **The lesson is adopted**: entry and exit are designed (calibrated debutant seeding, an explicit decay) and then measured (C9, §6.5), not assumed away. |

## 3. Data

### 3.1 Sources

| Source | What | Licence and status | Used for |
|---|---|---|---|
| transfermarkt-datasets (github.com/dcaribou/transfermarkt-datasets), snapshot of 6 July 2026 | 88,769 matches from 2012/13; 1.89 M appearances with minutes; 3.18 M line-up rows (starters and bench); players, market values, transfers | Repository CC0; the data is scraped from Transfermarkt, so static research only (Spec §5) | All rating inputs |
| Club-Football-Match-Data (github.com/xgabora/Club-Football-Match-Data) | football-data.co.uk results with corners, cards and Bet365 odds; clubelo.com snapshots on the 1st and 15th of each month | Repository MIT; football-data.co.uk states its data is free but "All Rights Reserved"; clubelo snapshots after 1 June 2025 are the repository author's continuation and are dropped | Tier-2 test (corners, cards), bookmaker benchmark, clubelo reference |

**API-Football**: no key was present in the environment, so it was not used.
**clubelo's own API** answered 502 throughout; its snapshots came through the
mirror above.

Coverage, from the store (`ingest.py` prints it):

- 14 top flights with minutes for 99–100% of matches over all 14 seasons
  (England, Spain, Italy, Germany, France, Netherlands, Portugal, Belgium,
  Turkey, Russia, Scotland, Greece, Ukraine, Denmark), their cups and super
  cups, and every UEFA club round including qualifying (Champions League 99.8%
  with minutes, Europa League 98%, qualifiers 70–80%).
- Ten more leagues (Austria, Switzerland, Brazil, MLS, Saudi Arabia and others)
  only from 2024; they enter the pool late, through their own matches and the
  2025 Club World Cup.
- **Gaps**: the Conference League has results but no minutes; domestic cups
  have minutes for 50–85% of matches (the lower-division side is often
  missing); **national teams have line-ups only for 2024–2026** (Copa América
  2024, Asian Cup 2024, AFCON 2025, World Cup 2026). Every World Cup and
  European Championship from 2006 to 2024 has results but no line-ups.

### 3.2 Defects found and how they are handled

- **Shoot-outs are added into the score.** A 0-0 won 5-3 on penalties is stored
  as 5:3. Shoot-out events are subtracted; because long shoot-outs are
  sometimes incomplete in the events, the model never trusts the corrected
  goals for a shoot-out: a single match decided on penalties is a draw with
  goal difference 0, and a second leg's goal difference follows from the first
  leg (the aggregate was level). 58 matches carry the flag
  `incomplete_shootout_events`.
- **The column named `aggregate` is the match score**, not the two-leg
  aggregate. Legs are paired by competition, season, round and reversed teams
  (3,852 second legs).
- **Neutral venues are not flagged.** League matches are treated as home
  matches. Any other club match is neutral when its stadium is none of the home
  club's league grounds that season (finals, the 2020 single-venue rounds,
  clubs playing "home" European matches abroad): 1,185 matches. National-team
  tournament matches are neutral unless the home side is a host.
- **Four matches have a team playing twice on one day**; they are data errors
  and are left out of the rating.

### 3.3 The coverage gap, and the second player set

The original 100 players (set A) are veterans whose careers start around 2004;
the data starts in 2012. 94 of them appear, 63 with at least 200 matches, but
14 have nothing after 2014.

**Choice: add a second player set (set B) and evaluate set A over its covered
years.** Extending coverage back to 2004 would need minutes for every player of
every covered team, not just the 100 (the "team without him" baseline and the
conservation accounting both need whole squads), plus pre-2012 European
results that no open dataset found here has. That is a scrape of hundreds of
thousands of match sheets, beyond "static research" in spirit. Narrowing the
window alone would leave the owner's diagnostic cases untested. Set B is 57
players whose careers lie inside 2012–2026, grouped by what they test
(`players.SET_B_GROUPS`):

- **league movers** (20): weaker to stronger league, which tests the shared
  scale (Van Dijk, Luis Díaz, Darwin Núñez, Frenkie de Jong, Haaland, Salah,
  Kvaratskhelia, …);
- **low minutes, later a large fee** (5): Julián Álvarez, Gonçalo Ramos, Cole
  Palmer, Jadon Sancho, Rodrygo;
- **ever-present starters** (13): goalkeepers (Oblak, ter Stegen, Alisson,
  Ederson, Pickford) and outfielders who rarely missed a match (Kane, Rice,
  Azpilicueta, Rodri, Bernardo Silva, Koulibaly, Milinković-Savić, Kimmich);
- **young stars** (19), as a control.

Every name resolved to one Transfermarkt id; the ids are pinned in
`players.SET_B_TM_IDS`.

### 3.4 Storage

Downloads, the derived store and every chart or result derived from them live
under `research/data/raw/`, added to `.gitignore` in this run. The tracked
`data/openelo_market.sqlite3` and `outputs/` are untouched. `ingest.py` parses
the raw files as data and imports nothing local, so it runs in isolated mode.

## 4. Team Elo

Command: `evaluate.py team` (§4.1–4.3, 4.5), `evaluate.py hindsight` and
`evaluate.py replay` (§4.4), `evaluate.py benchmarks` (§4.6).

### 4.1 The model

Every team carries a rating and a variance (how unsure the rating is). Per
match, as a batch per day:

```
ratingDifference = homeRating + homeAdvantage − awayRating      homeAdvantage = 0 at a neutral venue
expectedScore    = 1 ÷ (1 + 10^(−ratingDifference ÷ 400))
surprise         = score − expectedScore                       score: 1 win, ½ draw (and every shoot-out), 0 loss
```

The update is the extended Kalman filter step of a logistic observation (the
"simplified Kalman filter" of Szczecinski & Tihon, and in effect Glicko):

```
slope         = ln 10 ÷ 400
spread        = expectedScore × (1 − expectedScore)
load          = weight × slope² × spread × variance             one load per side
gain          = variance × slope × weight ÷ (1 + homeLoad + awayLoad)
swing         = gain × surprise                                   home +, away −
variance'     = variance × (1 + otherLoad) ÷ (1 + homeLoad + awayLoad)
```

and between matches `variance` grows by `processNoise` per idle day, capped
at the variance a new team starts with. `weight` is World Football Elo's margin
multiplier (1 for one goal, 1.5 for two, (11 + margin) ÷ 8 beyond).

The variance is the one mechanism behind three behaviours that would otherwise
need rules: a new or promoted team moves fast until its level is known; a team
returning from the summer break moves faster than in March, because its
squad may have changed; and an established team settles to a steady step,
which is ordinary Elo with K ≈ 20. Standard Elo is the limit where every
variance is equal and constant.

**Seeding.** Every team in the first season starts at 1500. Later, a team seen
for the first time in a league starts at that league's current mean less
100 points (promoted teams are weaker than the league they join); a team first
seen outside a covered league (a cup's lower-division side, a qualifier from
an uncovered country) starts at the pool's mean less 300. Both offsets were
fitted.

**What the exchange gives up.** Because each side's gain depends on its own
variance, a match is not exactly zero-sum: a new team with a large variance
absorbs most of a surprise. This is the cost of the uncertainty term; its
effect on the player pool is measured in §6.5 (row "team swings, forward
filter").

### 4.2 Fitted constants and results

Fitted on 2014/15–2018/19, scored on 2019/20–2025/26 (SCORED_TEST_MATCHES scored
test matches). Log loss and Brier score: lower is better.

| Variant | Fit log loss | Test log loss | Test Brier |
|---|---|---|---|
| Plain Elo (baseline: K = 17, home advantage 40, fitted seeds) | 0.9757 | 0.9858 | 0.5870 |
| Elo + margin multiplier | 0.9740 | 0.9836 | 0.5855 |
| Elo with uncertainty + margin (process noise 6 per day, initial variance 400², home advantage 50) | 0.9724 | 0.9825 | 0.5847 |
| … + match importance by stage | 0.9720 | 0.9823 | 0.5846 |
| … + competition state (second legs) | 0.9724 | 0.9825 | 0.5848 |
| … + corners (tier 2) | 0.9709 | 0.9814 | 0.5840 |
| … + cards (tier 2) | 0.9723 | 0.9824 | 0.5847 |

The ordered logit's slope on the final candidate is 0.0052 per Elo point,
close to ln 10 ÷ 400 = 0.0058: the ratings sit on a genuine Elo scale.

**C2 (team prediction): pass.** The forward-only candidate (uncertainty,
margin and corners) beats plain Elo by **−0.0044 nats** of test log loss
(95% interval −0.0058 to −0.0031). With the hindsight correction the gap
widens (§4.4).

### 4.3 Match importance, competition state, and the shared scale

**Match importance and competition state are separate factors** in the code
(`stage_weights`, `competition_state`) and were fitted separately:

- **Importance by stage** (eight weights relative to league matches): test gain
  −0.0002 (interval −0.0005 to +0.0001). **Not adopted.** The fitted weights
  point *against* the Spec's intent: early cup rounds 0.5, late cup rounds,
  super cups and continental finals 0.25, continental knockouts 0.75. A cup
  tie against a lower-division side, often with a rotated eleven, and a
  single final say less about a team's strength than a league match, not more.
- **Competition state** for second legs: the first-leg margin is a head start
  worth `goalValue` points per goal; the chance the home side goes through is
  the expected score with that head start, and the weight is
  `stateFloor + (1 − stateFloor) × 4 × chance × (1 − chance)`: 1 for an open
  tie, `stateFloor` for a decided one. Fitted floor 0.75, 600 points per goal:
  test gain −0.000003 (interval −0.00007 to +0.00006). **Not adopted**: second
  legs of decided ties are too rare to matter to prediction. The mechanism is
  ready if the owner wants it as a rule of fairness rather than accuracy.
- League dead rubbers (end-of-season matches with nothing at stake) are **not
  modelled**: it needs a simulation of every league table. Open.

**A single shared scale.** All leagues sit in one pool from the first day, and
the bridge competitions (every UEFA round from the first qualifier, the
Club World Cup) are the only matches that move one league against another.
The importance fit is telling here: continental qualifying (1.25) and group
matches (1.5) and the Club World Cup (3.0) came out *above* league matches.
That is not importance; it is the bridge doing its job, because those are the
only matches that carry information about the gap between leagues, and the
model wants to learn it faster. A league-level rating (every team's rating as
a league offset plus its own, with bridge matches moving the offset of the
whole league at once) is the natural mechanism for that and is a proposal for
a later round (§9). §4.6 checks the scale against clubelo.

### 4.5 Tier-2 inputs

Both enter as a second, lower-weight observation inside the same Kalman step:
an observed share (the home side's share of the corners, or the away side's
share of the cards, where stronger sides' opponents collect more) whose
expected value is the expected score at a scaled rating difference. The scale
was fitted by least squares (corners 0.35, cards 0.25), the weight by the
objective (corners 4, cards 1).

| Input | Test gain over goals alone | 95% interval | On matches that have the data | Adopted? |
|---|---|---|---|---|
| Corner differential | −0.0011 | −0.0019 to −0.0004 | −0.0031 (22,373 matches) | **Yes**, narrowly: the rule asks for at least 0.001 |
| Team card totals | −0.0001 | −0.0003 to +0.0001 | −0.0005 | No |

Corners are a referee-awarded fact and pass the owner's line for inputs.
Their gain exists only where the provider supplies corners (domestic leagues
here); a match without corner data is rated on the result alone.
