import sys, pickle; sys.path.insert(0, ".")
import pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_process_noise3.pkl").read_bytes())
B = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs", bonus_scale=400.0,
         share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2, national_scale=100.0, output="weighted")
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
names = store.players().set_index("player_id").name
for team, club in ((27, "Bayern"), (281, "City"), (11, "Arsenal")):
    rows = []
    for pid in apps[(apps.team_id == team) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique():
        a = v2.series(int(pid), v2.Variant(**B), ctx, [snap]); b = v2.series(int(pid), v2.Variant(**B, big_game=True), ctx, [snap])
        if a.empty or int(a.team_id.iloc[0]) != team: continue
        rows.append((names[pid], round(a.rating.iloc[0]), round(b.rating.iloc[0])))
    d = pd.DataFrame(rows, columns=["player", "now", "big"]).sort_values("big", ascending=False).head(10)
    d["rank now"] = [sorted([r[1] for r in rows], reverse=True).index(x) + 1 for x in d.now]
    print(club, "|", "; ".join(f"{r.player} {r.big} ({r.big - r.now:+d}, was #{r._4})" for r in d.itertuples()))
