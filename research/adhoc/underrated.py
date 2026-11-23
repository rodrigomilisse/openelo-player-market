"""Which groups does the formula underrate in national-team selection? Formula = club + 250 x pecking order
(full squad, when in the squad) + 200 x availability + 100 x recent squad. Pooled 2022, 2024, 2026.
Per group: actual selected, predicted selected, missing = actual - predicted (players).
    python adhoc/underrated.py   # from research/, about 1-2 minutes
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/availability_check.py").read().split("for label, (snap")[0])
src = open("adhoc/nt_cutoff.py").read(); exec(src[src.index("def predicted"):src.rindex("for label, (snap")])
lc = q("SELECT t.team_id, co.country league FROM team t LEFT JOIN competition co ON co.competition_id = t.domestic_competition_id")
LEAGUE = dict(zip(lc.team_id, lc.league))
TOP5 = {"England", "Spain", "Germany", "Italy", "France"}
EUR2 = {"Portugal", "Netherlands", "Belgium", "Türkiye", "Scotland", "Austria", "Switzerland", "Greece", "Denmark", "Czech Republic",
        "Croatia", "Serbia", "Ukraine", "Russia", "Poland", "Sweden", "Norway", "Romania"}
def ltype(x):
    return "top-5 league" if x in TOP5 else "other European league" if x in EUR2 else \
        "Saudi Arabia" if x == "Saudi Arabia" else "Americas (Brazil, Argentina, US, Mexico)" if x in {"Brazil", "Argentina", "United States", "Mexico"} else \
        "Asia/Oceania (Japan, Korea, Australia)" if x in {"Japan", "Korea, South", "Australia"} else "other/unknown"

parts = []
for label, (snap, comps) in {"2022": ("2022-11-01", ["FIWC"]), "2024": ("2024-06-01", ["EURO", "COPA"]), "2026": ("2026-06-01", ["FIWC"])}.items():
    c = snapshot(snap, comps)
    c = spells(c, snap)
    s = c.club + 250 * c.order + 200 * c.avail2 + 100 * c.recent
    c["pred"] = predicted(c, s); c["event"] = label
    c["league"] = c.team_id.map(LEAGUE)
    parts.append(c); print(label, len(c), flush=True)
c = pd.concat(parts, ignore_index=True)
c["league type"] = c.league.map(ltype)
c["home or abroad"] = np.where(c.league == c.citizenship, "plays in his own country", "plays abroad")
c["age band"] = pd.cut(c.age, [18, 22, 25, 29, 32, 36], labels=["19-22", "23-25", "26-29", "30-32", "33-35"]).astype(str)
c["NT history"] = pd.cut(c.nt, [-.01, 0, .2, .5, 2], labels=["none", "some (<20%)", "regular (20-50%)", "core (50%+)"]).astype(str)
c.loc[~c.nt_known, "NT history"] = "nation not covered before"
c["club band x order"] = (pd.cut(c.band, [0, 10, 40, 150, 1e6], labels=["top-10", "11-40", "41-150", "150+"]).astype(str) + " club, rank " +
                          pd.cut(c.rank_order, [0, 6, 12, 99], labels=["1-6", "7-12", "13+"]).astype(str))
depth = c[c.band <= 40].groupby(["event", "citizenship"]).size()
c["nation depth"] = pd.cut(c.set_index(["event", "citizenship"]).index.map(depth).fillna(0).values, [-1, 5, 20, 60, 1e4],
                           labels=["0-5 players at top-40 clubs", "6-20", "21-60", "60+"]).astype(str)
c["position"] = c.position.fillna("?")
out = []
for dim in ["league type", "home or abroad", "age band", "NT history", "club band x order", "nation depth", "position"]:
    for g, x in c.groupby(dim):
        out.append((dim, g, len(x), int(x.selected.sum()), int(x.pred.sum()), int(x.selected.sum() - x.pred.sum())))
t = pd.DataFrame(out, columns=["dimension", "group", "n", "actual", "predicted", "missing"])
pd.set_option("display.width", 200)
for d, x in t.groupby("dimension", sort=False):
    print(f"\n{d}"); print(x.drop(columns="dimension").sort_values("missing").to_string(index=False))
# the strongest joint cell: age x league type
x = c.groupby(["age band", "league type"]).agg(n=("selected", "size"), actual=("selected", "sum"), predicted=("pred", "sum"))
x["missing"] = x.actual - x.predicted
print("\nage x league type, |missing| >= 8"); print(x[x.missing.abs() >= 8].sort_values("missing").to_string())
x = c.groupby(["NT history", "club band x order"]).agg(n=("selected", "size"), actual=("selected", "sum"), predicted=("pred", "sum"))
x["missing"] = x.actual - x.predicted
print("\nNT history x club band, |missing| >= 8"); print(x[x.missing.abs() >= 8].sort_values("missing").to_string())
