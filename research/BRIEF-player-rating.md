# Player rating: brief (2026-11-26)

Research only. Everything here runs offline on the research store (`research/data/raw`), data to
**24 November 2026** (transfermarkt-datasets to 6 July 2026 plus the scraped `data/transfermarkt-recent`
matches, research use only). Transfermarkt values stop at June 2026, clubelo at June 2025, international
results at 6 October 2026. Scripts are in `research/adhoc/`; pages were published as private artifacts.

## Goal

The rating says **how good a player is right now, as professionals judge him**. Age and potential are left
to the market. Each term stands for one professional judgement, corrected for its known biases:

| Term | Whose judgement |
|---|---|
| Club rating | recruiters: what level of club employs him (and how that club is performing) |
| Minutes | his coach: how much he is trusted, above all in the matches that matter |
| Goals and assists | output that separates players the coach trusts equally (the very top) |
| National term | national coaches: the only judgement that compares players across clubs |

Two rules sit above everything:
- **No systematic mispricing by group.** The rating sets dividends; a whole class of player rated too high or
  too low is a mispricing traders will exploit. Random misses inside a group are acceptable. A change that only
  moves errors from one group to another is not a fix.
- **Interpretability.** No new term for a small gain; every term must be explainable in one sentence.

Owner's principles carried throughout: measure, do not judge (non-selection is data, measured naturally);
position never enters the rating except the goalkeeper reference; no plus-minus; transfers count at once
through the club term; minutes are scaled by where they were earned; not playing is always punished in
principle (how to punish injury is still open).

## The candidate (pushed in `research/candidate.py`)

```
rating = 0.7 × club rating            team Elo, league redistribution of European results 0.3 zero-sum
       + minutes bonus                400 × weighted average over his last 50 matchday squads of
                                      (his share of the match − the top-16 players' share of that match)
       + goals and assists            119 per goal and 59 per assist per 90 (prior 5 × 90),
                                      each weighted by opposition strength (centred on the average goal)
       + national term                100 × mean over his nation's last 20 covered matches in 2 years of
                                      (his share, unused in the squad 0.2) × strength from national-team Elo
```

- **Match weights in the minutes bonus:** Champions League 4, knockouts and final 8; domestic league 4 for
  the strongest league by average club rating (England), then 3 (Spain), 2 (Italy), 1 for every other league;
  everything else 1; times opponent strength (2 × the team's chance of not winning).
- **Minutes earned at another club** are rescaled by 2^((that club − current club) ÷ 400).
- **Internationals missed while injured count for neither side:** out of his club's squad for the club matches
  just before and after (within 21 days), or he played earlier in that international window and then left the
  squad. Otherwise an international he missed while playing for his club counts as rotation (0).
- **No absence term.** Matches out of the club squad are not counted at all (open question below).
- Code: `candidate_team_constants()`, `CANDIDATE_PLAYER`, `candidate_context()` in `research/candidate.py`;
  comparison against the live formula in `adhoc/live_vs_candidate.py` and `adhoc/world_top100.py`.

## Decisions and their effect, in order

| # | Decision | Effect seen | Status |
|---|---|---|---|
| 1 | National-team selection as the main check (who makes each squad, per nation) | Club + coach terms predict squads at 0.87–0.88 AUC; club alone 0.82–0.84; Transfermarkt 0.91–0.92 | Kept as a check, not a target |
| 2 | Pecking order (rank) instead of minutes share | Same accuracy as share; a rank bucket tied every regular (my error) | Dropped; continuous share kept |
| 3 | Per-group calibration | Fit fringe players at top clubs overrated; regulars at clubs 11–40 overrated (the bigger error, after a bug fix) | Principle kept |
| 4 | Signals that separate fringe players | Continental starts (0.80 AUC inside the group), longer memory, coming on vs unused | Led to importance weighting |
| 5 | Underrated groups | Second-tier European leagues overrated by about a third (−219 squad places); top-5 and Americas underrated | Led to the league fix |
| 6 | League redistribution of European results, 0.3 zero-sum | Gap to clubelo: England −40 → −17, Portugal +59 → +19, Germany +63 → +8; team log loss slightly better (0.9813 → 0.9797) | Kept |
| 7 | Slow seasonal club Elo (recruitment level) | Almost no change (Bayern −36, others 0–19) | Not adopted |
| 8 | Minutes scaled by the club where earned, relative to current club | Semenyo and Guéhi lose bonus from old minutes; centring on the market average stretched the top (Kane 2674) | Kept, relative version |
| 9 | Goals weighted by opposition (D400, centred) | Champions League scorers up, Liga Portugal scorers down; also moved weight to top-club attackers | Kept |
| 10 | Goals by own club | Doubled club level (Saliba 34th) | Rejected |
| 11 | Goals and assists cut (−30%, then −25%) | Proportions back near the old candidate | Kept at −25% |
| 12 | Assists | Out lifted the tier-2 defenders/midfielders; in lifted Olise and Bellingham; assists repeat year to year at 0.61 against 0.79 for goals | Back in at half a goal |
| 13 | Absence term | Counted PSG-style rotation omissions as absence; injured players rose when dropped (Havertz, Musiala) | Dropped; injury open |
| 14 | Window over all club matches (missed = 0), windows 30/50/80 | Window 80 nearly matched the two-term version (TM 0.825 vs 0.830) | Not adopted yet |
| 15 | Champions League 4, leagues 4-3-2-1 | Small moves at first: a bug ignored match weights when minutes were rescaled by club; after the fix PSG's European starters rose | Kept |
| 16 | Top-5 reference | Cancelled full regulars at star clubs (Bellingham ≈ 0) | Replaced |
| 17 | Weighted reference, then top-10 | Moved whole clubs, never the order inside a club | Superseded |
| 18 | Champions League knockouts 8 | Neves started all 8 PSG knockouts; agreement with the owner's PSG order 0.60 → 0.70 | Kept |
| 19 | Per-match reference | Missed matches drop out of both sides; Mbappé, Bellingham, Havertz up | Kept |
| 20 | National strength: club ratings → player ratings → national Elo | Player-rating strength barely changed the table; national Elo lifted Spain/Argentina/Colombia, removed Bayern double count | National Elo kept |
| 21 | National strength doubled (scale 200) | Rewarded strong-nation regulars; TM 0.824 → 0.808 | Rejected |
| 22 | Three-year national window | Two-year-old non-selection dragged new internationals (Vitinha 159 → 60) | Rejected |
| 23 | Injury-aware internationals | Mbappé's three injured Nations League matches no longer count; he moved above Vinícius | Kept |
| 24 | Goal pot set by club Elo, paid by players below the squad median | Did what was asked (Bayern defenders pay, Arsenal defenders gain) | Not adopted: overfitting risk |
| 25 | Club zero-sum of goal and national bonuses by minutes | Regulars paid for team-mates; injured players shot up | Rejected |
| 26 | Data refresh to 24 November 2026 | 1,296 matches, Nations League and qualifiers, 2026–27 transfers | Done |

## What failed and why

- **Rank buckets for pecking order:** ranks 1–6 all got the maximum, so every regular tied. A continuous share
  was needed.
- **The stand-alone formula:** built to test pieces against national-team selection, then shown as a rating.
  It had no squad reference and only positive terms, so academy players sat just under their club and the top
  stretched. The tested pieces went into `player_v2` instead.
- **A national term three times the decided size** in that stand-alone formula, which inflated German players.
- **Rank among candidates instead of the full squad** in the selection checks (bug): fringe players looked
  higher in the order than they were.
- **Weights ignored with minutes rescaled by club** (bug): importance weighting did nothing in several tables.
- **Injury check spanning the summer break** (bug): Saliba lost all his World Cup credit (national 0).
- **Absence counted as missed squads**: rotation by squad omission (PSG) was punished as absence; without it,
  injured players were not punished at all.
- **Club-level references (top-5, weighted, top-10)**: a reference is one number per club per match, so it can
  only move whole clubs; within-club order is set by the player's own share, goals and national term.
- **Goal pot by minutes**: scorers paid too; by non-scorers, PSG midfielders paid for Dembélé. Fixable, but
  each fix was chosen while looking at the players it moved.
- **Slow club Elo**: Sporting is high all year round; smoothing results does not measure recruitment power.

## Owner's target lists (2026-27 squads)

Rough tiers given earlier: **Kane, Olise, Haaland, Díaz, Dembélé**; then **Rice, Saliba, João Neves, Nuno
Mendes, Hakimi, Gabriel**; then Rodri, Kimmich and others.

Combined order (2026-27):
1. Kane, Olise, Yamal, Bellingham, Haaland
2. Rice, João Neves, Vitinha, Saliba, Gabriel, Güler, Fermín, Kvaratskhelia, Doué, Cubarsí, Pedri, Rodri,
   Courtois, Dembélé, Nuno Mendes, Hakimi, Luis Díaz, Diomande, Valverde, Cucurella, Bernardo Silva, Vinícius,
   Enzo Fernández

By club:
- **Bayern:** Kane, Olise | Díaz, Upamecano, Kimmich
- **PSG:** João Neves, Vitinha | Kvaratskhelia, Doué, Dembélé, Nuno Mendes, Hakimi, Fabián Ruiz, Pacho, Ferran
- **PSG with reasons:** Dembélé (Champions League minutes, national, goals), Neves (CL minutes, national),
  Vitinha (CL minutes, national), Kvaratskhelia (CL minutes, goals), Doué (minutes, national), Mendes (CL
  minutes, national), Hakimi (CL minutes, goals), Fabián (CL minutes, national), Pacho, Ferran
- **Barcelona:** Yamal, Raphinha | Fermín, Cubarsí, Pedri, Rodri, Joan García, Gordon, Koundé, Olmo
- **Real Madrid:** Bellingham, Mbappé | Güler | Courtois, Diomande, Valverde, Cucurella, Bernardo Silva,
  Vinícius, Tchouaméni, Endrick, Konaté, Huijsen
- **Arsenal:** Rice | Saliba, Gabriel | Raya | Gyökeres, Saka, Calafiori, Ødegaard, Bruno Guimarães, Konsa,
  Timber, Tzolis, Madueke
- **Man City:** Haaland | Cherki | Enzo Fernández, Elliot Anderson, Doku, Guéhi, O'Reilly, Semenyo,
  Donnarumma, Gvardiol
- **Sporting:** Altimira, Suárez | Maxi Araújo, Doumbia, Fresneda, Irankunda, Geny Catamo, Zalazar

## Transfermarkt order of the owner's players (June 2026 values, €m)

Haaland 200, Yamal 200, Mbappé 180, Olise 150, Pedri 150, João Neves 140, Vinícius 140, Kvaratskhelia 140,
Vitinha 140, Bellingham 130, Doué 120, Rice 120, Saka 110, Dembélé 100, Saliba 100, Fermín 100,
Enzo Fernández 90, Cherki 90, Valverde 90, Güler 90, Pacho 80, Nuno Mendes 80, Hakimi 80, Cubarsí 80,
Semenyo 80, Elliot Anderson 75, Gabriel 75, Doku 75, Guéhi 70, Upamecano 70, Díaz 70, Bruno Guimarães 70,
O'Reilly 70, Tchouaméni 70, Timber 70, Raphinha 70, Ødegaard 65, Gyökeres 65, Gordon 65, Kane 60, Koundé 60,
Olmo 60, Huijsen 60, Calafiori 55, Rodri 50, Madueke 50, Cucurella 50, Ferran 50, Donnarumma 45, Konaté 45,
Joan García 45, Diomande 42, Konsa 40, Endrick 40, Tzolis 40, Kimmich 35, Maxi Araújo 35, Fabián Ruiz 30,
Zalazar 30, Suárez 30, Raya 30, Geny Catamo 25, Bernardo Silva 22, Altimira 20, Fresneda 15, Courtois 15,
Doumbia 9, Irankunda 8.

## Results with the candidate (25 November 2026)

World top 25 (players of the 25 strongest clubs): Kane, Yamal, Dembélé, Olise, Mbappé, Raphinha, Haaland,
Vinícius, Díaz, Doué, Enzo Fernández, Julián Álvarez, Fabián Ruiz, Cubarsí, Rodri, Saka, Cucurella, Valverde,
Bellingham, Vitinha, Upamecano, Rice, Gabriel, Mac Allister, Bruno Guimarães (before the summer-break fix;
Saliba moves from about 107th to about 60th with it).

Against the live site's formula (OpenElo beta 0.1, `pipeline/rate.py`) on the same players: rank correlation
0.92; agreement with Transfermarkt 0.67 live against 0.71 candidate. The live formula overrates Bayern's squad
(Kimmich 6th, Saibari 8th, Brown 13th) and underrates PSG and City (Dembélé 28th, Haaland 25th).

Agreement with the owner's PSG order: 0.47–0.70 depending on version (best with knockouts ×8, before the
international-window rule moved Fabián Ruiz above Vitinha).

## Open questions

1. **Injury.** Not playing should always cost something, but matches out of the squad are currently free.
   Options: the window over all club matches (missed = 0, window 80); a time-based window; a mild, recovering
   availability term.
2. **Rotation by squad omission:** proposed rule 2+ in a row out of the squad = injured, 1 = rotation (0),
   bench = not picked; threshold 2 vs 4 untested.
3. **Knockout samples are small** (4–8 a season) and weigh 8× (12–16× with opponent strength).
4. **Friendlies count as much as competitive internationals.**
5. **Goal pot / attackers vs defenders by team style**: works, overfitting risk; needs an out-of-sample check.
6. **South American clubs are rated about 1440** (Flamengo, Palmeiras), hundreds below comparable European
   clubs; affects every home-based player and national squads.
7. **National-team coverage:** only the top-ranked nations were scraped (Georgia missing, so Kvaratskhelia gets
   no national credit); international results stop at 6 October 2026.
8. **Rolling the national window back** past injured matches (currently it shrinks instead).
9. **Out-of-sample checks not yet run on the full candidate:** national-team selection per group, and
   next-year Transfermarkt change.

## Opinions (mine, stated as opinions)

- I think the candidate is clearly better than the live formula at the top: its top 10 is the world-class
  attackers, and it no longer inflates whole squads at dominant clubs.
- I think national-team Elo is the right nation strength: it adds information the club term does not have.
  It does move some of the owner's tier 2 down (Rice, Neves).
- I think the goal pot is the change most at risk of overfitting; I would not adopt it without the
  out-of-sample checks.
- I think the window over all club matches (missed = 0) is the cleanest answer to injury and rotation in one
  rule, and worth revisiting before the next release.
- I think João Neves at 2nd in PSG cannot come from the data we have: he is a rotation player for club and
  country in this window except in Champions League knockouts. Ranking him higher needs a signal we do not
  measure.
- I think the Transfermarkt gap (0.91 against 0.88 on selection) is mostly national-team history and
  potential, which Transfermarkt prices and we leave out on purpose.

## Summary

The rating now measures four professional judgements: club level (with European results shared across
leagues), the coach's trust weighted towards the big matches and compared match by match, goals and assists
weighted by opposition, and national selection weighted by the national team's own Elo with injuries left out.
It puts Kane, Yamal, Dembélé, Olise, Mbappé, Raphinha, Haaland, Vinícius, Díaz and Doué on top, agrees with
Transfermarkt slightly better than the live formula, and fixes the Bayern inflation and the PSG/City
underrating of the live site. The main open problem is injury, which is currently free in the club term.
Before it replaces the live formula: settle injury, run the national-team selection check per group and the
next-year Transfermarkt check on the full candidate, and rerun the world top 100 with the summer-break fix.
