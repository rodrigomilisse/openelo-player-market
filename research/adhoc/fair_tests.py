"""Fair tests of each factor: equal-spread calibration, then weight x1.5/x2 and spread x2/x3. Usage: fair.py STAGE"""
import sys, json, time; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
import fit_light as fl
COMMON = dict(share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2, national_scale=100.0, output="weighted", team_weight=0.7)
SNAPS = [d for d in fl.days if d >= fl.D(pd.Timestamp("2018-07-01"))][::12]
ROWS, COLLECT = [], [False]
_orig = v2.Player.published
def _pub(self, day, c):
    if COLLECT[0]:
        ROWS.append(dict(minutes=self.bonus(day, c), goals=self.output_points(c),
                         absence=-(self.uncapped_discount() if self.v.absence_mode != "capped" else self.discount)))
    return _orig(self, day, c)
v2.Player.published = _pub
def measure(over):
    var = v2.Variant(**{**fl.BASE, **COMMON, **over}); ROWS.clear(); COLLECT[0] = True
    for pid in fl.tracked: v2.series(pid, var, fl.ctx, SNAPS)
    COLLECT[0] = False
    df = pd.DataFrame(ROWS); df["m+a"] = df.minutes + df.absence
    return df
def calibrated(over, col, target, keys):
    sd = measure(over)[col].std(); k = target / sd
    return {**over, **{key: over[key] * k for key in keys}}
def weighted(over, w, keys):
    return {**over, **{key: over[key] * w for key in keys}}
GOAL = ("goal_scale", "assist_scale"); MIN = ("bonus_scale",)
# the owner's intended order at the top (tiers, not strict)
INT = [("Harry Kane", 27, 1), ("Michael Olise", 27, 1), ("Erling Haaland", 281, 1), ("Luis Díaz", 27, 1), ("Ousmane Dembélé", 583, 1),
       ("Declan Rice", 11, 2), ("William Saliba", 11, 2), ("João Neves", 583, 2), ("Nuno Mendes", 583, 2), ("Achraf Hakimi", 583, 2), ("Gabriel", 11, 2),
       ("Rodri", 281, 3), ("Joshua Kimmich", 27, 3)]
snap = fl.D(pd.Timestamp("2026-07-07")); _pl = store.players(); _apps = fl.ctx.appearances.copy(); _apps["day"] = _apps.game_id.map(fl.ctx.day)
_ids = []
for n, t, tier in INT:
    c = _apps[(_apps.team_id == t) & (_apps.day >= snap - 365) & (_apps.minutes > 0) & _apps.player_id.isin(_pl[_pl.name == n].player_id)].player_id.value_counts()
    _ids.append(int(c.index[0]))
def intended(over):
    var = v2.Variant(**{**fl.BASE, **COMMON, **over}); r = []
    for pid in _ids:
        s = v2.series(pid, var, fl.ctx, [snap]); r.append(float(s.rating.iloc[0]))
    tiers = pd.Series([x[2] for x in INT]); rk = pd.Series(r).rank(ascending=False)
    return round(float(tiers.rank().corr(rk.rank())), 3), int(rk[12]), int(rk[4])      # corr, Kimmich's rank, Dembélé's rank among the 13
def run(name, over):
    t = time.time(); m = fl.evaluate(over); c, kim, dem = intended(over)
    print("RESULT\t" + json.dumps({"variant": name, "C7 A": round(m["C7 A"], 3), "C7 B": round(m["C7 B"], 3), "fit": round(m["rank fit"], 3),
                                   "held": round(m["rank held-out"], 3), "intended": c, "Kimmich#": kim, "Dembele#": dem}), flush=True)
if __name__ == "__main__":
    stage = sys.argv[1]
    A = dict(COMMON, squad_window=True, window=50, bonus_scale=400.0, goal_scale=226.0, assist_scale=113.0, absence_mode="window", absence_window=150, absence_scale=2.0)
    G1 = {**A}; G2 = {**A, "output_per_team_match": 60}
    if stage == "goals_minutes":
        g1 = measure(G1); target_goal = g1.goals.std(); print("per-90 goal sd", round(target_goal, 1), flush=True)
        G3 = calibrated(G2, "goals", target_goal, GOAL); print("calibrated goal scale", round(G3["goal_scale"]), round(G3["assist_scale"]), flush=True)
        run("goals per 90 (226/113)", G1); run("goals per club match, raw 226/113", G2); run("goals per club match, equal spread", G3)
        run("... weight x1.5", weighted(G3, 1.5, GOAL)); run("... weight x2", weighted(G3, 2.0, GOAL))
        S0 = measure(G3); tma, tm = S0["m+a"].std(), S0.minutes.std()
        print("two-term sd: minutes", round(tm, 1), "minutes+absence", round(tma, 1), flush=True)
        single = {**G3, "squad_window": False, "window": 150, "absence_scale": 0.0}
        S1 = calibrated(single, "minutes", tma, MIN); S2 = calibrated(single, "minutes", tm, MIN)
        run("two terms", G3); run("single term, equal spread to the two terms", S1); run("single term, equal spread to minutes alone", S2)
        run("single (equal two terms) weight x1.5", weighted(S1, 1.5, MIN)); run("single weight x2", weighted(S1, 2.0, MIN))
        for k in (1.0, 3.0, 4.0): run(f"two terms, absence {k:g} per missed match", {**G3, "absence_scale": k})
    else:
        g1 = measure(G1); target_goal = g1.goals.std(); G3 = calibrated(G2, "goals", target_goal, GOAL)
        S0 = measure(G3); tma, tm = S0["m+a"].std(), S0.minutes.std()
        single = {**G3, "squad_window": False, "window": 150, "absence_scale": 0.0}; S1 = calibrated(single, "minutes", tma, MIN)
        tm1 = measure(S1).minutes.std(); tg = measure(G3).goals.std()
        if stage == "strength":
            for D in (800, 400):
                c = calibrated({**S1, "minutes_strength": True, "strength_d": float(D)}, "minutes", tm1, MIN); run(f"minutes by club strength D{D}", c)
                if D == 400: run("... weight x1.5", weighted(c, 1.5, MIN)); run("... weight x2", weighted(c, 2.0, MIN))
            for D in (200, 130):
                run(f"... spread x{400 // D if D == 200 else 3} (D{D})", calibrated({**S1, "minutes_strength": True, "strength_d": float(D)}, "minutes", tm1, MIN))
        if stage in ("goal_club", "goal_opp"):
            kind = "club" if stage == "goal_club" else "opp"
            for D in (800, 400):
                c = calibrated({**G3, "goal_scaling": kind, "goal_d": float(D)}, "goals", tg, GOAL); run(f"goals by {kind} D{D}", c)
                if D == 400: run("... weight x1.5", weighted(c, 1.5, GOAL)); run("... weight x2", weighted(c, 2.0, GOAL))
            for D in (200, 130):
                run(f"... spread x{2 if D == 200 else 3} (D{D})", calibrated({**G3, "goal_scaling": kind, "goal_d": float(D)}, "goals", tg, GOAL))
        if stage == "comp":
            c = calibrated({**G3, "goal_scaling": "comp", "goal_comp_power": 1.0}, "goals", tg, GOAL); run("goals by competition (stage weights)", c)
            run("... weight x1.5", weighted(c, 1.5, GOAL)); run("... weight x2", weighted(c, 2.0, GOAL))
            for pw in (2.0, 3.0): run(f"... spread x{int(pw)} (power {int(pw)})", calibrated({**G3, "goal_scaling": "comp", "goal_comp_power": pw}, "goals", tg, GOAL))
            for pw in (1.0, 2.0, 3.0): run(f"minutes weighted by competition, power {int(pw)}", {**G3, "match_importance": True, "importance_power": pw})
