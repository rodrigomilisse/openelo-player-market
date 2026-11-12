"""Light evaluation of player_v2 constants, for iterating by hand (not a search).

    .venv/bin/python fit_light.py '{"x1": {}, "x2": {"bonus_scale": 400}}'   # overrides on BASE
    FIT_SAMPLE=0.3 ...                                                        # share of tracked players

Scores against age-adjusted Transfermarkt values (linear:2). Rank correlation is
reported before 2023 (the fit period) and from 2023 (held out); C7 on all moves.
The built context is cached in data/raw/cache/, so a run costs a few seconds per variant.
"""
import os, sys, json, time, math, pickle, random
os.environ.setdefault("OPENELO_TM_AGE_ADJUST", "linear:2")
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import player_v2 as v2, player_checks as pc, store, team_checks, candidate as c

BASE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16,
            national="clubs", bonus_scale=400.0, national_scale=100.0)
SAMPLE, SPLIT = float(os.environ.get("FIT_SAMPLE", "1")), "2023-01-01"
TEAM = json.loads(os.environ.get("FIT_TEAM", "{}"))   # team-constant overrides, e.g. {"process_noise": 3}
CACHE = store.RAW_DIR / "cache" / ("context" + "".join(f"_{k}{v}" for k, v in sorted(TEAM.items())) + ".pkl")

t = time.time()
if CACHE.exists():
    ctx = pickle.loads(CACHE.read_bytes())
else:
    ctx = v2.Context(c.team_constants().with_(**TEAM))
    CACHE.parent.mkdir(exist_ok=True); CACHE.write_bytes(pickle.dumps(ctx, protocol=5))
print(f"context {time.time()-t:.0f}s", flush=True)

CASE = {"Rodri": 357565, "Wirtz": 598577, "Bruno": 240306, "Kane": 132098}
tracked = sorted(pc.tracked_ids() | set(CASE.values()))
if SAMPLE < 1:
    random.Random(1).shuffle(tracked); tracked = sorted(set(tracked[:int(len(tracked) * SAMPLE)]) | set(CASE.values()))
days = team_checks.month_starts()
D = pc.day_of
sets = {"A": set(pc.set_a_ids()), "B": set(pc.set_b_groups())}
moves = {n: pc.substantial_moves(p) for n, p in sets.items()}
cover = {n: pc.Coverage(p) for n, p in sets.items()}
vals = store.valuations(); vals = vals[vals.player_id.isin(tracked)]
vals["month"] = pd.to_datetime(vals.date).dt.to_period("M")
monthly = []
for pid, g in vals.groupby("player_id"):
    m = g.groupby("month").value_eur.mean()
    m = m.reindex(pd.period_range(m.index.min(), m.index.max(), freq="M")).ffill()
    for per in m.index[::3]:
        later = per + 12
        if later in m.index and m[per] > 0 and m[later] > 0:
            monthly.append((pid, D(per.to_timestamp()), D(later.to_timestamp()), math.log(m[later] / m[per])))
split_day = D(pd.Timestamp(SPLIT))
print(f"{len(tracked)} players, {len(monthly)} candidate pairs", flush=True)

def evaluate(over: dict) -> dict:
    var = v2.Variant(**{**BASE, **over})
    t0 = time.time()
    allp = pd.concat([v2.series(p, var, ctx, days) for p in tracked])
    ser = pc.RatingSeries(allp)
    out = {}
    for n in sets:
        sub = allp[allp.player_id.isin(cover[n].days.keys())]
        out[f"C7 {n}"] = pc.directional(moves[n], pc.RatingSeries(sub), cover[n], 6, 6)["share"]
    rows = []
    for pid, d0, d1, dv in monthly:
        r0, r1 = ser.at(pid, d0), ser.at(pid, d1)
        if r0 is None or r1 is None: continue
        if not (cover["A"].played_between(pid, d0, d1) or cover["B"].played_between(pid, d0, d1)): continue
        rows.append((d0 < split_day, r1 - r0, dv))
    p = pd.DataFrame(rows, columns=["train", "dr", "dv"])
    rho = lambda q: float(q.dr.rank().corr(q.dv.rank()))
    out["rank fit"], out["rank held-out"] = rho(p[p.train]), rho(p[~p.train])
    out["pairs"] = f"{p.train.sum()}/{(~p.train).sum()}"
    for name, pid in CASE.items():
        s = allp[(allp.player_id == pid) & (allp.day == D(pd.Timestamp("2026-01-01")))]
        out[f"gap {name} 26-01"] = round(float(s.rating.iloc[0] - s.team_rating.iloc[0])) if len(s) else None
    out["secs"] = round(time.time() - t0)
    return out

if __name__ == "__main__":
    variants = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"base": {}}
    table = {}
    for name, over in variants.items():
        table[name] = evaluate(over); print(name, table[name]["secs"], "s", flush=True)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(table).round(3).to_string())
