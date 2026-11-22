# Next steps (agreed with the owner, 2026-11-12)

Working list for the direct player model (`rating = team rating + minutes bonus +
national-team term − absence`) and the team Elo. Each item is a light test
(`fit_light.py`, about a minute) shown to the owner before the next decision.

## Queued

1. **Minutes rule and keepers.** Variants at club 400 / NT 50:
   A current (minutes); B starters credited the full match, substitutes their
   minutes, keepers against a reference share of 1.0 (first choice gets 0);
   C starters full, substitutes a fixed 0.25, keeper rule; D as B without the
   keeper rule. Same starter rule for national-team call-ups. Keep the computed
   top-16 squad mean. Report the Transfermarkt scores, the case gaps and a
   **plot of the mean minutes bonus of regulars by position** (keeper, defender,
   midfielder, attacker) before and after.
2. **Lower team K** (e.g. 15 and 10 against the fitted value): does the preferred
   minutes scale come back down, and what does the team log loss lose? One team
   rating is used for clubs and players (no separate smoothed copy).
3. **League share of European results** (tested, see below): keep at about 0.3;
   check pool drift (the shares are not zero-sum across leagues of different
   sizes) and a zero-sum version; refit K with it.
4. **National teams (decided, `nt_matches` mode).** Points only ever added: over
   the nation's last 20 covered matches, none older than two years, each match is
   worth his minutes share (0 if not selected, at least 0.2 if in the squad) ×
   strength, divided by the number of matches. Strength = the squad's average club
   rating without him (sum once per match, subtract his own). Scale 100. Not being
   selected is measured, never deducted: the others gain and he does not. The
   two-year cap only matters while the data is tournaments only.
   **Open:** a bigger bonus for a player at a weaker club, measured rather than
   judged (see the relative-club term proposal).
5. **Big-game trust** (separating regulars): weight each club match in the
   minutes share by the opponent's strength, so rotation in easy matches counts
   less. Check whether it reorders the top of squads (Bayern, City, Arsenal).
6. **Bookmaker benchmark** for the team Elo (Bet365 odds on 50,441 matches): log
   loss gap overall, by league and by month of the season. Deferred by the owner
   as too much for this stage. Note: the overall comparison is already coded
   (`evaluate.py benchmarks`, with clubelo too); only the breakdowns are new. An
   ordering benchmark against Opta's power rankings was suggested instead; Opta is
   not reachable from here and is proprietary, while clubelo (open, in the store
   until June 2025) is the ordering reference already used.
7. **Rotated line-ups in the team Elo**: weight each match's update by how many
   regulars started (also covers dead rubbers without simulating tables).

## Results so far

**Minutes rule and keepers (item 1).** National rule as decided (20 matches, two
years, credit 0.2, scale 100), club scale 400. Squad mean measured with the same
rule as the player.

| Variant | C7 A / B | Rank fit / held-out |
|---|---|---|
| A minutes | 0.697 / 0.882 | 0.476 / 0.409 |
| B starts full, subs minutes, keeper reference 1.0 | 0.684 / 0.882 | 0.481 / 0.410 |
| C starts full, subs 0.25, keeper reference 1.0 | 0.684 / 0.885 | 0.477 / 0.407 |
| D starts full, subs minutes, no keeper rule | 0.681 / 0.885 | 0.481 / 0.407 |

Mean minutes bonus of top-5-league regulars (keepers / defenders / midfielders /
attackers): A 108 / 85 / 71 / 58; B −58 / 81 / 77 / 71; D 90 / 81 / 77 / 71. The
start rule closes most of the defender-attacker gap (27 → 10). Open: with the
keeper reference at 1.0 a regular first-choice keeper averages −58, because cup
keepers and rotation keep his share near 0.85 (Raya 2208 → 2034, Verbruggen
2120 → 1957).


**Items 3, 5, 7 (process noise 3, decided player rules, goal term 100 / 100).**

- League share (item 3), team log loss vs noise 3 without it: zero-sum 0.3
  −0.0018 (−0.0023 to −0.0013), European matches −0.0156, pool drift +2 to +6
  (not zero-sum: −0.0020, drift +12 to +16). With the share on, noise 6 −0.0023,
  noise 3 −0.0018, noise 1.5 −0.0005. Player rank correlation held-out 0.433 →
  0.446, C7 B 0.891 → 0.914.
- Big-game trust (item 5): minutes share weighted by 2 × (1 − expected score).
  Held-out 0.433 → 0.444, C7 B 0.891 → 0.904, C7 A 0.710 → 0.704. Top of squads
  barely reordered (moves of −6 to +33).
- Rotated line-ups (item 7), regularity = share of the usual eleven (most starts
  in the last 30 matches) fielded. Weighting the update by it: worse (+0.0024 at
  power 0.5, +0.0098 at 2). Shifting the expected result by 100 × the difference
  in regularity: −0.0015 (−0.0020 to −0.0009); 50: −0.0011; 200: none.

**Goal term (tested, open).** Goal involvement over the same 50 listed matches,
per 90 with 5 scoreless matches added, × 100. Process noise 3, rule B.

| Variant | Rank fit / held-out | C7 A / B | Mean bonus + goal term, keepers / defenders / midfielders / attackers |
|---|---|---|---|
| B | 0.489 / 0.423 | 0.717 / 0.885 | −58 / 81 / 77 / 71 |
| + goals | 0.505 / 0.436 | 0.710 / 0.891 | −58 / 85 / 87 / 99 |
| + goals and assists | 0.511 / 0.433 | 0.710 / 0.891 | −58 / 90 / 97 / 113 |
| + goals and assists scaled by position (analysis only) | 0.505 / 0.434 | 0.717 / 0.895 | −58 / 102 / 96 / 91 |

**Lower team K (item 2).** The team model's step size is set by its process
noise (fitted 6 per day). Decided player rules (B, national rule, keeper
reference).

| Process noise | Mean swing | Team test log loss vs fitted | Held-out rank corr. at club 200 / 400 / 800 | C7 A / B at 400 |
|---|---|---|---|---|
| 6 (fitted) | 17.7 | 0 | 0.350 / 0.410 / 0.454 | 0.684 / 0.882 |
| 3 | 15.8 | +0.0006 (+0.0002 to +0.0010) | 0.363 / 0.423 / 0.458 | 0.717 / 0.885 |
| 1.5 | 14.5 | +0.0020 (+0.0012 to +0.0027) | 0.374 / 0.431 / 0.457 | 0.717 / 0.891 |
| 0.75 | 13.7 | +0.0038 (+0.0028 to +0.0049) | 0.383 / 0.431 / 0.453 | 0.723 / 0.891 |

A smoother team rating helps player agreement at every club scale, most at
200-400, but 800 still scores best at every noise level: the scale question is
only partly team-rating noise. The 400-800 gap on held-out halves (0.044 →
0.022).
 After a European match between clubs of
different leagues, every other club active in each league in the past year gets
a share of its club's swing (scratch test, `teamelo.py` unchanged). Within a
league every club moves by the same amount, so domestic predictions and gaps
are untouched; only the level of the league moves. Test seasons 2019–26:

| Share | Log loss change, all matches (95% interval) | European matches only (5,601) |
|---|---|---|
| 0.02 | −0.0004 | −0.0028 |
| 0.15 | −0.0015 (−0.0018 to −0.0011) | −0.0118 (−0.0144 to −0.0091) |
| 0.30 | −0.0019 (−0.0024 to −0.0013) | −0.0151 (−0.0187 to −0.0111) |
| 0.50 | −0.0019 (−0.0026 to −0.0013) | −0.0162 (−0.0207 to −0.0113) |

For scale: everything the candidate team model gained over plain Elo was −0.0044.

## Decided

- Minutes rule B: a start counts as the full match, a substitute his minutes, the
  squad mean measured the same way; keepers against a reference share of 1.0
  (the owner accepts the small penalty for cup rotation). Same rule for national
  call-ups. A slight skew towards midfielders and attackers would be welcome only
  if it comes naturally.
- **Provisional, not locked:** goal term on, goals × 100 and assists × 100 per 90
  (changed from 50 / 40 by the owner); first tried at
  (`output="weighted"`), over the 50 listed matches with 5 scoreless matches added.
  Rank correlation fit / held-out 0.489 / 0.423 → 0.501 / 0.430; Kane +55 over B.
  Kept because it is arguably measurement rather than judgement, though the owner
  is not keen on it.
- **One playing-time term instead of two (2026-11-22).** Minutes bonus over his last N *club*
  matches (a missed match is 0, no separate absence discount), at club 0.7, goal 226 / assist 113,
  goal term per club match. Held-out rank correlation: two terms (squad-match minutes at 400 +
  window 150 × 2 absence) 0.496; one term over 150 club matches at scale 800 **0.507**, at 1000
  0.504 / 120 matches 0.478 / 200 matches 0.508 (scale 1000 0.509). With the old 50-match window
  it was 0.396: the window has to be long. So the single term is simpler and no worse.
- **Credit at the strength of the club where it was earned** (`minutes_strength`, owner design:
  the club he is at supplies the transfer adjustment; minutes count at the strength of where
  they were earned, so a regular at a smaller club or on loan does not get a top club's "picked
  every game" credit after moving). Each match counts (share − that club's reference share) ×
  2^((that club's rating − 2000) / D). Held-out 0.507 → 0.487 (D 800), 0.490 (D 400, scale 1000);
  C7 A 0.710 → 0.743 / 0.749; fit unchanged. Moves: Guéhi −59, Semenyo −23, Cherki −13 (from
  smaller clubs); Díaz +79, Olise +66, Madueke +17 (minutes at strong sides).
- **Absence, uncapped (2026-11-22, owner rule: not playing always costs, no cap, a longer absence
  costs more).** The old discount was capped at 120 and, because the timeline stopped at a player's
  last squad appearance, did nothing for a player still injured (Musiala and Havertz showed 0).
  Missed club matches are now counted up to the snapshot (`absence_mode`). Held-out rank
  correlation (goal 226 / assist 113, club 0.7, goal term per club match): capped 0.454; linear
  2 per missed match with recovery 3 per match played 0.489, recovery 1 0.495, 0.5 0.499, 0.25
  0.501; log (40 / 80 / 120) 0.484 / 0.472 / 0.456 (linear is better than log); window of the last
  150 club matches × 2 points 0.496; fading with half-life 100 × 2 0.489; a listed-but-unused match
  counting as missed (weight 0.5 / 1) makes no difference. Counting minutes over all club
  matches instead of squad matches (indirect) is much worse: 0.396. Simplest to state, and the
  choice: **each club match missed in the last 150 costs 2 points** (`absence_mode="window"`).
- Goal and assist weights tuned (club weight 0.7): fit rank correlation rises with both
  weights (0.518 at 158/68 → 0.526 at 300/226) while held-out peaks lower (0.458 at
  226/68, 0.457 at 226/113, 0.446 at 300/226); the surface is flat. Recommended 226 / 113
  (a goal = its measured team value, an assist half). Match importance in the minutes and
  goal windows (`match_importance`) is worse in every combination (fit −0.004 to −0.008).
- **Pending owner decision** (2026-11-22): goal value 70/30 of the measured 226 Elo per goal
  per match (goals 158, assists 68) and club weight 0.7 (`team_weight`). Rank correlation
  fit / held-out 0.512 / 0.442 → 0.518 / 0.457, C7 A / B 0.720 / 0.901 → 0.739 / 0.914;
  Haaland 21st → 8th of the 70-player sample. On-pitch goal difference (`onpitch.py`,
  `onpitch_scale`) tested and rejected: held-out 0.442 → 0.439 / 0.430 / 0.400 at scale
  100 / 200 / 400.
- Match weights **adopted** (2026-11-22): continental matches ×2, domestic cups and super
  cups ×0.5, Club World Cup ×1 (`candidate.current_team_constants()`). Reason: top clubs
  like PSG underperform the model domestically (0.844 expected, 0.809 actual) and
  outperform it in Europe (0.595 expected, 0.706 actual); European matches are the only
  direct evidence between leagues. Log loss: all matches −0.0003 (ns), European −0.0086
  (−0.0112 to −0.0057), domestic cups −0.0001 (ns). PSG 1,968 → 2,038 (3rd).
- Rotation shift **adopted** (2026-11-22): `lineup_shift=100` (a team fielding fewer of its
  usual eleven is expected to do worse in that match). Barely moves the top of the table
  (PSG 1,975 → 1,968).
- League share and big-game trust (items 3, 5) are **not
  adopted**: each is a small gain (the yardstick itself, the team model's gain over
  plain Elo, is small) and each costs interpretability. The options stay in the code,
  off by default.
- Team process noise 3 (from 6): +0.0006 team log loss for +0.013 held-out player agreement.
- Position never enters the rating, except the keeper reference; positions are
  for analysis only. Counting any appearance as a full match (`appearance`) was
  tested and rejected: it over-values substitutes (held-out rank correlation
  0.410 → 0.319).

- No plus-minus; the direct model is the candidate.
- Keepers: full credit only as first choice, a lot less otherwise.
- Age is handled separately later; evaluation uses Transfermarkt values divided by
  a linear age factor (20 worth twice 30).
