# ADR-0018: Rating calculation in rating-service

- **Status**: Proposed, not yet implemented. Each item is marked decided,
  proposed or open. Amends ADR-0001's service table: rating-service is Java,
  not "may later be Python".
- **Date**: 2026-11-12

## Context

Phase 1 (`research/FINDINGS.md`) chose and validated the formula on 14 seasons
of public data, and wrote an exact integer reference (`research/exact.py`). This
ADR places that formula in `rating-service`: the tables it reads and writes,
how a published number is made reproducible, how often numbers are published,
and how other services read them.

ADR-0001 gives rating-service the catalog (players, teams, competitions,
matches) and the rating snapshots, consuming `match.completed` from
ingestion-service (ADR-0017) and publishing `rating.snapshot.published` to
dividend-service and market-service.

The hindsight correction makes one distinction central. **A rating for a past
date, computed later with more matches known, is a different number from the
one published on that date.** Every design choice below follows from keeping
"what was published" and "what we would say now" apart.

## Decision

### Decided

1. **Java and Spring Boot**, like `market-service`; `research/` stays Python.
   The formula is ported once, and a parity test checks the port bit for bit
   against the Python reference (decision 7). This amends ADR-0001's "may
   later be Python".
2. **Exact integer arithmetic**, the same rule as money: fixed-point integers,
   one stated rounding rule, `Math.*Exact` for every business operation. The
   units and the rounding rule are those of `research/exact.py` (FINDINGS.md
   §6).
3. **Application-layer logic.** The computation reads match facts and writes
   snapshot rows. No stored procedures (Spec §5).
4. **Consumes `match.completed` idempotently** (deduplicated by event id,
   ADR-0001 decision 4) and **publishes `rating.snapshot.published`** through a
   transactional outbox.
5. **Opponent strength is corrected in hindsight; published snapshots never
   change.** A correction moves the current rating like a new match does and
   leaves past payouts alone.
6. **Dividends settle against an explicitly referenced snapshot id**, never
   "the latest" (ADR-0001).

### Proposed

7. **Parity fixture.** The Java test suite reads a fixture of match facts and
   the integer reference's expected outputs (team and player ratings at every
   snapshot, and the conservation ledger) and requires equality to the last
   milli-Elo. It cannot be cut from the research data: that is scraped, and
   the repository is public (FINDINGS.md §3.4). So it is **generated**: a
   seeded generator in `research/` writes a few seasons of synthetic matches
   that exercise every branch (new teams, second legs, extra time, shoot-outs,
   corners present and missing, transfers, long inactivity, national-team
   matches, a team at the edge of the expected-score table, the largest
   variances), runs `exact.py` on them, and writes both to
   `services/rating-service/src/test/resources/parity/`. Synthetic data is
   fine here: parity tests the arithmetic, not the model. The generator's seed
   and the expected-score table's hash are part of the fixture, so a changed
   table fails loudly. A second check runs the reference on real licensed data
   in CI where the licence allows it, outside git.

8. **The catalog, fully normalised.** No nullable column; an optional fact is
   its own table; enums are Postgres native types; ids are UUID v7 and never
   carry time order; facts are append-only.

   | Table | Holds | Notes |
   |---|---|---|
   | `competitions` | id, `created_at`, name, kind | kind: `DOMESTIC_LEAGUE`, `DOMESTIC_CUP`, `SUPER_CUP`, `CONTINENTAL`, `CLUB_WORLD_CUP`, `NATIONAL_TEAM` |
   | `teams` | id, `created_at`, name, kind | kind: `CLUB`, `NATIONAL` |
   | `players` | id, `created_at`, name | |
   | `player_positions` | player, position group, `recorded_at` | optional and changeable, so its own timestamped rows (ADR-0006 proposal); read only by the display layer (decision 15) |
   | `competition_sources`, `team_sources`, `player_sources`, `match_sources` | catalog id, source (enum), source id | unique (source, source id); the mapping ADR-0017 open point 2 recommends keeping here |
   | `matches` | id, `created_at`, competition, season, stage, home team, away team, kick-off | the match's identity |
   | `match_facts` | id, match, version, `known_at`, venue, result kind, home goals, away goals, extra time | unique (match, version); one row per `match.completed` version |
   | `second_legs` | match, first-leg match | optional relationship, its own table |
   | `shootouts` | match fact | presence means the tie was decided on penalties |
   | `match_corners` | match fact, home corners, away corners | optional: only when the provider had them |
   | `appearances` | match fact, player, side, started, minutes | primary key (match fact, player) |
   | `rating_versions` | id, `created_at`, name, constants document, expected-score table hash | the formula and constants; never edited (decision 10) |
   | `snapshots` | id, `created_at`, rating version, as-of date, knowledge cutoff, kind | kind: `PROVISIONAL` or `SETTLING`; unique (version, as-of date, cutoff) |
   | `snapshot_team_ratings` | snapshot, team, rating (milli-Elo) | |
   | `snapshot_player_ratings` | snapshot, player, rating (milli-Elo) | |
   | `consumed_events`, `outbox_events`, `relayed_events` | idempotent inbox and the outbox | as ADR-0017 |

   A player's current team, minutes share, decay state and so on are not
   stored: they follow from `appearances` and are recomputed by every replay.

9. **A settling snapshot is a stored fact; everything else is derived.**
   ADR-0006's test asks whether a value can be recomputed from stored facts and
   rules. A snapshot's numbers can: they are a function of the facts known at
   its cutoff (`known_at` ≤ cutoff), the rating version and the as-of date. But
   the hindsight correction means "the facts known at the cutoff" is not "all
   facts", so the inputs must be selected by `known_at`, which is why every
   fact carries it (ADR-0017 decision 9). Two arguments make the settling
   snapshot a fact anyway:
   - **It records an event.** Publishing a number that money then settles
     against is something that happened. If a bug were later found in the
     formula, recomputing would give a different number, and the payout was
     still made on the old one. Like a posting, the published value is the
     record; the recomputation is the audit.
   - **Spec §2 already requires it**: a version that settled money is frozen
     and archived, so the record is never re-derived with new code.

   So `snapshots` and their rating rows are append-only facts, and a
   reconciliation job (ADR-0005's pattern) replays each settling snapshot from
   the facts known at its cutoff with its archived version, and alerts on any
   difference. Provisional ratings are a cache in the sense of ADR-0006
   decision 4: rebuildable at any time, never referenced by money.

10. **Versions are frozen once they settle money.** A new fit of the constants
    is a new `rating_versions` row, announced in advance like a fee change;
    it never refits against open positions (Spec §2). Old versions stay in the
    table, and the code for each version stays buildable (a version id maps to
    a released artifact).

11. **Determinism and replay.** The computation for as-of date D, with
    knowledge cutoff K, is:
    1. select the match facts with `known_at` ≤ K, taking each match's highest
       version, and dropping `ABANDONED` and `AWARDED` results;
    2. order them by match date, then by catalog match id, and treat each date
       as one batch (FINDINGS.md §6.4): arrival order from Kafka never matters;
    3. run the forward filter, then the hindsight replay with the version's lag
       and iteration count, as of every match day up to D;
    4. run the player model over the same days, with the replay's swings;
    5. write the team and player ratings as of the start of D.

    The same function serves the live rating (D = today, K = now) and the
    audit of a settling snapshot (its own D and K). A late or out-of-order
    `match.completed` only means the next run starts its replay window from
    an earlier day; nothing is updated in place.

12. **The formula** is FINDINGS.md §6, summarised:
    - **Team step**, per observation (the result, then corners when known):

      ```
      expected   = expectedScore(scale × ratingDifference)     table, linear between whole points
      surprise   = observed − expected
      spread     = expected × (1 − expected)
      load       = weight × slope² × spread × variance          one per side
      gain       = variance × slope × weight ÷ (1 + loadHome + loadAway)
      swing      = gain × surprise
      variance'  = variance × (1 + loadOther) ÷ (1 + loadHome + loadAway)
      ```

      with `slope = ln 10 ÷ 400 × scale`, `weight` the margin multiplier for
      the result and a fixed weight for corners, and each team's variance
      grown by the process noise for every idle day, capped at the initial
      variance.
    - **Hindsight replay**: a backward pass per team folds its later matches
      into an information-form estimate (precision = 1 ÷ variance), adding the
      process noise per day crossed; each opponent enters a match at its cavity
      (forward estimate before the match combined with the backward
      information after it); every team is re-run forward against those
      cavities. Matches older than the lag are settled for good.
    - **Players**: per match, `minutesShare × teamSwing` (rounded once per
      side and shared by largest remainder) plus
      `minutesShare × anchorRate × (teamRatingBefore − playerRating)`; the
      published rating adds a minutes bonus that sums to zero within a squad.
      Debutants start at their team's rating less an offset; a player inactive
      beyond the grace period decays linearly to the replacement level.
      National-team matches attribute the surprise against the line-ups'
      club-derived strength by minutes.

13. **Corrections and hindsight are one mechanism.** A provider correction is
    a new fact version with a later `known_at`; the hindsight correction is
    later matches arriving. Both are handled by decision 11: recompute as of
    now from the facts known now, write a new snapshot, keep every old one.
    There is no correction path of its own.

14. **Lifecycle steps**, all inside the replay of decision 11, in date order:
    - **seeding**: a player's first appearance creates his rating at his
      team's rating before the match, less the debutant offset; a team's first
      match creates its rating at the mean of the league it enters less an
      offset (or the pool's mean less a larger one outside a covered league);
    - **inactivity decay**: on a snapshot date, or at his next appearance, a
      player whose last appearance is older than the grace period is moved
      along the straight line to the replacement level;
    - **national-team calibration**: a national-team match with at least 60%
      of both line-ups' minutes rated feeds back as described in decision 12.

15. **Consumers read events, not rating-service.** `rating.snapshot.published`
    announces a snapshot: id, rating version, as-of date, cutoff, kind, the
    number of rows and a hash of them. The rows themselves follow as
    `rating.snapshot.rows` events in chunks (about 30,000 players do not fit
    one Kafka message comfortably), each carrying the snapshot id. A consumer
    stores the rows, checks count and hash, and only then treats the snapshot
    as available. dividend-service builds its payout plan from a settling
    snapshot it holds locally and names that snapshot id in
    `dividend.payout.requested`. market-service keeps a local read model of
    provisional ratings for display and listing. **This replaces the
    `RatingProvider` mock the Spec mentions, which was never built**: in
    market-service the local read model is the provider, and its tests load a
    fixture snapshot. No service calls rating-service synchronously in the
    money path.

16. **Positions stay out of the number.** The rating is the same formula for
    every player. Any comparison across positions (a percentile within a
    position group) is a separate read model, built from `player_positions`
    and the snapshot rows.

## Consequences

+ Every settling number has a stored record and a reproducible derivation; the
  reconciliation job turns "anyone can recompute it" into a checked property.
+ Late data, out-of-order delivery, provider corrections and the hindsight
  correction all take one path.
+ The Java port is held to the Python reference by a test that needs no
  scraped data in git.
+ Consumers settle against a local, verified copy of a snapshot, so a
  rating-service outage cannot stop or alter a payout.
  − Each run replays the lag window every day, and the hindsight replay with
  iterations is the costliest step (Phase 1: minutes per day of data in
  Python; a Java port should be well under a second per day).
  − Snapshot rows grow linearly: about 30,000 players per snapshot. Monthly
  settling snapshots plus daily provisional ones is about 11 M rows a year;
  provisional rows can be pruned because they are a cache.
  − A rating version can never be "fixed" once it has settled money; a bug
  fix is a new version, announced in advance.
  − Kafka, an `ingestion` and a `rating` database are needed before any of
  this runs (open point 6).

## Alternatives considered

- **Python rating-service reusing `research/`**: one implementation, no port.
  Rejected by the owner: one stack, and the money rule (exact integers, the
  same conventions as `market-service`) is easier to enforce in Java. The
  parity test keeps the two from drifting.
- **Snapshots as a view over facts**: no stored copy, strictly normalised. But
  a view recomputes with today's code; a bug fix would silently change a number
  money settled on. Kept only for provisional ratings.
- **Updating ratings in place per match** (a `players.rating` column): simplest
  reads, but it cannot answer "as known on date D", and the hindsight
  correction rewrites past swings, which an in-place running total cannot
  express.
- **Separate correction events and handlers**: rejected in decision 13; one
  replay covers every reason a number changes.
- **One message per snapshot**: simpler, but large; chunks with a final count
  and hash keep messages small and make completeness checkable.

## Open points

1. **Snapshot cadence and the delayed freeze.** Options:
   (a) a settling snapshot frozen immediately at the end of each dividend
   period; (b) a provisional rating after every match day for display only,
   and the settling snapshot for period end D computed and frozen at D + W,
   after W more weeks of matches have corrected the opponents of the period's
   matches (the owner's example: the end of September frozen at the end of
   October settles the October dividend); (c) per match or per matchday
   settling snapshots. **Recommendation: (b)**, with W chosen from Phase 1's
   revision curve (FINDINGS.md §4.4: how much a date's rating still moves per
   extra week): the freeze can come well before the replay's lag, once the
   expected remaining revision is small. What (b) implies:
   - **Record date**: the holder at the end of D receives the dividend for the
     period; the payment happens at D + W. A share sold between D and D + W
     carries no claim on that dividend (an ex-dividend date at D, as for
     equities).
   - **Display**: the app shows the live provisional rating and, separately,
     the last frozen settling rating; holders see the provisional number move
     on days their player did not play (FINDINGS.md §4.4 measures how much).
   - **Longer W** means more accurate settling numbers and later payments.
2. **The split rule and the zero of the scale.** The dividend split is
   dividend-service's design, but the formula fixes only rating differences;
   the level comes from the seed (1500) and drifts with entries and exits.
   FINDINGS.md §6.6 measures how much a split proportional to the level depends
   on where zero sits, against splits by standing in the pool. That result
   should decide whether the split uses the level at all before
   dividend-service is designed.
3. **Match importance as a value judgment.** Phase 1 found no predictive gain
   from weighting by stage, and the fitted weights favoured finals *less*
   (FINDINGS.md §4.3). The Spec wants decisive high-stakes matches rewarded.
   Whether to set stage weights by declaration, accepting a measured
   predictive cost, is a decision for the owner; the integer form supports it
   with one more constant per stage.
4. **National-team coverage.** Line-ups exist in the research data only for
   2024–2026, so the calibration is barely tested. The licensed provider's
   national-team coverage (qualifiers, Nations League, friendlies) decides how
   much separating information this source really gives.
5. **The constants' governance**: who may publish a new rating version, the
   notice period, and how users are told.
6. **Infrastructure prerequisites**, not added here: Kafka in
   `infra/compose.yml`; `rating` and `ingestion` databases (one Postgres
   instance with three databases is enough locally).
