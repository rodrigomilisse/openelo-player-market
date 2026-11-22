"""Single-term minutes with a recency kernel, and a player-by-player look at the goal-factor options.
Run from research/ with PYTHONPATH set to this folder:  kernel_tests.py kernel_a | kernel_b | analysis
"""
import sys
sys.path.insert(0, ".")
import pandas as pd
import fair
from fair import MIN, GOAL
import player_v2 as v2
import fit_light as fl

COMMON = fair.COMMON
A = dict(COMMON, squad_window=True, window=50, bonus_scale=400.0, goal_scale=226.0, assist_scale=113.0,
         absence_mode="window", absence_window=150, absence_scale=2.0)
G1 = {**A}
G2 = {**A, "output_per_team_match": 60}

stage = sys.argv[1]
g1 = fair.measure(G1)
tg, tma = g1.goals.std(), g1["m+a"].std()
print("per-90 two-term: goal sd", round(tg, 1), "minutes+absence sd", round(tma, 1), flush=True)

def single(H):
    over = {**G1, "squad_window": False, "window": 400, "absence_scale": 0.0, "minutes_half_life": float(H)}
    return fair.calibrated(over, "minutes", tma, MIN)

if stage == "kernel_a":
    fair.run("two terms (per-90 goals)", G1)
    for H in (25, 50):
        fair.run(f"single term, recency half-life {H} matches", single(H))
elif stage == "kernel_b":
    for H in (75, 100, 150):
        fair.run(f"single term, recency half-life {H} matches", single(H))
elif stage == "analysis":
    G3 = fair.calibrated(G2, "goals", tg, GOAL)
    cfgs = {
        "per 90 goals": G1,
        "per club match": G3,
        "x2 weight (club match)": fair.weighted(G3, 2.0, GOAL),
        "opposition D200": fair.calibrated({**G3, "goal_scaling": "opp", "goal_d": 200.0}, "goals", tg, GOAL),
        "opposition D400 x2": fair.weighted(fair.calibrated({**G3, "goal_scaling": "opp", "goal_d": 400.0}, "goals", tg, GOAL), 2.0, GOAL),
        "club D130": fair.calibrated({**G3, "goal_scaling": "club", "goal_d": 130.0}, "goals", tg, GOAL),
    }
    names = [x[0] for x in fair.INT]
    out = {}
    for k, c in cfgs.items():
        var = v2.Variant(**{**fl.BASE, **COMMON, **c})
        out[k] = [round(float(v2.series(pid, var, fl.ctx, [fair.snap]).rating.iloc[0])) for pid in fair._ids]
    d = pd.DataFrame(out, index=names)
    print("RATINGS")
    print(d.to_string())
    print("RANKS among the 13")
    print(d.rank(ascending=False).astype(int).to_string())
