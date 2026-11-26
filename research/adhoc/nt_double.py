"""Three variants vs the current rating, side by side, top 7 of each of 9 clubs.
All on: league redistribution 0.3 zero-sum (team Elo), minutes x competition x opponent, minutes bonus at the
club where earned (D400), goals x opposition (D400, centred over all goals; no extra shift).
    python adhoc/all_applied.py   # from research/; first run builds the league-share context (cached)
"""
import sys, pickle, time, html; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store, candidate as c
t0 = time.time()
base_ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current.pkl").read_bytes())
P = store.RAW_DIR / "cache" / "context_current_league0.3zs.pkl"
if P.exists(): new_ctx = pickle.loads(P.read_bytes())
else:
    new_ctx = v2.Context(c.current_team_constants().with_(league_share=0.3, league_zero_sum=True))
    P.write_bytes(pickle.dumps(new_ctx, protocol=5))
print(f"contexts {time.time() - t0:.0f}s", flush=True)
CAND = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
            bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
            national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=226.0, assist_scale=113.0,
            absence_mode="window", absence_window=150, absence_scale=2.0)
tmr = new_ctx.team_matches[new_ctx.team_matches.day >= (pd.Timestamp("2026-07-07") - store.EPOCH).days - 730].rating
R0 = 400.0 * np.log2(np.mean(2.0 ** (tmr / 400.0)))     # club strength where the minutes factor is 1, market average
print("minutes-factor centre", round(R0))
ALL = {**CAND, "match_importance": True, "big_game": True, "minutes_strength": True, "strength_d": 400.0, "strength_relative": True,
       "goal_scaling": "opp", "goal_d": 400.0, "goal_r0": 1624.0, "goal_scale": 226.0 * 0.7, "assist_scale": 113.0 * 0.7}
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 985: "Man United", 583: "PSG", 131: "Barcelona", 418: "Real Madrid", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
apps = base_ctx.appearances.copy(); apps["day"] = apps.game_id.map(base_ctx.day)
pl = store.players().set_index("player_id")
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
pids = [(int(p), t) for t in CLUBS for p in apps[(apps.team_id == t) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique()
        if pl.position.get(p) != "Goalkeeper"]
def run(cfg, ctx):
    var = v2.Variant(**cfg); r, tr = {}, {}
    for p, t in pids:
        s = v2.series(p, var, ctx, [snap])
        if not s.empty and int(s.team_id.iloc[0]) == t: r[p] = float(s.rating.iloc[0]); tr[t] = float(s.team_rating.iloc[0])
    return pd.Series(r), tr
CUR = ALL
VARS = {"National-team term doubled (scale 200)": {**ALL, "national_scale": 200.0}}
cur, _ = run(CUR, new_ctx); res = {k: run(v, new_ctx)[0] for k, v in VARS.items()}
print(f"players {time.time() - t0:.0f}s", flush=True)
tmS = pd.Series(tmv)
def table(d, col, other, ids):
    x = d.loc[list(ids)].sort_values(col, ascending=False)
    rk = x[col].rank(ascending=False, method="min"); ro = x[other].rank(ascending=False, method="min")
    rows = []
    for p, r in x[col].items():
        mv = int(ro[p] - rk[p]); cls = "up" if mv > 0 else "down" if mv < 0 else ""
        arrow = f"▲{mv}" if mv > 0 else f"▼{-mv}" if mv < 0 else ""
        tm = "" if pd.isna(tmv.get(p)) else f"{tmv.get(p):g}"
        rows.append(f"<tr><td class=n>{int(rk[p])}</td><td>{html.escape(str(pl.name.get(p)))}</td><td>{CLUBS[dict(pids)[p]]}</td>"
                    f"<td class=n>{r:.0f}</td><td class='n {cls}'>{arrow}</td><td class=n>{tm}</td></tr>")
    return "<table><tr><th>#</th><th>Player</th><th>Club</th><th>Rating</th><th>vs other</th><th>TM €m</th></tr>" + "".join(rows) + "</table>"
parts = []
for k, v in res.items():
    d = pd.DataFrame({"cur": cur, "var": v}).dropna(); club = d.index.map(dict(pids)).map(CLUBS)
    ids = set(d.index[d.groupby(club).cur.rank(ascending=False, method="first") <= 7]) | set(d.index[d.groupby(club)["var"].rank(ascending=False, method="first") <= 7])
    corr = lambda col: d[col].rank().corr(tmS.reindex(d.index).rank())
    parts.append(f"<h2>{html.escape(k)}</h2><p>Mean rating: current {d.cur.mean():.0f}, this version {d['var'].mean():.0f}. "
                 f"Rank correlation with Transfermarkt: current {corr('cur'):.3f}, this version {corr('var'):.3f}.</p>"
                 f"<div class=pair><div><h3>Current</h3>{table(d, 'cur', 'var', ids)}</div><div><h3>{html.escape(k)}</h3>{table(d, 'var', 'cur', ids)}</div></div>")
    print(k, [f"{i+1} {pl.name.get(p)}" for i, p in enumerate(d.loc[list(ids)].sort_values('var', ascending=False).index[:20])])
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
page = (f"<title>National Term Doubled</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}</style><h1>Current rating with the national-team term doubled</h1>"
        f"<p>Current: league redistribution (0.3, zero-sum), minutes weighted by competition and opponent, minutes scaled by the club where earned "
        f"relative to his current club, goals and assists weighted by opposition and cut by 30% (158 and 79 per 90), absence term on. "
        f"Snapshot 7 July 2026 (data ends early July 2026). Top 7 outfield players of each club under either version; ranks count only the players listed.</p>"
        f"{''.join(parts)}")
open("adhoc/nt_double.html", "w").write(page); print("written")
