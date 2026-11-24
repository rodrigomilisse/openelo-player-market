"""1) The best line through the overlap: logistic regression with one intercept per nation (each nation
has its own cut-off), fitted on one tournament and tested on the other. Weights are shown in club-rating
points (coefficient / club coefficient), i.e. how many points of club rating each ingredient is worth.
4) Value vs selection with no look-ahead: value before the tournament predicting selection; selection
predicting the value change over the following year, against players of similar value and age.
    python adhoc/nt_line.py   # from research/, about 1-2 minutes
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0])
vv = q("SELECT player_id, date, value_eur FROM valuation"); vv["date"] = pd.to_datetime(vv.date)

def value_at(ids, day):
    x = vv[vv.date < day].sort_values("date").groupby("player_id").tail(1)
    return ids.map(dict(zip(x.player_id, x.value_eur)))

def fit(X, y, nat, iters=60):
    nations = sorted(set(nat)); D = (nat[:, None] == np.array(nations)[None, :]).astype(float)
    A = np.hstack([X, D]); b = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-A @ b)); W = p * (1 - p) + 1e-9
        H = A.T @ (A * W[:, None]) + 1e-3 * np.eye(len(b)); b += np.linalg.solve(H, A.T @ (y - p))
    return b[:X.shape[1]]

def within_auc(c, s):
    return np.nanmean([auc(s.loc[g.index].values, g.selected.values) for _, g in c.groupby("citizenship")])

EV = {"2022 World Cup": ("2022-11-01", ["FIWC"]), "2024 Euro + Copa": ("2024-06-01", ["EURO", "COPA"]), "2026 World Cup": ("2026-06-01", ["FIWC"])}
C = {}
for label, (snap, comps) in EV.items():
    c = spells(snapshot(snap, comps), snap)
    c["v0"] = value_at(c.player_id, pd.Timestamp(snap)); c["v1"] = value_at(c.player_id, pd.Timestamp(snap) + pd.Timedelta(days=365))
    c["lv"] = np.log(c.v0.fillna(1e4)); c["recent"] = c.recent.astype(float)
    c["order_x_club"] = c.order2 * (c.club - 1600) / 200
    C[label] = c
    print(f"{label}: {c.citizenship.nunique()} nations, {len(c)} candidates, {int(c.selected.sum())} selected", flush=True)

SETS = {"club, order, avail, recent": ["club", "order2", "avail2", "recent"],
        "+ order x club level": ["club", "order2", "avail2", "recent", "order_x_club"],
        "+ goals per 90": ["club", "order2", "avail2", "recent", "goals90"],
        "+ NT history": ["club", "order2", "avail2", "recent", "nt"]}
print("\n1) Fitted line. Weights in club-rating points; AUC on the OTHER tournament (2024 <-> 2026); hand-set = club + 160 order + 200 avail + 100 recent")
for name, cols in SETS.items():
    for tr, te in (("2024 Euro + Copa", "2026 World Cup"), ("2026 World Cup", "2024 Euro + Copa")):
        a, b = C[tr], C[te]
        mu, sd = a[cols].mean(), a[cols].std()
        w = fit(((a[cols] - mu) / sd).values, a.selected.values.astype(float), np.asarray(a.citizenship, dtype=object)) / sd.values
        pts = w / w[0]
        s = b[cols].values @ w
        hand = b.club + 160 * b.order2 + 200 * b.avail2 + 100 * b.recent
        print(f"  {name:28} fit {tr[:4]}: " + "  ".join(f"{k}={p:.0f}" if k != "club" else "club=1" for k, p in zip(cols, pts)) +
              f"   test {te[:4]} AUC {within_auc(b, pd.Series(s, index=b.index)):.3f} (hand-set {within_auc(b, hand):.3f})")

print("\n4) Value and selection, no look-ahead")
for label, c in C.items():
    r = c.club + 160 * c.order2 + 200 * c.avail2 + 100 * c.recent
    both = (r.rank(pct=True) + c.lv.rank(pct=True))
    print(f"  {label}: value before -> selection AUC {within_auc(c, c.lv):.3f}; our rating {within_auc(c, r):.3f}; both averaged {within_auc(c, both):.3f}")
    d = c[c.v0.notna() & c.v1.notna() & (c.v0 > 0)].copy()
    if len(d) < 200: print("    (no value a year later)"); continue
    d["chg"] = np.log(d.v1 / d.v0)
    d["cell"] = pd.qcut(d.lv, 10, duplicates="drop").astype(str) + pd.cut(d.age, [18, 23, 27, 31, 36]).astype(str)
    d["res"] = d.chg - d.groupby("cell").chg.transform("mean")
    sel = d[d.selected].res.mean(); non = d[~d.selected].res.mean()
    print(f"    selection -> value change next year (vs same value decile and age): selected {np.exp(sel)-1:+.1%}, not selected {np.exp(non)-1:+.1%}  (n={len(d)})")
    d["r"] = (c.club + 160 * c.order2 + 200 * c.avail2)[d.index]
    d["rres"] = d.r - d.groupby("cell").r.transform("mean")
    top, bot = d[d.rres > d.rres.quantile(.75)].res.mean(), d[d.rres < d.rres.quantile(.25)].res.mean()
    print(f"    our rating above TM (top quarter vs bottom, same value and age) -> value change next year: {np.exp(top)-1:+.1%} vs {np.exp(bot)-1:+.1%}")
