"""Side-by-side tables per decision (feature off | on) on the 7-club mixed list, as an HTML page.
Each variant is shifted so the mean rating of all these players equals the base (same average points).
    python adhoc/decision_tables.py   # from research/, about 2 minutes; writes adhoc/decision_tables.html
"""
import sys, pickle, html; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current.pkl").read_bytes())
CAND = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
            bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
            national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=226.0, assist_scale=113.0,
            absence_mode="window", absence_window=150, absence_scale=2.0)
DEC = {"Minutes weighted by match importance (competition x opponent)": {"match_importance": True, "big_game": True},
       "Minutes bonus scaled by the club where it was earned (D400)": {"minutes_strength": True, "strength_d": 400.0},
       "Goals weighted by opposition strength (D400, centred)": {"goal_scaling": "opp", "goal_d": 400.0, "goal_r0": 1624.0}}
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 583: "PSG", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
pl = store.players().set_index("player_id")
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
pids = [(int(p), t) for t in CLUBS for p in apps[(apps.team_id == t) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique()
        if pl.position.get(p) != "Goalkeeper"]
def run(over):
    var = v2.Variant(**{**CAND, **over}); r = {}
    for p, t in pids:
        s = v2.series(p, var, ctx, [snap])
        if not s.empty and int(s.team_id.iloc[0]) == t: r[p] = float(s.rating.iloc[0])
    return pd.Series(r)
R = {"off": run({})}; print("base done", flush=True)
for k, o in DEC.items(): R[k] = run(o); print(k, "done", flush=True)
d = pd.DataFrame(R).dropna(); d = d - (d.mean() - d["off"].mean())
d.to_csv("adhoc/decision_tables.csv")
club = d.index.map(dict(pids)).map(CLUBS)
def pick(col):
    rk = d.groupby(club)[col].rank(ascending=False, method="first"); n = d.groupby(club)[col].transform("size")
    return set(d.index[(rk <= 5) | (rk > n - 5)])
def table(col, ids, other):
    x = d.loc[list(ids)].sort_values(col, ascending=False)
    rk = d[col].rank(ascending=False, method="min"); ro = d[other].rank(ascending=False, method="min")
    rows = []
    for i, (p, r) in enumerate(x[col].items(), 1):
        mv = int(ro[p] - rk[p]) if col != other else 0
        cls = "up" if mv > 0 else "down" if mv < 0 else ""
        arrow = f"▲{mv}" if mv > 0 else f"▼{-mv}" if mv < 0 else ""
        tm = "" if pd.isna(tmv.get(p)) else f"{tmv.get(p):g}"
        rows.append(f"<tr><td>{int(rk[p])}</td><td>{html.escape(str(pl.name.get(p)))}</td><td>{CLUBS[dict(pids)[p]]}</td>"
                    f"<td class=n>{r:.0f}</td><td class='n {cls}'>{arrow}</td><td class=n>{tm}</td></tr>")
    return "<table><tr><th>#</th><th>Player</th><th>Club</th><th>Rating</th><th>vs other</th><th>TM €m</th></tr>" + "".join(rows) + "</table>"
corr = lambda c: d[c].rank().corr(pd.Series(tmv).reindex(d.index).rank())
parts = []
for k in DEC:
    ids = pick("off") | pick(k)
    parts.append(f"<h2>{html.escape(k)}</h2><p>Rank correlation with Transfermarkt: off {corr('off'):.3f}, on {corr(k):.3f}. "
                 f"Arrows: places gained (▲) or lost (▼) compared with the other table.</p>"
                 f"<div class=pair><div><h3>Off</h3>{table('off', ids, k)}</div><div><h3>On</h3>{table(k, ids, 'off')}</div></div>")
css = """:root{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#e3e3e3;--up:#1a7f37;--down:#c62828;--head:#f5f5f5}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--mute:#9a9a9a;--line:#333;--up:#4ac26b;--down:#ff6b6b;--head:#222}}
body{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:0;padding:16px}
h1{font-size:20px}h2{font-size:17px;margin-top:32px}h3{font-size:15px;margin:8px 0}p{color:var(--mute)}
.pair{display:flex;gap:24px;flex-wrap:wrap}.pair>div{flex:1 1 420px;min-width:0;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{padding:3px 6px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{background:var(--head)}.n{text-align:right;font-variant-numeric:tabular-nums}.up{color:var(--up)}.down{color:var(--down)}"""
page = (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Decision tables</title><style>{css}</style></head><body><h1>Player rating: each decision off and on</h1>"
        f"<p>Previous player_v2 candidate, snapshot 7 July 2026, outfield players of Bayern, Arsenal, PSG, City, Sporting, Brighton, Braga. "
        f"Each list: the 5 highest and 5 lowest of each club under either version. Ranks are among all {len(d)} outfield players of these clubs. "
        f"Every version is shifted so the average rating equals the base.</p>{''.join(parts)}</body></html>")
open("adhoc/decision_tables.html", "w").write(page); print("written")
