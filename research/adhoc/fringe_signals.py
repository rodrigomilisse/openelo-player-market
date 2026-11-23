"""What separates the fit fringe players at top clubs whom national coaches pick from those they do not?
Group: top-20 club by team rating, pecking order rank 12+ when fit, in a squad in the last 6 weeks.
Pooled over 2022 World Cup, 2024 Euro + Copa, 2026 World Cup. No information after the snapshot.
    python adhoc/fringe_signals.py   # from research/, about 1-2 minutes
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0])
tr = q("SELECT player_id, date, from_team_id, to_team_id, fee_eur FROM transfer"); tr["date"] = pd.to_datetime(tr.date)

def extra(c, snap):
    snap = pd.Timestamp(snap); day = int((snap - store.EPOCH).days)
    rating = tm[tm.day < day].groupby("team_id").rating.last()
    hist = lineup[(lineup.national == 0) & (lineup.date < snap) & (lineup.date >= snap - pd.Timedelta(days=3 * 365))]
    rows = {}
    for p, team in zip(c.player_id, c.team_id):
        h = hist[hist.player_id == p].sort_values("date")
        lg = h[h.type == "domestic_league"]
        prev = lg[lg.team_id != team]
        prev_club = rating.get(prev.team_id.mode().iloc[0], np.nan) if len(prev) else np.nan
        prev_rate = prev.starter.mean() if len(prev) >= 10 else np.nan
        long_rate = lg.tail(40).starter.mean()          # last 40 matchday squads, any club, up to 3 years
        cont = h[h.type == "international_cup"]
        f = tr[(tr.player_id == p) & (tr.date < snap) & (tr.date >= snap - pd.Timedelta(days=3 * 365))].fee_eur.max()
        used = (h[h.starter == 0].minutes > 0).mean() if (h.starter == 0).any() else np.nan
        rows[p] = dict(prev_club=prev_club, prev_rate=prev_rate, long_rate=long_rate,
                       cont_starts=cont.starter.sum(), fee=np.log1p(f) if pd.notna(f) else 0.0, used_sub=used)
    return c.join(pd.DataFrame.from_dict(rows, orient="index"), on="player_id")

EV = {"2022": ("2022-11-01", ["FIWC"]), "2024": ("2024-06-01", ["EURO", "COPA"]), "2026": ("2026-06-01", ["FIWC"])}
parts = []
for label, (snap, comps) in EV.items():
    c = spells(snapshot(snap, comps), snap)
    g = c[(c.band <= 20) & (c.rank2 >= 12) & c.recent].copy()
    g = extra(g, snap); g["event"] = label
    parts.append(g); print(f"{label}: {len(g)} fit fringe players at top-20 clubs, {int(g.selected.sum())} selected", flush=True)
g = pd.concat(parts, ignore_index=True)
g["age_u23"] = (g.age < 23).astype(float)
F = {"national-team history (2 years)": "nt", "pecking order, last 40 squads any club (3 years)": "long_rate",
     "start rate at previous club": "prev_rate", "previous club rating": "prev_club", "transfer fee paid (3 years)": "fee",
     "continental starts (3 years)": "cont_starts", "comes on when on the bench": "used_sub", "goals per 90": "goals90",
     "current pecking order (rank)": "order2", "availability (injury spells)": "avail2", "club rating": "club",
     "age under 23 (analysis only)": "age_u23"}
print(f"\nAUC inside the group (selected vs not), {len(g)} players, {int(g.selected.sum())} selected; 0.5 = no information")
print(f"  {'signal':52}{'pooled':>8}{'same nation':>13}{'coverage':>10}")
for name, col in F.items():
    x = g[g[col].notna()]
    pooled = auc(x[col].values, x.selected.values)
    w = t = 0
    for _, n in x.groupby(["event", "citizenship"]):
        a, b = n[n.selected][col].values, n[~n.selected][col].values
        w += (a[:, None] > b[None, :]).sum() + 0.5 * (a[:, None] == b[None, :]).sum(); t += len(a) * len(b)
    print(f"  {name:52}{pooled:8.2f}{(w / t if t else np.nan):13.2f}{len(x) / len(g):10.0%}")
print("\nselected vs not, means:")
print(g.groupby("selected")[list(F.values())].mean().T.round(2).to_string())
