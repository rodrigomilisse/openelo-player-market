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
- League share, big-game trust and the rotation shift (items 3, 5, 7) are **not
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
