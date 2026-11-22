"""Per-nation cut-off check: each model ranks a nation's candidates, its top N (N = players that nation
actually used) is the predicted squad. For player groups, compare the predicted selection rate with the
actual one: a calibrated model predicts each group as often as coaches pick it.
Also: within-nation rank correlation of each model, and of Transfermarkt value, with national-team history.
    python adhoc/nt_cutoff.py   # from research/, about 1 minute
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0])

def predicted(c, s):
    out = pd.Series(False, index=c.index)
    for _, g in c.groupby("citizenship"):
        n = int(g.selected.sum()); out[s.loc[g.index].sort_values(ascending=False).index[:n]] = True
    return out

for label, (snap, comps) in {"2024": ("2024-06-01", ["EURO", "COPA"]), "2026": ("2026-06-01", ["FIWC"])}.items():
    c = spells(snapshot(snap, comps), snap)
    vv = q("SELECT player_id, date, value_eur FROM valuation"); vv = vv[vv.date < snap].sort_values("date").groupby("player_id").tail(1)
    c["tm"] = np.log(c.player_id.map(dict(zip(vv.player_id, vv.value_eur))).fillna(1e4))
    M = {"club only": c.club, "order only": c.order2 + 0 * c.club,
         "club+160 order": c.club + 160 * c.order2,
         "+200 avail": c.club + 160 * c.order2 + 200 * c.avail2,
         "+200 avail +100 recent": c.club + 160 * c.order2 + 200 * c.avail2 + 100 * c.recent,
         "Transfermarkt": c.tm}
    P = {k: predicted(c, s) for k, s in M.items()}
    G = {"all": c.index == c.index,
         "fit fringe at top-10 club (rank 13+)": (c.band <= 10) & (c.rank2 >= 13) & c.recent,
         "fit regular at club 11-40 (rank 1-6)": (c.band > 10) & (c.band <= 40) & (c.rank2 <= 6) & c.recent,
         "regular at club 41-150": (c.band > 40) & (c.band <= 150) & (c.rank2 <= 6),
         "regular at club 150+": (c.band > 150) & (c.rank2 <= 6),
         "available <70% (injury spells)": c.avail2 < .7,
         "available 95%+": c.avail2 >= .95,
         "not in a squad, last 6 weeks": ~c.recent}
    print(f"\n=== {label}: {c.citizenship.nunique()} nations. Selection rate: actual vs each model's predicted (n)")
    print(f"  {'group':40}{'actual':>8}" + "".join(f"{k:>24}" for k in M))
    for g, m in G.items():
        print(f"  {g:40}{c.selected[m].mean():8.2f}" + "".join(f"{P[k][m].mean():24.2f}" for k in M) + f"   (n={int(m.sum())})")
    print("  precision of predicted squad (all)      " + "".join(f"{(c.selected & P[k]).sum() / P[k].sum():24.3f}" for k in M))
    k = c[c.nt_known]
    rc = lambda s: np.nanmean([s.loc[g.index].rank().corr(g.nt.rank()) for _, g in k.groupby("citizenship")])
    print(f"  within-nation rank corr with NT history ({k.citizenship.nunique()} nations): " + "  ".join(f"{n}: {rc(s):.2f}" for n, s in M.items()))
