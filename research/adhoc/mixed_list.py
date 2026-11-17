import sys, pickle, json; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_process_noise3.pkl").read_bytes())
BASE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0, national_scale=100.0)
NEW = dict(nt_matches=20, nt_days=730, nt_credit=0.2)
G = dict(share_rule="starter", gk_reference=True)
VARS = {"B": {**NEW, **G}, "goals": {**NEW, **G, "output": "goals"}, "GA": {**NEW, **G, "output": "ga"}, "GApos": {**NEW, **G, "output": "ga_position"}}
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 583: "PSG", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
got = {}; orig = v2.Player.published
def published(self, day, context):
    got["nt"] = self.national_points(day, context); return orig(self, day, context)
v2.Player.published = published
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
names = store.players().set_index("player_id").name
rows = []
for team, club in CLUBS.items():
    pids = apps[(apps.team_id == team) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique()
    for pid in pids:
        rec = {"player": names.get(pid, pid), "club": club}
        ok = True
        for vn, over in VARS.items():
            s = v2.series(int(pid), v2.Variant(**{**BASE, **over}), ctx, [snap])
            if s.empty or int(s.team_id.iloc[0]) != team: ok = False; break
            rec[vn] = round(float(s.rating.iloc[0])); rec["nt " + vn] = round(got["nt"])
        if ok: rows.append(rec)
d = pd.DataFrame(rows)
for vn in VARS:
    d["rank " + vn] = d.groupby("club")[vn].rank(ascending=False, method="first").astype(int)
pick = d[(d["rank GA"] <= 5) | d["rank GA"].between(15, 20)].sort_values("GA", ascending=False)
for _, r in pick.iterrows():
    print(f"| {r.player} | {r.club} | {r['rank GA']} | {r['B']} | {r['goals']} | {r['GA']} | {r['GApos']} |")
