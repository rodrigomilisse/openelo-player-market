"""Compares player_v2 variants on the case players and on agreement with Transfermarkt.

    .venv/bin/python compare_variants.py                       # the four ideas alone
    .venv/bin/python compare_variants.py '{"name": "{\"absence\": true}"}'   # any variants, as JSON
"""
import sys, time, json, math
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import player_v2 as v2, player_checks as pc, store, team_checks, candidate as c
V = v2.Variant
variants = {
 "baseline, no fill": V(fill=False), "baseline": V(),
 "A split": V(split=True), "B split+weighted": V(split=True, weighted=True),
 "C absence": V(absence=True), "D selection": V(selection=True),
}
if len(sys.argv) > 1:
    variants = {k: V(**json.loads(v)) for k, v in json.loads(sys.argv[1]).items()}
t = time.time(); ctx = v2.Context(c.team_constants()); print("context", round(time.time()-t), "s", flush=True)
CASE = {"Rodri": 357565, "Wirtz": 598577, "Isak": None, "Bruno": 240306, "Müller": None, "Kane": 132098}
pl = store.players().merge(store.query("select player_id, count(*) n from appearance group by player_id"), on="player_id")
for n, full in (("Isak", "Alexander Isak"), ("Müller", "Thomas Müller")):
    CASE[n] = int(pl[pl.name == full].sort_values("n", ascending=False).iloc[0].player_id)
tracked = pc.tracked_ids() | set(CASE.values())
days = team_checks.month_starts()
D = lambda s: pc.day_of(s)
moves = {n: pc.substantial_moves(p) for n, p in (("A", set(pc.set_a_ids())), ("B", set(pc.set_b_groups())))}
cover = {n: pc.Coverage(p) for n, p in (("A", set(pc.set_a_ids())), ("B", set(pc.set_b_groups())))}
vals = store.valuations(); vals = vals[vals.player_id.isin(tracked)]
vals["month"] = pd.to_datetime(vals.date).dt.to_period("M")
def gap(s, date):
    r = s[s.day == D(date)]
    return round(float(r.rating.iloc[0] - r.team_rating.iloc[0])) if len(r) else None
def at(s, date):
    r = s[s.day == D(date)]
    return float(r.rating.iloc[0]) if len(r) else None
out = []
for name, var in variants.items():
    t = time.time()
    allp = pd.concat([v2.series(p, var, ctx, days) for p in sorted(tracked)])
    cs = {n: allp[allp.player_id == p] for n, p in CASE.items()}
    wirtz_inj = cs["Wirtz"][(cs["Wirtz"].day >= D("2022-07-01")) & (cs["Wirtz"].day <= D("2023-07-01"))]
    row = {"variant": name,
      "Rodri gap 25-01": gap(cs["Rodri"], "2025-01-01"), "Rodri gap 25-07": gap(cs["Rodri"], "2025-07-01"), "Rodri gap 26-01": gap(cs["Rodri"], "2026-01-01"),
      "Wirtz worst gap in injury": round(float((wirtz_inj.rating - wirtz_inj.team_rating).min())), "Wirtz gap 24-01": gap(cs["Wirtz"], "2024-01-01"),
      "Wirtz move Jul→Oct 25": round(at(cs["Wirtz"], "2025-10-01") - at(cs["Wirtz"], "2025-07-01")),
      "Isak move Sep→Oct 25": round(at(cs["Isak"], "2025-10-01") - at(cs["Isak"], "2025-09-01")),
      "Bruno mean gap 21-26": round(float((cs["Bruno"][cs["Bruno"].day >= D("2021-01-01")].rating - cs["Bruno"][cs["Bruno"].day >= D("2021-01-01")].team_rating).mean())),
      "Kane mean gap 16-23": round(float((lambda k: (k.rating - k.team_rating).mean())(cs["Kane"][(cs["Kane"].day >= D("2016-01-01")) & (cs["Kane"].day < D("2023-07-01"))]))),
      "Müller worst gap 2015": round(float((lambda m: (m.rating - m.team_rating).min())(cs["Müller"][(cs["Müller"].day >= D("2014-07-01")) & (cs["Müller"].day <= D("2016-01-01"))])))}
    snap = allp.assign(forward_rating=allp.rating)
    for n in ("A", "B"):
        sub = snap[snap.player_id.isin(cover[n].days.keys() | set())]
        r = pc.directional(moves[n], pc.RatingSeries(sub), cover[n], 6, 6)
        row[f"C7 set {n}"] = round(r["share"], 3)
    # strict: Spearman of 12-month changes
    ser = pc.RatingSeries(snap)
    pairs = []
    for pid, g in vals.groupby("player_id"):
        m = g.groupby("month").value_eur.mean()
        m = m.reindex(pd.period_range(m.index.min(), m.index.max(), freq="M")).ffill()
        for per in m.index[::3]:
            later = per + 12
            if later not in m.index or m[per] <= 0 or m[later] <= 0: continue
            d0 = D(per.to_timestamp()); d1 = D(later.to_timestamp())
            r0, r1 = ser.at(pid, d0), ser.at(pid, d1)
            if r0 is None or r1 is None: continue
            if not (cover["A"].played_between(pid, d0, d1) or cover["B"].played_between(pid, d0, d1)): continue
            pairs.append((r1 - r0, math.log(m[later] / m[per])))
    p = pd.DataFrame(pairs, columns=["dr", "dv"])
    row["Spearman Δ12m"] = round(float(p.dr.rank().corr(p.dv.rank())), 3)
    row["pairs"] = len(p)
    out.append(row); print(name, round(time.time()-t), "s", flush=True)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30)
f = pd.DataFrame(out).set_index("variant").T
print(f.to_string())
