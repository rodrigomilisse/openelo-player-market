import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
import player_v2 as v2, store, candidate as c
VD = v2.Variant(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs")
ctx = v2.Context(c.team_constants())
BAY = 27
snap = int(ctx.by_team[BAY].day.max()) + 1
date = store.EPOCH + pd.Timedelta(days=snap)
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day); apps["length"] = apps.game_id.map(ctx.length)
recent = apps[(apps.team_id == BAY) & (apps.day >= snap - 365) & (apps.minutes > 0)]
recent = recent.assign(share=np.minimum(recent.minutes, recent.length) / recent.length)
n_matches = ctx.by_team[BAY].query("day >= @snap - 365").shape[0]
agg = recent.groupby("player_id").agg(matches=("share", "size"), s=("share", "sum"))
agg["share"] = agg.s / n_matches
agg = agg.sort_values("share", ascending=False).head(22)
pl = store.players().set_index("player_id")
raw, adj = store.valuations(""), store.valuations("linear:2")
def tm(df, pid):
    d = df[(df.player_id == pid) & (df.date <= date.strftime("%Y-%m-%d"))].sort_values("date")
    return (d.value_eur.iloc[-1] / 1e6, d.date.iloc[-1]) if len(d) else (np.nan, None)
rows = []
for pid in agg.index:
    s = v2.series(int(pid), VD, ctx, [snap])
    if s.empty: continue
    r = s.iloc[-1]; v, vd = tm(raw, pid); a, _ = tm(adj, pid)
    age = (date - pd.Timestamp(pl.date_of_birth[pid])).days / 365.25
    rows.append((pl.name[pid], round(age, 1), agg.share[pid].round(2), round(r.rating), round(r.rating - r.team_rating), v, a, vd, int(r.team_id)))
df = pd.DataFrame(rows, columns=["player", "age", "share", "direct elo", "gap", "TM €M", "age-adj €M", "valued", "team_id"]).sort_values("direct elo", ascending=False)
print("as of", date.date(), "| Bayern team rating", round(ctx.by_team[BAY].query("day < @snap").pipe(lambda t: t.rating.iloc[-1] + t.swing.iloc[-1])))
print(df.drop(columns="team_id").to_string(index=False, float_format=lambda x: f"{x:.1f}"))
c_ = df[["direct elo", "TM €M"]].dropna(); a_ = df[["direct elo", "age-adj €M"]].dropna()
print("Spearman elo vs TM:", round(c_.rank().corr().iloc[0,1], 2), "| vs age-adj TM:", round(a_.rank().corr().iloc[0,1], 2))
