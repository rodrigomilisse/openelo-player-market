"""Everything applied vs the previous candidate, side by side, top 7 of each of 9 clubs.
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
ALL = {**CAND, "match_importance": True, "big_game": True, "minutes_strength": True, "strength_d": 400.0,
       "goal_scaling": "opp", "goal_d": 400.0, "goal_r0": 1624.0}
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 583: "PSG", 131: "Barcelona", 418: "Real Madrid", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
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
off, tr_off = run(CAND, base_ctx); on, tr_on = run(ALL, new_ctx)
print(f"players {time.time() - t0:.0f}s", flush=True)
d = pd.DataFrame({"off": off, "on": on}).dropna()
print("mean rating off / on:", round(d.off.mean()), round(d.on.mean()))
club = d.index.map(dict(pids)).map(CLUBS)
ids = set(d.index[d.groupby(club).off.rank(ascending=False, method="first") <= 7]) | set(d.index[d.groupby(club).on.rank(ascending=False, method="first") <= 7])
def table(col, other):
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
corr = lambda col: d[col].rank().corr(pd.Series(tmv).reindex(d.index).rank())
clubrows = "".join(f"<tr><td>{CLUBS[t]}</td><td class=n>{tr_off.get(t, np.nan):.0f}</td><td class=n>{tr_on.get(t, np.nan):.0f}</td></tr>"
                   for t in sorted(CLUBS, key=lambda t: -tr_on.get(t, 0)))
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
page = (f"<title>Rating With Everything Applied</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}.clubs{{max-width:360px}}</style><h1>Previous candidate vs everything applied</h1>"
        f"<p>Snapshot 7 July 2026. Top 7 outfield players of each club under either version; ranks count only the players listed. "
        f"Applied: league redistribution of European results (0.3, zero-sum) in the team Elo; minutes weighted by competition and opponent; "
        f"minutes bonus scaled by the club where it was earned; goals weighted by opposition strength. No extra shift: mean rating "
        f"{d.off.mean():.0f} before, {d.on.mean():.0f} after. Rank correlation with Transfermarkt: {corr('off'):.3f} before, {corr('on'):.3f} after.</p>"
        f"<h2>Club ratings</h2><div class=clubs><table><tr><th>Club</th><th>Before</th><th>After</th></tr>{clubrows}</table></div>"
        f"<h2>Players</h2><div class=pair><div><h3>Previous candidate</h3>{table('off', 'on')}</div><div><h3>Everything applied</h3>{table('on', 'off')}</div></div>")
open("adhoc/all_applied.html", "w").write(page); print("written")
