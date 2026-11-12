# Player-model experiments (branch `communication`, 2026-11-12)

Working results after the owner review of 2026-11-12. `FINDINGS.md` is an
earlier draft and still describes the first candidate (hindsight correction and
corners, both since dropped); it is not updated yet.

Regenerate: `.venv/bin/python -I ingest.py --fetch`, `evaluate.py team`, then
`compare_variants.py` with the variants below (see its docstring). All runs are
floats; constants of the new terms are set by hand (`player_v2.py`), not fitted.

## Candidate

- **Team**: Elo with an uncertainty per team and the goal-difference
  multiplier, forward only. No hindsight correction, no corners.
- **Player base**: the team swing shared by minutes, a 5% pull per full match
  towards the team's rating, debutants at team − 50.
- **Data fix**: where the dataset lists a starter but no minutes, he is credited
  the full match (14% of player-seasons with 10+ starts had missing minutes).

## Measures

- Case gaps: player rating minus his team's rating.
- **C7**: share of substantial Transfermarkt moves (≥25%, ≥€5M) matched in
  direction over −6/+6 months. Higher is better.
- **Rank correlation**: Spearman between 12-month rating change and 12-month
  change in log Transfermarkt value, tracked players (4,561 pairs). Higher is
  better.

## 1. The four ideas alone

| Measure | Baseline | A persistent offset | B weighted offset | C bounded absence | D own-window selection |
|---|---|---|---|---|---|
| Rodri gap, Jan 25 / Jul 25 / Jan 26 | +137 / −167 / −152 | +159 / −136 / −76 | +101 / −182 / −121 | +54 / +18 / −51 | +105 / −170 / −140 |
| Wirtz worst gap in ACL injury | −228 | −238 | −244 | −85 | −241 |
| Isak / Wirtz change on moving to Liverpool | −97 / −80 | −100 / −74 | −100 / −74 | −94 / −82 | +35 / +38 |
| C7 set A / set B | 0.717 / 0.868 | 0.683 / 0.847 | 0.669 / 0.850 | 0.700 / 0.844 | 0.713 / 0.865 |
| Rank correlation | 0.461 | 0.435 | 0.439 | 0.439 | 0.479 |

## 2. Combinations

| Measure | C+D | A+C+D | B+C | All |
|---|---|---|---|---|
| Rodri gap, Jan 25 / Jul 25 / Jan 26 | +23 / +15 / −39 | +44 / +48 / +40 | +19 / −10 / −30 | −13 / −13 / −17 |
| Wirtz worst gap in injury | −96 | −121 | −120 | −132 |
| C7 set A / set B | 0.700 / 0.865 | 0.652 / 0.856 | 0.638 / 0.820 | 0.652 / 0.856 |
| Rank correlation | 0.442 | 0.418 | 0.414 | 0.417 |

Handling minutes (C, D) helps; the attempts at a persistent +/− (A, B) cost
agreement with Transfermarkt at these hand-set constants.

## 3. Minutes-share window (C+D, window over matches in the matchday squad)

| Measure | Team 38 | Squad 50 | Squad 100 | Squad 150 | Squad 200 |
|---|---|---|---|---|---|
| Rodri gap, Jan 25 / Jul 25 / Jan 26 | +23 / +15 / −39 | +122 / +159 / +68 | +123 / +167 / +78 | +124 / +170 / +86 | +120 / +168 / +87 |
| Wirtz worst gap in injury | −96 | +37 | +25 | +25 | +25 |
| Wirtz gap Jan 24 | +73 | +76 | +83 | +76 | +76 |
| Isak / Wirtz change on move | +38 / +36 | +29 / +47 | +36 / +39 | +35 / +40 | +37 / +43 |
| Kane mean gap 2016–23 | +71 | +101 | +98 | +92 | +88 |
| C7 set A / set B | 0.700 / 0.865 | 0.706 / 0.868 | 0.689 / **0.874** | 0.662 / 0.868 | 0.652 / 0.865 |
| Rank correlation | 0.442 | **0.504** | 0.480 | 0.462 | 0.453 |

Counting only matches he was in the squad keeps an injured regular's standing,
so injuries now cost little (Wirtz never drops below his team; Rodri keeps the
signal from City's collapse). A 50-match window gives the best rank
correlation of every variant tried; longer windows hurt set A (veterans keep
an old status too long).

## 4. National-team selection points (on squad 100)

Points for being a regular in a national team, never for its results:
`50 × minutes share over the last 10 call-ups in two years × strength`, with
strength flat (1), from the line-up's mean club rating (how stacked the squad
is: `(level − 1600) ÷ 200`), or from a national-team Elo built from tournament
results.

| Measure | Squad 100 | + NT flat | + NT clubs | + NT Elo |
|---|---|---|---|---|
| C7 set A / set B | 0.689 / 0.874 | 0.689 / 0.874 | 0.689 / 0.874 | 0.689 / 0.874 |
| Rank correlation | 0.480 | 0.480 | 0.480 | 0.480 |

**No measurable effect, for a data reason.** National-team line-ups exist only
for 2024–26 (Copa América 2024, Asian Cup 2024, AFCON 2025, World Cup 2026).
The points are real (in mid-2026 regulars of England, France and Spain get up
to +85 under the club-strength scheme, mean +11 over 1,714 players with 3+
call-ups) but Transfermarkt valuations end in June 2026, so no move can be
scored after them. The national-team Elo built from tournaments alone is
compressed (top team about 1,720) and gives almost nothing. Testing this needs
national line-ups for earlier years (for example StatsBomb's open data for the
2018 and 2022 World Cups and Euro 2020 and 2024).

## Open

- Whether an injury should cost as little as the squad-window variants make it.
- Fitting the new constants (absence cap, window length, selection scale)
  instead of setting them by hand.
- National-team data for earlier years.

## 5. National-team data for 2014–26 (`national.py`)

Line-ups added from open sources into separate `nt_*` tables, matched to
Transfermarkt ids: World Cups 2014/2018/2022 (jfjelstul/worldcup, minutes from
substitutions; 83% / 90% / 96% of listed players matched), Euro 2020/2024 and
AFCON 2023 (StatsBomb, exact minutes; 89% / 93% / 54%). The national-team Elo
now runs over every international since 1872 (martj42), K by tournament, so top
teams reach about 2,200 (Brazil 2,214, Argentina 2,210 before Qatar 2022) rather
than the 1,720 of the tournament-only version. Still missing: qualifiers and
friendlies line-ups, Euro 2016, Copa América before 2024.

On squad 100 / squad 50 (C+D):

| Measure | Squad 100 | + NT flat | + NT clubs | + NT Elo | Squad 50 | 50 + NT clubs | 50 + NT Elo |
|---|---|---|---|---|---|---|---|
| C7 set A / set B | 0.689 / 0.874 | 0.706 / 0.868 | 0.703 / 0.868 | 0.700 / 0.874 | 0.706 / 0.868 | **0.727 / 0.877** | 0.724 / 0.874 |
| Rank correlation | 0.480 | 0.490 | 0.488 | 0.469 | 0.504 | **0.509** | 0.489 |

A small gain from the club-strength scheme. The Elo scheme overshoots (Rodri
+289): its strength formula `(level − 1600) ÷ 200` was set for the compressed Elo
and needs a new scale.

## 6. Squad mean over the most used players

The squad average in the minutes bonus (`share − squad mean`) is now the mean
share of the N players with the most minutes in the window (`squad_top`), so it
no longer depends on how many fringe players the dataset lists. 50-match window,
club-strength national points:

| Measure | all | top 14 | top 16 | top 18 | top 20 | top 22 |
|---|---|---|---|---|---|---|
| Rank correlation | 0.509 | 0.507 | 0.508 | 0.509 | 0.509 | 0.510 |
| C7 set A / set B | 0.727 / 0.877 | 0.720 / 0.874 | 0.724 / 0.880 | 0.724 / 0.877 | 0.724 / 0.880 | 0.724 / 0.877 |
| Rodri gap Jul 25 | +227 | +172 | +179 | +186 | +193 | +199 |
| Kane mean gap 2016–23 | +130 | +76 | +84 | +91 | +99 | +106 |
| Wirtz worst gap in injury | +37 | −20 | −14 | −6 | +2 | +11 |

Agreement is unchanged, gaps shrink with N. Top 16 (starting eleven plus five
substitutes) is the choice. Smaller N raises the mean, so the 200 scale will
want to rise.

## 7. Team rating as a direct component (`direct`)

`rating = team rating after its last match + minutes bonus + national points`:
no personal level, no pull, no debutant offset. A transfer moves the rating by
the difference between the clubs.

| Measure | Current (level) | Direct |
|---|---|---|
| Rank correlation | 0.508 | 0.432 |
| C7 set A / set B | 0.724 / 0.880 | 0.683 / 0.853 |
| Isak / Wirtz change on moving | +19 / +34 | +168 / +95 |
| Rodri gap Jul 25 | +179 | +65 |

Direct fixes squad players that were far too low (Bayern: Bischof −205 → −51,
Urbig −183 → −49) at the cost of agreement. Decision (owner): keep direct, the
jump at a transfer is accepted; the target is that the rating leads or catches up
with Transfermarkt directionally, not that it matches its size. Olise: rating
+121 by July 2024 and +226 at the move to Bayern while his value was still
€55M, then Transfermarkt climbs to €140M as the rating keeps rising.

## 8. Age-adjusted Transfermarkt values (evaluation only)

Transfermarkt values include age (remaining career); the rating has none (age
is to be added separately later). So the comparison can be run against values
restated at the age-25 level: `OPENELO_TM_AGE_ADJUST=1` makes `store.valuations()`
divide every value by the typical drift of value with age (mean 12-month log
change by age over all valued players, summed outwards from 25; relative value
0.89 at 24, 1.06 at 26, 0.77 at 30, 0.42 at 32). Ratings never see it.

| Measure | Current, raw | Current, adjusted | Direct, raw | Direct, adjusted | Direct, no NT, adjusted |
|---|---|---|---|---|---|
| Rank correlation | 0.508 | 0.406 | 0.432 | 0.353 | 0.343 |
| C7 set A / set B | 0.724 / 0.880 | 0.687 / 0.797 | 0.683 / 0.853 | 0.668 / 0.783 | 0.629 / 0.776 |

- Bruno's divergence is age: his raw value falls €90M → €40M (2021–26) while his
  rating is flat; adjusted, his value is flat at about €75–85M.
- All agreement falls on the adjusted values, so part of the earlier agreement was
  both rising for young players and falling for old. The gap between direct and
  current narrows (rank correlation −0.076 raw, −0.053 adjusted).
- Caveat: the average curve also removes the average real change in ability with
  age (growth at 20, decline at 32), which results-based ratings should
  partly capture; and players who stop being valued drop out of the curve, so
  the decline at old ages is understated.

## Current candidate

Team Elo with uncertainty (forward only); player rating = team rating + 200 ×
(share in own 50-match squad window − mean share of the squad's 16 most used
players) + club-strength national-team points (scale 50); bounded absence
discount; minutes filled for starters without them. Constants hand-set, not
fitted.
