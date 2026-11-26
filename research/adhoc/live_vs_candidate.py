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
if P.exists(): new_ctx = pickle.loads(P.read_bytes()); old_ctx = pickle.loads((store.RAW_DIR / "cache" / "before_recent" / "context_current_league0.3zs.pkl").read_bytes())
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
REC = {**ALL, "absence_scale": 0.0, "goal_scale": 158.0, "assist_scale": 79.0}
SNAP_NEW = (pd.Timestamp("2026-11-25") - store.EPOCH).days
def run_at(cfg, ctx, day):
    var = v2.Variant(**cfg); r = {}
    for p, t in pids:
        s_ = v2.series(p, var, ctx, [day])
        if not s_.empty and int(s_.team_id.iloc[0]) in CLUBS: r[p] = float(s_.rating.iloc[0]); CLUB_OF[p] = int(s_.team_id.iloc[0])
    return pd.Series(r)
CLUB_OF = {}
import teamelo as te
LIVE_TEAM = te.TeamConstants(uncertainty=True, process_noise=3.0, initial_variance=400.0 ** 2, home_advantage=50.0,
                             goal_difference=True, league_seed_offset=100.0, unknown_seed_offset=300.0)
LP = store.RAW_DIR / "cache" / "context_live_formula.pkl"
if LP.exists(): live_ctx = pickle.loads(LP.read_bytes())
else:
    live_ctx = v2.Context(LIVE_TEAM); LP.write_bytes(pickle.dumps(live_ctx, protocol=5))
LIVE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0,
            national_scale=100.0, nt_matches=20, nt_credit=0.2, nt_days=730, share_rule="starter", gk_reference=True, output="weighted",
            goal_scale=100.0, assist_scale=100.0, output_prior=5.0)
cur = run_at(LIVE, live_ctx, SNAP_NEW); old_club = dict(CLUB_OF); CLUB_OF.clear()
# custom match weights for the minutes window: Champions League 4 (knockouts and final 8); domestic league by league strength
# (strongest league 4, then 3, 2, 1, and 1 for every league after); everything else 1
games = store.query("SELECT g.game_id, g.competition_id, g.stage, co.type, co.country FROM game g JOIN competition co USING(competition_id)")
tmx = new_ctx.team_matches.merge(games, on="game_id", how="left")
recent = tmx[(tmx.day >= (pd.Timestamp("2026-07-07") - store.EPOCH).days - 730) & (tmx.type == "domestic_league")]
lg = recent.groupby("country").rating.mean().sort_values(ascending=False)
lg = lg[recent.groupby("country").team_id.nunique().reindex(lg.index) >= 10]
LW = {k: w for k, w in zip(lg.index, [4.0, 3.0, 2.0])}
print("league order:", [(k, round(v)) for k, v in lg.head(6).items()])
w = np.where((tmx.competition_id == "CL") & tmx.stage.isin(["continental_knockout", "continental_final"]), 8.0, np.where(tmx.competition_id == "CL", 4.0, np.where(tmx.type == "domestic_league", tmx.country.map(LW).fillna(1.0), 1.0)))
import copy
wctx = copy.copy(new_ctx); wctx.team_matches = new_ctx.team_matches.copy(); wctx.team_matches["importance"] = w
wctx.by_team = {t: g.reset_index(drop=True) for t, g in wctx.team_matches.groupby("team_id")}
REC2 = {**REC, "squad_top": 5, "goal_scale": 158.0 * 0.75, "assist_scale": 79.0 * 0.75, "nt_skip_injured": True, "weighted_reference": True}
res = {"Current candidate (4-3-2-1, CL 4, knockouts 8, national Elo)": run_at({**REC2, "national": "elo", "squad_top": 16, "per_match_reference": True, "nt_window_injury": True}, wctx, SNAP_NEW)}; new_club = dict(CLUB_OF)
print(f"players {time.time() - t0:.0f}s", flush=True)
tmS = pd.Series(tmv)
def table(d, col, other, ids):
    x = d.loc[list(ids)].sort_values(col, ascending=False)
    rk = x[col].rank(ascending=False, method="min"); ro = x[other].rank(ascending=False, method="min")
    tr = pd.Series({p: tmv.get(p, np.nan) for p in x.index}).rank(ascending=False, method="min")
    rows = []
    for p, r in x[col].items():
        mv = int(ro[p] - rk[p]); cls = "up" if mv > 0 else "down" if mv < 0 else ""
        arrow = f"▲{mv}" if mv > 0 else f"▼{-mv}" if mv < 0 else ""
        tm = "" if pd.isna(tmv.get(p)) else f"{tmv.get(p):g}"
        rows.append(f"<tr><td class=n>{int(rk[p])}</td><td>{html.escape(str(pl.name.get(p)))}</td><td>{CLUBS.get((new_club if col == 'var' else old_club).get(p), '')}</td>"
                    f"<td class=n>{r:.0f}</td><td class='n {cls}'>{arrow}</td><td class=n>{tm}</td><td class=n>{'' if pd.isna(tr[p]) else int(tr[p])}</td></tr>")
    return "<table><tr><th>#</th><th>Player</th><th>Club</th><th>Rating</th><th>vs other</th><th>TM €m</th><th>TM rank</th></tr>" + "".join(rows) + "</table>"
parts = []
for k, v in res.items():
    d = pd.DataFrame({"cur": cur, "var": v}).dropna(); club = d.index.map(lambda p: new_club.get(p, old_club.get(p)))
    ids = set(d.index[d.groupby(club).cur.rank(ascending=False, method="first") <= 7]) | set(d.index[d.groupby(club)["var"].rank(ascending=False, method="first") <= 7])
    corr = lambda col: d[col].rank().corr(tmS.reindex(d.index).rank())
    parts.append(f"<h2>{html.escape(k)}</h2><p>Mean rating: current {d.cur.mean():.0f}, this version {d['var'].mean():.0f}. "
                 f"Rank correlation with Transfermarkt: current {corr('cur'):.3f}, this version {corr('var'):.3f}.</p>"
                 f"<div class=pair><div><h3>Live site formula (pipeline/rate.py, OpenElo beta 0.1)</h3>{table(d, 'cur', 'var', ids)}</div><div><h3>{html.escape(k)}</h3>{table(d, 'var', 'cur', ids)}</div></div>")
    print(k, [f"{i+1} {pl.name.get(p)}" for i, p in enumerate(d.loc[list(ids)].sort_values('var', ascending=False).index[:20])])
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
page = (f"<title>Live Formula Vs Candidate</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}</style><h1>Match weights 4-3-2-1, top-5 reference, goals cut 25%, injury-aware national term, weighted reference, Champions League knockouts ×8</h1>"
        f"<p>Current: league redistribution (0.3, zero-sum), minutes weighted by competition and opponent, minutes scaled by the club where earned "
        f"relative to his current club, goals and assists weighted by opposition and cut by 30% (158 and 79 per 90), absence term on. "
        f"Snapshot 7 July 2026 (data ends early July 2026). Top 7 outfield players of each club under either version; ranks count only the players listed.</p>"
        f"{''.join(parts)}")
open("adhoc/live_vs_candidate.html", "w").write(page); print("written")
d = pd.DataFrame({"live": cur, "cand": list(res.values())[0]}).dropna()
a = d.sort_values("live", ascending=False).head(50); b = d.sort_values("cand", ascending=False).head(50)
nm = lambda p: pl.name.get(p); cl = lambda p: CLUBS.get(new_club.get(p, old_club.get(p)), "")
for i in range(50):
    pa, pb = a.index[i], b.index[i]
    print(f"| {i+1} | {nm(pa)} ({cl(pa)}) {a.live.iloc[i]:.0f} | {nm(pb)} ({cl(pb)}) {b.cand.iloc[i]:.0f} |")
print("rank corr live vs candidate:", round(d.live.rank().corr(d.cand.rank()), 3), "| with TM: live", round(d.live.rank().corr(pd.Series(tmv).reindex(d.index).rank()), 3), "candidate", round(d.cand.rank().corr(pd.Series(tmv).reindex(d.index).rank()), 3))
PSG_OWN = ["Ousmane Dembélé", "João Neves", "Vitinha", "Khvicha Kvaratskhelia", "Désiré Doué", "Nuno Mendes", "Achraf Hakimi", "Fabián Ruiz", "Willian Pacho", "Ferran Torres"]
v = list(res.values())[0]
for lab, ser in (("current", cur), ("new", v)):
    x = pd.Series({pl.name.get(p): r for p, r in ser.items() if pl.name.get(p) in PSG_OWN})
    order = x.sort_values(ascending=False)
    sp = pd.Series([PSG_OWN.index(n) for n in order.index]).corr(pd.Series(range(len(order))), method="pearson")
    print(lab, "PSG order:", list(order.index), "| agreement with yours:", round(sp, 2))
for n in ["William Saliba", "João Neves", "Kai Havertz", "Gabriel", "Declan Rice", "Vitinha", "Nuno Mendes"]:
    ps = [p for p in v.index if pl.name.get(p) == n]
    if ps: print(n, "current", round(cur.get(ps[0], float("nan"))), "new", round(v[ps[0]]))
