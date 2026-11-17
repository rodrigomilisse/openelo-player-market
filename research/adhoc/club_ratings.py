import sys, pickle; sys.path.insert(0, ".")
import pandas as pd, numpy as np
import store, player_v2 as v2
ctx = pickle.loads((store.RAW_DIR / "cache" / "context.pkl").read_bytes())
names = store.teams().set_index("team_id").name
def rating(t):
    r = ctx.by_team.get(t)
    return None if r is None or r.empty else float(r.rating.iloc[-1] + r.swing.iloc[-1])
EURO = ["A1", "BE1", "C1", "DK1", "ES1", "FR1", "GB1", "GR1", "IT1", "L1", "NL1", "NO1", "PL1", "PO1", "RO1", "RU1", "SC1", "SE1", "SER1", "TR1", "TS1", "UKR1", "KR1"]
games = store.query("select competition_id, home_team_id h, away_team_id a, home_goals hg, away_goals ag, date from game where season = 2025 and national = 0")
league = games[games.competition_id.isin(EURO)]
# UCL
cl = games[games.competition_id == "CL"]
cl_teams = sorted(set(cl.h) | set(cl.a))
dom = store.teams().set_index("team_id").domestic_competition_id
print(f"UCL 2025-26: {len(cl_teams)} clubs, data to {cl.date.max()}")
rows = sorted(((rating(t), names[t], dom.get(t)) for t in cl_teams if rating(t)), reverse=True)
for i, (r, n, d) in enumerate(rows, 1): print(f"{i:>2} {n:<28} {d:<5} {r:.0f}")
# leagues
tabs = {}
for lg, g in league.groupby("competition_id"):
    pts, gd = {}, {}
    for x in g.itertuples():
        for t, f, a in ((x.h, x.hg, x.ag), (x.a, x.ag, x.hg)):
            pts[t] = pts.get(t, 0) + (3 if f > a else 1 if f == a else 0); gd[t] = gd.get(t, 0) + f - a
    tab = sorted(pts, key=lambda t: (-pts[t], -gd[t]))
    tabs[lg] = [(t, pts[t], rating(t)) for t in tab if rating(t)]
mean = {lg: np.mean([r for _, _, r in v]) for lg, v in tabs.items()}
top = ["GB1", "ES1", "L1", "IT1", "FR1", "PO1", "NL1", "BE1", "TR1", "SC1"]
print("\nleague   clubs  played  mean rating | mid club (position) | bottom club")
for lg in top:
    v = tabs[lg]; n = len(v); mid = v[(n + 1) // 2 - 1]; bot = v[-1]
    played = int(league[league.competition_id == lg].shape[0] * 2 / n)
    print(f"{lg:<6} {n:>4} {played:>6} {mean[lg]:>8.0f} | {names[mid[0]]} ({(n + 1) // 2}th) {mid[2]:.0f} | {names[bot[0]]} ({n}th) {bot[2]:.0f}")
print("\nnext five by mean:", [(lg, round(mean[lg])) for lg in sorted(mean, key=mean.get, reverse=True)[10:15]])
