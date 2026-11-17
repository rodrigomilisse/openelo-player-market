import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
import player_v2 as v2, store, candidate as c
VD = v2.Variant(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0, national_scale=100.0)
import pickle; ctx = pickle.loads((store.RAW_DIR / 'cache' / 'context.pkl').read_bytes())
TEAM = int(sys.argv[1]); SNAPDATE = sys.argv[2]
snap = int((pd.Timestamp(SNAPDATE) - store.EPOCH).days)
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day); apps["length"] = apps.game_id.map(ctx.length)
recent = apps[(apps.team_id == TEAM) & (apps.day >= snap - 365) & (apps.minutes > 0)]
recent = recent.assign(share=np.minimum(recent.minutes, recent.length) / recent.length)
n_matches = ctx.by_team[TEAM].query("day >= @snap - 365").shape[0]
agg = recent.groupby("player_id").agg(s=("share", "sum")); agg["all"] = agg.s / n_matches
agg = agg.sort_values("all", ascending=False).head(80)
pl = store.players().set_index("player_id")
LAST = {}
orig = v2.Player.published
def published(self, day, context):
    r = orig(self, day, context)
    LAST.update(rating=r, bonus=self.bonus(day, context), nt=self.national_points(day, context), discount=self.discount,
                window=float(np.mean(self.window)) if self.window else np.nan, squad=context.squad_mean_at(self.team, day, VD.squad_top),
                calls=len([x for x in self.call_ups if snap - 730 <= x[0] < snap][-10:]),
                nt_share=float(np.mean([x[1] for x in [x for x in self.call_ups if snap - 730 <= x[0] < snap][-10:]] or [np.nan])),
                nt_level=float(np.mean([x[2] for x in [x for x in self.call_ups if snap - 730 <= x[0] < snap][-10:]] or [np.nan])))
    return r
v2.Player.published = published
rows = []
for pid in agg.index:
    s = v2.series(int(pid), VD, ctx, [snap])
    if s.empty or int(s.team_id.iloc[0]) != TEAM: continue
    r = s.iloc[0]
    rows.append((pl.name[pid], round(agg["all"][pid], 2), round(LAST["window"], 2), round(LAST["squad"], 2), round(r.team_rating), round(LAST["bonus"]), round(LAST["nt"]), round(-LAST["discount"]), round(r.rating), LAST["calls"], None if np.isnan(LAST["nt_share"]) else round(LAST["nt_share"], 2), None if np.isnan(LAST["nt_level"]) else round(LAST["nt_level"])))
df = pd.DataFrame(rows, columns=["player", "share all", "share when in squad", "squad mean", "team", "minutes bonus", "national pts", "absence", "direct elo", "NT matches", "NT share", "NT lineup level"])
print(df.to_string(index=False))

df.insert(1, "club", store.teams().set_index("team_id").name[TEAM]); df["team"] = df["team"].astype(int); df.to_csv(sys.argv[3], index=False)
