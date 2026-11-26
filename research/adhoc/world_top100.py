"""World top 100: live-site formula (pipeline/rate.py, OpenElo beta 0.1) vs current candidate, players of the 25
strongest clubs by the candidate's club Elo on 2026-11-25 (outfield players who played for them in the past year
and are still there). Writes adhoc/world_top100.html and .csv.
Current candidate: league redistribution 0.3 zero-sum; minutes weighted Champions League 4 (knockouts 8), leagues
4-3-2-1 by strength, x opponent strength; per-match top-16 reference; minutes relative to current club; goals 119 /
assists 59 per 90 weighted by opposition; national term from national-team Elo, internationals skipped when injured
(club or camp); no absence term.
    python adhoc/world_top100.py   # from research/, about 8-10 minutes
"""
import sys, pickle, copy, html, time; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store, teamelo as te
t0 = time.time()
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current_league0.3zs.pkl").read_bytes())
live_ctx = pickle.loads((store.RAW_DIR / "cache" / "context_live_formula.pkl").read_bytes())
SNAP = (pd.Timestamp("2026-11-25") - store.EPOCH).days
games = store.query("SELECT g.game_id, g.competition_id, g.stage, co.type, co.country FROM game g JOIN competition co USING(competition_id)")
tmx = ctx.team_matches.merge(games, on="game_id", how="left")
rec = tmx[(tmx.day >= SNAP - 730) & (tmx.type == "domestic_league")]
lg = rec.groupby("country").rating.mean().sort_values(ascending=False); lg = lg[rec.groupby("country").team_id.nunique().reindex(lg.index) >= 10]
LW = dict(zip(lg.index, [4.0, 3.0, 2.0]))
w = np.where((tmx.competition_id == "CL") & tmx.stage.isin(["continental_knockout", "continental_final"]), 8.0,
             np.where(tmx.competition_id == "CL", 4.0, np.where(tmx.type == "domestic_league", tmx.country.map(LW).fillna(1.0), 1.0)))
wctx = copy.copy(ctx); wctx.team_matches = ctx.team_matches.copy(); wctx.team_matches["importance"] = w
wctx.by_team = {t: g.reset_index(drop=True) for t, g in wctx.team_matches.groupby("team_id")}
CAND = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="elo",
            bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
            national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=118.5, assist_scale=59.25,
            absence_mode="window", absence_window=150, absence_scale=0.0, match_importance=True, big_game=True,
            minutes_strength=True, strength_d=400.0, strength_relative=True, goal_scaling="opp", goal_d=400.0, goal_r0=1624.0,
            nt_skip_injured=True, weighted_reference=True, per_match_reference=True, nt_window_injury=True)
LIVE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0,
            national_scale=100.0, nt_matches=20, nt_credit=0.2, nt_days=730, share_rule="starter", gk_reference=True, output="weighted",
            goal_scale=100.0, assist_scale=100.0, output_prior=5.0)
last = ctx.team_matches[ctx.team_matches.day < SNAP].sort_values("day").groupby("team_id").tail(1)
last = last[last.day >= SNAP - 120]
top = (last.assign(r=last.rating + last.swing).sort_values("r", ascending=False).head(25))
TEAMS = dict(zip(top.team_id, top.r))
tn = store.query("SELECT team_id, name FROM team").set_index("team_id").name
pl = store.players().set_index("player_id")
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
recent = apps[(apps.day >= SNAP - 365) & (apps.day < SNAP) & (apps.minutes > 0) & apps.team_id.isin(TEAMS)]
pids = sorted({int(p) for p in recent.player_id.unique() if pl.position.get(p) != "Goalkeeper"})
print(f"{len(TEAMS)} clubs, {len(pids)} players ({time.time() - t0:.0f}s)", flush=True)
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
def run(cfg, cx, label):
    var = v2.Variant(**cfg); out = {}
    for i, p in enumerate(pids):
        s = v2.series(p, var, cx, [SNAP])
        if not s.empty and int(s.team_id.iloc[0]) in TEAMS: out[p] = (float(s.rating.iloc[0]), int(s.team_id.iloc[0]))
        if i % 200 == 0: print(f"  {label}: {i}/{len(pids)} ({time.time() - t0:.0f}s)", flush=True)
    return out
L = run(LIVE, live_ctx, "live"); C = run(CAND, wctx, "candidate")
d = pd.DataFrame({"live": {p: v[0] for p, v in L.items()}, "cand": {p: v[0] for p, v in C.items()}}).dropna()
d["club"] = [tn.get(C.get(p, L.get(p))[1]) for p in d.index]; d["name"] = d.index.map(pl.name); d["TM"] = d.index.map(tmv)
d["rank_live"] = d.live.rank(ascending=False, method="min").astype(int); d["rank_cand"] = d.cand.rank(ascending=False, method="min").astype(int)
d.to_csv("adhoc/world_top100.csv")
a = d.sort_values("live", ascending=False).head(100); b = d.sort_values("cand", ascending=False).head(100)
def cell(r, other):
    mv = int(r[other] - (r.rank_live if other == "rank_cand" else r.rank_cand))
    cls = "up" if mv > 0 else "down" if mv < 0 else ""
    return mv, cls
rows = []
for i in range(100):
    ra, rb = a.iloc[i], b.iloc[i]
    ma = int(ra.rank_cand - ra.rank_live); mb = int(rb.rank_live - rb.rank_cand)
    fa = f"▲{-ma}" if ma < 0 else f"▼{ma}" if ma > 0 else ""
    fb = f"▲{mb}" if mb > 0 else f"▼{-mb}" if mb < 0 else ""
    rows.append(f"<tr><td class=n>{i+1}</td><td>{html.escape(str(ra['name']))}</td><td>{html.escape(str(ra.club))}</td><td class=n>{ra.live:.0f}</td>"
                f"<td class='n {'up' if ma < 0 else 'down' if ma > 0 else ''}'>{fa}</td><td class=sep></td>"
                f"<td>{html.escape(str(rb['name']))}</td><td>{html.escape(str(rb.club))}</td><td class=n>{rb.cand:.0f}</td>"
                f"<td class='n {'up' if mb > 0 else 'down' if mb < 0 else ''}'>{fb}</td><td class=n>{'' if pd.isna(rb.TM) else f'{rb.TM:g}'}</td></tr>")
corr = lambda c: d[c].rank().corr(d.TM.rank())
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
clubs = ", ".join(f"{tn.get(t)}" for t in TEAMS)
page = (f"<title>World Top 100</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}.wide{{overflow-x:auto}}td.sep{{border:none;width:16px}}</style><h1>World top 100: live formula against current candidate</h1>"
        f"<p>Ratings on 25 November 2026 from research data (to 24 November). Outfield players of the 25 strongest clubs by the candidate's club Elo. "
        f"Left: the live site's formula (OpenElo beta 0.1, pipeline/rate.py). Right: the current candidate. Arrows: places gained (▲) or lost (▼) in the other version. "
        f"Rank correlation between the two: {d.live.rank().corr(d.cand.rank()):.3f}; with Transfermarkt (June 2026 values): live {corr('live'):.3f}, candidate {corr('cand'):.3f}.</p>"
        f"<p>Clubs: {html.escape(clubs)}.</p>"
        f"<div class=wide><table><tr><th>#</th><th>Live: player</th><th>Club</th><th>Rating</th><th>in candidate</th><th class=sep></th>"
        f"<th>Candidate: player</th><th>Club</th><th>Rating</th><th>in live</th><th>TM €m</th></tr>{''.join(rows)}</table></div>")
open("adhoc/world_top100.html", "w").write(page); print(f"written ({time.time() - t0:.0f}s)")
