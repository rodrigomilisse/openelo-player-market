"""League redistribution of European results: does it close our league gaps against clubelo, and what
does it cost the team model? Team Elo only. For each league_share (plain and zero-sum): rating on 2025-06-01
minus clubelo, centred on the median, mean by league (clubs at clubelo >= 1750); test log loss overall and
on European matches.
    python adhoc/league_share_check.py   # from research/, about 2 minutes
"""
import sys, time; sys.path.insert(0, ".")
import numpy as np, pandas as pd, teamelo as te, candidate as c, store
matches = te.load_matches()
day = (pd.Timestamp("2025-06-01") - store.EPOCH).days
ce = store.query("SELECT team_id, elo FROM clubelo WHERE date = (SELECT MAX(date) FROM clubelo WHERE date <= '2025-06-01')").set_index("team_id").elo
lc = store.query("SELECT t.team_id, co.country FROM team t JOIN competition co ON co.competition_id = t.domestic_competition_id").set_index("team_id").country
names = store.query("SELECT team_id, name FROM team").set_index("team_id").name
CLUBS = ["Bayern Munich", "Liverpool FC", "Arsenal FC", "Manchester City", "Paris Saint-Germain", "Real Madrid", "FC Barcelona",
         "Inter Milan", "Sporting CP", "SL Benfica", "FC Porto", "PSV Eindhoven", "Brighton & Hove Albion", "Aston Villa"]
gaps, clubs, losses = {}, {}, []
for ls, zs in [(0, False), (0.15, False), (0.3, False), (0.5, False), (0.15, True), (0.3, True), (0.5, True)]:
    t0 = time.time()
    preds, _ = te.run(matches, c.current_team_constants().with_(league_share=ls, league_zero_sum=zs))
    last = {}
    for p in preds:
        if p.match.day < day:
            last[p.match.home] = p.home_rating + p.home_swing; last[p.match.away] = p.away_rating + p.away_swing
    frame = te.scored_frame(preds); s = te.score(frame)
    eu = frame[frame.competition_id.isin(te.EUROPEAN)].game_id if "competition_id" in frame else None
    s_eu = te.score(frame, eu) if eu is not None else None
    name = f"share {ls}" + (" zero-sum" if zs else "")
    x = pd.DataFrame({"ours": pd.Series(last), "clubelo": ce}).dropna(); x = x[x.clubelo >= 1750]
    x["gap"] = (x.ours - x.clubelo) - (x.ours - x.clubelo).median(); x["league"] = x.index.map(lc)
    gaps[name] = x.groupby("league").gap.mean(); clubs[name] = pd.Series(last).rename(index=names)
    losses.append((name, round(s.test_log_loss, 4), round(s_eu.test_log_loss, 4) if s_eu else None,
                   round(float(x.gap.abs().mean()), 1), round(float(np.corrcoef(x.ours, x.clubelo)[0, 1]), 3)))
    print(f"{name}: {time.time() - t0:.0f}s", flush=True)
g = pd.DataFrame(gaps); n = pd.DataFrame({"ours": pd.Series(last), "clubelo": ce}).dropna()
n = n[n.clubelo >= 1750].index.map(lc).value_counts()
g.insert(0, "clubs", n.reindex(g.index))
print("\nour rating - clubelo, centred, mean by league (clubs at clubelo >= 1750, 2025-06-01)")
print(g.round(0).sort_values("share 0").to_string())
print("\nmodel quality: test log loss (all matches / European matches), mean |gap| to clubelo, correlation with clubelo")
print(pd.DataFrame(losses, columns=["setting", "test log loss", "European log loss", "mean |gap|", "corr clubelo"]).to_string(index=False))
cl = pd.DataFrame(clubs).reindex(CLUBS); cl.insert(0, "clubelo", ce.rename(index=names).reindex(CLUBS))
print("\nclub ratings on 2025-06-01"); print(cl.round(0).to_string())
