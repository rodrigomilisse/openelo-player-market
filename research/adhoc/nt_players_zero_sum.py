"""(1) National strength from team-mates' ratings without the national term (club level + minutes + goals and
assists), rescaled to the same mean and spread across nations as the club-rating strength; (2) goal and
national bonuses taken back from the club's squad in proportion to minutes, so the club's total is set by its Elo.
Base: assists in (158 / 79 per 90, opposition-weighted), no absence, 2-year national window. Snapshot 2026-07-07.
    python adhoc/nt_players_zero_sum.py   # from research/, about 3 minutes
"""
import sys, pickle, html, time, dataclasses; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
t0 = time.time()
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current_league0.3zs.pkl").read_bytes())
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
CFG = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
           bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
           national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=158.0, assist_scale=79.0,
           absence_mode="window", absence_window=150, absence_scale=0.0, match_importance=True, big_game=True,
           minutes_strength=True, strength_d=400.0, strength_relative=True, goal_scaling="opp", goal_d=400.0, goal_r0=1624.0)
VAR = v2.Variant(**CFG); FLAT = dataclasses.replace(VAR, national="flat")
got = {}; orig = v2.Player.published
def pub(self, day, context):
    got.update(base=self.rating(), minutes=self.bonus(day, context), goals=self.output_points(context), nt_clubs=self.national_points(day, context))
    v = self.v; self.v = FLAT; got["nt_flat"] = self.national_points(day, context); self.v = v
    calls = [c for c in getattr(self, "call_ups", []) if c[0] < day]; got["nation"] = calls[-1][5] if calls else None
    return orig(self, day, context)
v2.Player.published = pub
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 985: "Man United", 583: "PSG", 131: "Barcelona", 418: "Real Madrid",
         336: "Sporting", 1237: "Brighton", 1075: "Braga"}
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
yr = apps[(apps.day >= snap - 365) & (apps.day < snap)]
pl = store.players().set_index("player_id"); tn = store.query("SELECT team_id, name FROM team").set_index("team_id").name
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
def comps(pid):
    s = v2.series(int(pid), VAR, ctx, [snap])
    return None if s.empty else dict(player_id=int(pid), team=int(s.team_id.iloc[0]), **{k: got[k] for k in ("base", "minutes", "goals", "nt_clubs", "nt_flat", "nation")})
# players of the clubs
rows = []
for t in CLUBS:
    for p in yr[(yr.team_id == t) & (yr.minutes > 0)].player_id.unique():
        r = comps(p)
        if r and r["team"] == t: r["club_minutes"] = float(yr[(yr.player_id == p) & (yr.team_id == t)].minutes.sum()); rows.append(r)
d = pd.DataFrame(rows)
print(f"club players {len(d)}  ({time.time() - t0:.0f}s)", flush=True)
# national strength from team-mates' ratings without the national term, for the nations of these players
nations = set(d.nation.dropna().astype(int))
members = {}
for p, lst in ctx.national_call_ups.items():
    for c in lst:
        if snap - 730 <= c[0] < snap and c[5] in nations: members.setdefault(int(c[5]), set()).add(int(p))
pre = {}
for n, ps in members.items():
    for p in ps:
        if p in pre: continue
        r = comps(p); pre[p] = None if r is None else r["base"] + r["minutes"] + r["goals"]
print(f"national squad players {len(pre)}  ({time.time() - t0:.0f}s)", flush=True)
old = {}; new = {}
for n, ps in members.items():
    v = [pre[p] for p in ps if pre.get(p) is not None]
    new[n] = np.mean(v) if v else np.nan
for p, lst in ctx.national_call_ups.items():
    for c in lst:
        if snap - 730 <= c[0] < snap and c[5] in nations: old.setdefault(int(c[5]), []).append(c[2])
S = pd.DataFrame({"old_level": {n: np.mean(v) for n, v in old.items()}, "new_level": new}).dropna()
S["old_strength"] = (S.old_level - 1600).clip(lower=0) / 200
z = (S.new_level - S.new_level.mean()) / S.new_level.std()
S["new_strength"] = (S.old_strength.mean() + z * S.old_strength.std()).clip(lower=0)
S["nation"] = S.index.map(lambda i: tn.get(i, i))
print(S.sort_values("new_strength", ascending=False)[["nation", "old_level", "old_strength", "new_level", "new_strength"]].round(2).head(25).to_string(index=False))
d["nt_new"] = d.nt_flat * d.nation.map(S.new_strength).fillna(0)
d["current"] = d.base + d.minutes + d.goals + d.nt_clubs
d["nt_players"] = d.base + d.minutes + d.goals + d.nt_new
def zero_sum(nt_col):
    b = d.goals + d[nt_col]
    w = d.club_minutes / d.groupby("team").club_minutes.transform("sum")
    return d.base + d.minutes + b - w * d.assign(b=b).groupby("team").b.transform("sum")
d["zero_sum"] = zero_sum("nt_new")
d["name"] = d.player_id.map(pl.name); d["club"] = d.team.map(CLUBS); d["TM"] = d.player_id.map(tmv)
d.to_csv("adhoc/nt_players_zero_sum.csv", index=False)
print(f"done ({time.time() - t0:.0f}s); mean current {d.current.mean():.0f}, nt_players {d.nt_players.mean():.0f}, zero_sum {d.zero_sum.mean():.0f}")
# page
def table(x, col, other, ids):
    x = x.loc[ids].sort_values(col, ascending=False)
    rk = x[col].rank(ascending=False, method="min"); ro = x[other].rank(ascending=False, method="min"); tr = x.TM.rank(ascending=False, method="min")
    out = []
    for i, r in x.iterrows():
        mv = int(ro[i] - rk[i]); cls = "up" if mv > 0 else "down" if mv < 0 else ""
        out.append(f"<tr><td class=n>{int(rk[i])}</td><td>{html.escape(str(r['name']))}</td><td>{r.club}</td><td class=n>{r[col]:.0f}</td>"
                   f"<td class='n {cls}'>{'▲%d' % mv if mv > 0 else '▼%d' % -mv if mv < 0 else ''}</td><td class=n>{'' if pd.isna(r.TM) else f'{r.TM:g}'}</td>"
                   f"<td class=n>{'' if pd.isna(tr[i]) else int(tr[i])}</td></tr>")
    return "<table><tr><th>#</th><th>Player</th><th>Club</th><th>Rating</th><th>vs other</th><th>TM €m</th><th>TM rank</th></tr>" + "".join(out) + "</table>"
corr = lambda c: d[c].rank().corr(d.TM.rank())
parts = []
for col, title in (("nt_players", "National strength from team-mates' ratings"), ("zero_sum", "National strength from team-mates' ratings, and goal and national bonuses taken from the squad")):
    ids = list(set(d.index[d.groupby("team").current.rank(ascending=False, method="first") <= 7]) | set(d.index[d.groupby("team")[col].rank(ascending=False, method="first") <= 7]))
    parts.append(f"<h2>{html.escape(title)}</h2><p>Mean rating: current {d.current.mean():.0f}, this version {d[col].mean():.0f}. Rank correlation with Transfermarkt: current {corr('current'):.3f}, this version {corr(col):.3f}.</p>"
                 f"<div class=pair><div><h3>Current</h3>{table(d, 'current', col, ids)}</div><div><h3>This version</h3>{table(d, col, 'current', ids)}</div></div>")
srows = "".join(f"<tr><td>{html.escape(str(r.nation))}</td><td class=n>{r.old_level:.0f}</td><td class=n>{r.old_strength:.2f}</td><td class=n>{r.new_level:.0f}</td><td class=n>{r.new_strength:.2f}</td></tr>"
                for r in S.sort_values("new_strength", ascending=False).head(30).itertuples())
css = open("adhoc/decision_tables.py").read().split('css = """')[1].split('"""')[0]
page = (f"<title>National Strength And Club Totals</title><meta name=\"claude:viewport-fit-sides\" content=\"cover\">"
        f"<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
        f"<style>{css}.narrow{{max-width:620px}}</style><h1>National strength from player ratings, and club totals set by club Elo</h1>"
        f"<p>Current: league redistribution, importance-weighted minutes relative to current club, goals and assists weighted by opposition (158 and 79 per 90), "
        f"no absence term, national term with strength from team-mates' club ratings. Snapshot 7 July 2026 (data ends early July 2026). "
        f"Top 7 outfield and goalkeepers of each club under either version; ranks count only the players listed.</p>"
        f"<h2>Nation strength</h2><p>Old: team-mates' average club rating. New: team-mates' average rating without the national term, rescaled to the same mean and spread across these nations.</p>"
        f"<div class=narrow><table><tr><th>Nation</th><th>Avg club rating</th><th>Old strength</th><th>Avg player rating</th><th>New strength</th></tr>{srows}</table></div>"
        f"{''.join(parts)}")
open("adhoc/nt_players_zero_sum.html", "w").write(page); print("written")
