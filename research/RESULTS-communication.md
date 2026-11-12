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
