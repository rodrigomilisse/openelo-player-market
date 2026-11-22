"""Is availability a proxy for pecking order? Injury-like absence = runs of >= SPELL consecutive missed
matchday squads; scattered omissions count as the coach's choice (not starting), not unavailability.
    python adhoc/availability_check.py   # from research/, about 1 minute
"""
import sys; sys.path.insert(0, ".")
src = open("adhoc/nt_selection2.py").read().split("EVENTS = ")[0]
exec(src)
SPELL = 4

def spells(c, snap):
    snap = pd.Timestamp(snap)
    yr = lineup[(lineup.national == 0) & (lineup.date < snap) & (lineup.date >= snap - pd.Timedelta(days=365))]
    league = yr[yr.type == "domestic_league"]
    recent = set(yr[yr.date >= snap - pd.Timedelta(days=42)].player_id)
    out = {}
    for team, sq in c.groupby("team_id"):
        tl = league[league.team_id == team]
        tg = tl[["game_id", "date"]].drop_duplicates().sort_values("date")
        for p in sq.player_id:
            mine = tl[tl.player_id == p]
            j = mine.date.min()
            seq = tg[tg.date >= j].game_id.values
            ins = np.isin(seq, mine.game_id.values)
            st = dict(zip(mine.game_id, mine.starter))
            inj = np.zeros(len(seq), bool); i = 0
            while i < len(seq):
                if not ins[i]:
                    k = i
                    while k < len(seq) and not ins[k]: k += 1
                    if k - i >= SPELL: inj[i:k] = True
                    i = k
                else: i += 1
            fitm = ~inj
            starts = sum(st.get(g, 0) for g in seq[fitm])
            out[p] = (1 - inj.mean(), (starts + 1) / (fitm.sum() + 2), p in recent)
    o = pd.DataFrame.from_dict(out, orient="index", columns=["avail2", "rate2", "recent"])
    c = c.join(o, on="player_id")
    c["rank2"] = c.groupby("team_id").rate2.rank(ascending=False, method="min")
    c["order2"] = order_t(c.rank2)
    return c

for label, (snap, comps) in {"2024": ("2024-06-01", ["EURO", "COPA"]), "2026": ("2026-06-01", ["FIWC"])}.items():
    c = spells(snapshot(snap, comps), snap)
    print(f"\n=== {label}  ({len(c)} candidates)")
    print("correlation with pecking order:  old avail vs old order %.2f | injury-spell avail vs new order %.2f | recent-squad vs new order %.2f"
          % (c.avail.corr(c.order), c.avail2.corr(c.order2), c.recent.astype(float).corr(c.order2)))
    c["ostr"] = pd.cut(c.order2, [-.01, .001, .999, 1.01], labels=["order 0 (rank 20+)", "middle", "order 1 (rank 1-6)"])
    c["astr"] = pd.cut(c.avail2, [-.01, .7, .95, 1.01], labels=["<70%", "70-95%", "95%+"])
    print("selection rate by injury-spell availability WITHIN each pecking-order level (n in brackets)")
    t = c.groupby(["ostr", "astr"], observed=False).selected.agg(["mean", "size"])
    print(t.unstack().round(2).to_string())
    print("recent squad (last 6 weeks) within order levels:")
    print(c.groupby(["ostr", "recent"], observed=False).selected.agg(["mean", "size"]).unstack().round(2).to_string())
    print("AUC/precision, club + 160 x order:")
    print("  old order + old avail:   " + "  ".join(f"a={a}:{score(c, c.club + 160*c.order + a*c.avail)}" for a in (0, 100, 200)))
    print("  new order + spell avail: " + "  ".join(f"a={a}:{score(c, c.club + 160*c.order2 + a*c.avail2)}" for a in (0, 100, 200, 400)))
    print("  new order + recent:      " + "  ".join(f"a={a}:{score(c, c.club + 160*c.order2 + a*c.recent)}" for a in (0, 100, 200)))
