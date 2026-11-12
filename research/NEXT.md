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
4. **National teams, "the company you keep"**: replace the additive national
   points with a lift towards the level of the national team-mates:
   `rating = C + w × max(0, N − C)`, with C the club standing (team + bonus),
   N the national standing (mean club standing of his national team-mates on the
   pitch, himself excluded, + the same role bonus at national level), averaged over
   call-ups with a decay instead of the 10-call-up / two-year window. Starters
   full share, substitutes their minutes, unused squad members 0, keeper rule at
   national level too. Prototype on the seven clubs first.
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

**League share of European results.** After a European match between clubs of
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

- No plus-minus; the direct model is the candidate.
- Keepers: full credit only as first choice, a lot less otherwise.
- Age is handled separately later; evaluation uses Transfermarkt values divided by
  a linear age factor (20 worth twice 30).
