"""Refined coach term vs the current one, judged by per-group calibration of national-team selection.

coach v2 (one term): per player at his current club, his last 40 FIT club matches (any competition, up to
3 years; injury spells = 4+ club matches in a row out of the matchday squad, excluded); credit start 1,
came on 0.3, unused or left out 0; each match weighted by competition (continental 2, league 1, cups 0.5)
x opponent strength 2^((opponent - own team) / 200), clipped to [0.25, 4]. Rank among the full squad.
before: start rate when in the squad, league matches in the last 365 days, rank among the full squad.
Both + club + 200 x availability (injury spells) + 100 x in a squad in the last 6 weeks.
    python adhoc/coach_term.py   # from research/, about 2-3 minutes
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/nt_cutoff.py").read().split("for label, (snap")[0].replace('exec(open("adhoc/availability_check.py").read().split("', '#'))
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0])
src = open("adhoc/nt_cutoff.py").read(); exec(src[src.index("def predicted"):src.rindex("for label, (snap")])
TMM = ctx.team_matches[["game_id", "team_id", "day", "rating", "opp_rating"]]
CW = {"international_cup": 2.0, "domestic_league": 1.0}

def coach_v2(snap):
    snap = pd.Timestamp(snap); d1 = int((snap - store.EPOCH).days); d0 = d1 - 3 * 365
    tmm = TMM[(TMM.day >= d0) & (TMM.day < d1)].merge(games[["game_id", "type"]], on="game_id")
    tmm["w"] = tmm.type.map(CW).fillna(0.5) * np.clip(2.0 ** ((tmm.opp_rating - tmm.rating) / 200), 0.25, 4)
    lu = lineup[(lineup.national == 0) & (lineup.date < snap) & (lineup.date >= snap - pd.Timedelta(days=3 * 365))]
    lg = lu[lu.type == "domestic_league"]
    cur = lg.sort_values("date").groupby("player_id").tail(1).set_index("player_id").team_id
    out = []
    for team, tg in tmm.groupby("team_id"):
        tg = tg.sort_values("day").reset_index(drop=True)
        tl = lu[lu.team_id == team]
        gi = {g: i for i, g in enumerate(tg.game_id)}
        squad = cur[cur == team].index
        for p in squad:
            mine = tl[tl.player_id == p]
            if mine.empty: continue
            idx = np.array([gi[g] for g in mine.game_id if g in gi], int)
            if len(idx) == 0: continue
            n = len(tg); ins = np.zeros(n, bool); ins[idx] = True
            cr = np.zeros(n); m = mine[mine.game_id.isin(gi)]
            cr[[gi[g] for g in m.game_id]] = np.where(m.starter == 1, 1.0, np.where(m.minutes > 0, 0.3, 0.0))
            first = idx.min(); inj = np.zeros(n, bool); i = first
            while i < n:
                if not ins[i]:
                    k = i
                    while k < n and not ins[k]: k += 1
                    if k - i >= 4: inj[i:k] = True
                    i = k
                else: i += 1
            fit = np.where(~inj[first:])[0][-40:] + first
            if len(fit) < 5: continue
            w = tg.w.values[fit]
            out.append((p, team, float(cr[fit] @ w / w.sum())))
    o = pd.DataFrame(out, columns=["player_id", "team_id", "rate_v2"])
    o["rank_v2"] = o.groupby("team_id").rate_v2.rank(ascending=False, method="min")
    return o

EV = {"2022": ("2022-11-01", ["FIWC"]), "2024": ("2024-06-01", ["EURO", "COPA"]), "2026": ("2026-06-01", ["FIWC"])}
rows = []
for label, (snap, comps) in EV.items():
    c = spells(snapshot(snap, comps), snap)
    c = c.merge(coach_v2(snap)[["player_id", "rank_v2"]], on="player_id", how="left")
    c["order_v2"] = order_t(c.rank_v2.fillna(99))
    c["recent"] = c.recent.astype(float)
    base = c.club + 200 * c.avail2 + 100 * c.recent
    M = {"before k=250": base + 250 * c.order, "v2 k=250": base + 250 * c.order_v2, "v2 k=400": base + 400 * c.order_v2}
    P = {k: predicted(c, s) for k, s in M.items()}
    G = {"fit fringe, top-10 club (rank 13+)": (c.band <= 10) & (c.rank_order >= 13) & (c.recent > 0),
         "fit regular, club 11-40 (rank 1-6)": (c.band > 10) & (c.band <= 40) & (c.rank_order <= 6) & (c.recent > 0),
         "regular, club 41-150": (c.band > 40) & (c.band <= 150) & (c.rank_order <= 6),
         "regular, club 150+": (c.band > 150) & (c.rank_order <= 6),
         "injury spells, available <70%": c.avail2 < .7,
         "defenders": c.position == "Defender", "midfielders": c.position == "Midfield", "attackers": c.position == "Attack"}
    for g, m in G.items():
        rows.append(dict(event=label, group=g, n=int(m.sum()), actual=c.selected[m].mean(), **{k: P[k][m].mean() for k in M}))
    rows.append(dict(event=label, group="PRECISION (all)", n=len(c), actual=np.nan, **{k: (c.selected & P[k]).sum() / P[k].sum() for k in M}))
    rows.append(dict(event=label, group="AUC (all)", n=len(c), actual=np.nan, **{k: np.nanmean([auc(s.loc[x.index].values, x.selected.values) for _, x in c.groupby("citizenship")]) for k, s in M.items()}))
    # confound check: inside the fringe group, v2 order among players at their club 2+ years (no previous club in the window)
    fr = c[G["fit fringe, top-10 club (rank 13+)"] | ((c.band <= 20) & (c.rank_order >= 12) & (c.recent > 0))]
    print(f"{label}: done ({len(c)} candidates)", flush=True)
    C = globals().setdefault("FR", []); C.append(fr.assign(event=label))
t = pd.DataFrame(rows)
pd.set_option("display.width", 200)
for g, x in t.groupby("group", sort=False):
    print(f"\n{g}"); print(x.drop(columns="group").round(3).to_string(index=False))
fr = pd.concat(FR)
lg = lineup[(lineup.national == 0)]
print(f"\nfringe at top-20 clubs, pooled {len(fr)}: AUC of v2 order {auc(-fr.rank_v2.fillna(99).values, fr.selected.values):.2f}, before {auc(-fr.rank_order.values, fr.selected.values):.2f}")
