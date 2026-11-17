import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
import player_v2 as v2, store, candidate as c, player_checks as pc
V = v2.Variant(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs")
ctx = v2.Context(c.team_constants())
pl = store.players(); teams = store.teams().set_index("team_id").name
ids = {"Olise": int(pl[pl.name == "Michael Olise"].sort_values("player_id").iloc[0].player_id), "Bruno": 240306}
vals = store.valuations(False); adj = store.valuations(True)
for name, pid in ids.items():
    v = vals[vals.player_id == pid].sort_values("date")
    dates = pd.date_range("2019-07-01" if name == "Bruno" else "2021-07-01", "2026-05-01", freq="3MS")
    days = [pc.day_of(d) for d in dates]
    s = v2.series(pid, V, ctx, days).set_index("day")
    rows = []
    for d, day in zip(dates, days):
        if day not in s.index: continue
        r = s.loc[day]
        tm = v[v.date <= d.strftime("%Y-%m-%d")]; ta = adj[(adj.player_id == pid) & (adj.date <= d.strftime("%Y-%m-%d"))].sort_values("date")
        rows.append((d.strftime("%Y-%m"), teams.get(int(r.team_id), r.team_id), round(r.rating), round(r.team_rating), round(r.rating - r.team_rating), round(tm.value_eur.iloc[-1] / 1e6) if len(tm) else None, round(ta.value_eur.iloc[-1] / 1e6) if len(ta) else None))
    df = pd.DataFrame(rows, columns=["date", "club", "rating", "team", "gap", "TM €M", "TM adj"])
    df["Δrating"] = df.rating.diff(); df["Δ TM %"] = (df["TM €M"].pct_change() * 100).round()
    print(f"\n{name} (id {pid})"); print(df.to_string(index=False))
