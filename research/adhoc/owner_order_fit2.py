"""Can the rating's components reproduce the owner's orderings (per club, then combined)?
Components per player at 2026-07-07 from the current candidate (league redistribution 0.3 zero-sum, importance
weighted minutes, minutes relative to current club): club level, minutes bonus (scale 400), goals (226 per goal
per 90, opposition-weighted, no assists), national term (scale 100), absence discount (2 per missed match).
Players who moved after the data ends (July 2026) get their new club's rating and minutes rescaled to it.
Grid search over weights; agreement = Spearman with the owner's order (per club), and for the combined list
also the share of (listed, unlisted) pairs with the listed player higher.
    python adhoc/owner_order_fit.py   # from research/, about 1-2 minutes
"""
import sys, pickle, itertools; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current_league0.3zs.pkl").read_bytes())
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
CFG = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
           bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_credit=0.2,
           national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=226.0, assist_scale=113.0,
           absence_mode="window", absence_window=150, absence_scale=2.0, nt_days=1100, match_importance=True, big_game=True,
           minutes_strength=True, strength_d=400.0, strength_relative=True, goal_scaling="opp", goal_d=400.0, goal_r0=1624.0)
VAR = v2.Variant(**CFG)
got = {}; orig = v2.Player.published
def pub(self, day, context):
    got.update(base=self.rating(), absence=self.uncapped_discount(), minutes=self.bonus(day, context),
               nt=self.national_points(day, context), goals=self.output_points(context))
    return orig(self, day, context)
v2.Player.published = pub
TEAMS = {"Bayern": 27, "PSG": 583, "Barcelona": 131, "Real Madrid": 418, "Arsenal": 11, "Man City": 281, "Sporting": 336}
OWN = {"Bayern": ["Harry Kane", "Michael Olise", "Luis Díaz", "Dayot Upamecano", "Joshua Kimmich"],
       "Sporting": ["Altimira", "Luis Suárez", "Maxi Araújo", "Doumbia", "Iván Fresneda", "Nestory Irankunda", "Geny Catamo", "Rodrigo Zalazar"],
       "PSG": ["João Neves", "Vitinha", "Khvicha Kvaratskhelia", "Désiré Doué", "Ousmane Dembélé", "Nuno Mendes", "Achraf Hakimi", "Fabián Ruiz", "Willian Pacho", "Ferran"],
       "Barcelona": ["Lamine Yamal", "Raphinha", "Fermín López", "Pau Cubarsí", "Pedri", "Rodri", "Joan García", "Anthony Gordon", "Jules Koundé", "Dani Olmo"],
       "Real Madrid": ["Jude Bellingham", "Kylian Mbappé", "Arda Güler", "Thibaut Courtois", "Ousmane Diomande", "Federico Valverde", "Marc Cucurella",
                       "Bernardo Silva", "Vinicius Junior", "Aurélien Tchouaméni", "Endrick", "Ibrahima Konaté", "Dean Huijsen"],
       "Arsenal": ["Declan Rice", "William Saliba", "Gabriel", "David Raya", "Viktor Gyökeres", "Bukayo Saka", "Riccardo Calafiori", "Martin Ødegaard",
                   "Bruno Guimarães", "Ezri Konsa", "Jurriën Timber", "Christos Tzolis", "Noni Madueke"],
       "Man City": ["Erling Haaland", "Rayan Cherki", "Enzo Fernández", "Elliot Anderson", "Jérémy Doku", "Marc Guéhi", "Nico O'Reilly", "Antoine Semenyo",
                    "Gianluigi Donnarumma", "Joško Gvardiol"]}
COMBINED = ["Harry Kane", "Michael Olise", "Lamine Yamal", "Jude Bellingham", "Erling Haaland", "Declan Rice", "João Neves", "Vitinha", "William Saliba",
            "Gabriel", "Arda Güler", "Fermín López", "Khvicha Kvaratskhelia", "Désiré Doué", "Pau Cubarsí", "Pedri", "Rodri", "Thibaut Courtois",
            "Ousmane Dembélé", "Nuno Mendes", "Achraf Hakimi", "Luis Díaz", "Ousmane Diomande", "Federico Valverde", "Marc Cucurella", "Bernardo Silva",
            "Vinicius Junior", "Enzo Fernández"]
pl = store.players()
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
recent = apps[(apps.day >= snap - 400) & (apps.minutes > 0)]
mins = recent.groupby("player_id").minutes.sum()
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
def find(name):
    c = pl[pl.name == name]
    if c.empty: c = pl[pl.name.str.contains(name, case=False, regex=False)]
    c = c[c.player_id.isin(mins.index)]
    if c.empty: return None
    if name == "Gabriel": c = c[c.player_id.isin(recent[recent.team_id == 11].player_id)]
    if name == "Rodri": c = c[c.player_id.isin(recent[recent.team_id == 281].player_id)]
    return int(c.assign(v=c.player_id.map(tmv).fillna(0), m=c.player_id.map(mins)).sort_values(["v", "m"], ascending=False).player_id.iloc[0]) if len(c) else None
def club_rating(team):
    s = ctx.by_team[team]; b = s[s.day < snap]; return float(b.rating.iloc[-1] + b.swing.iloc[-1])
CR = {k: club_rating(t) for k, t in TEAMS.items()}
rows, missing = [], []
def comp(pid, club):
    s = v2.series(pid, VAR, ctx, [snap])
    if s.empty: return None
    old = float(s.team_rating.iloc[0]); new = CR[club]
    moved = int(s.team_id.iloc[0]) != TEAMS[club]
    return dict(player_id=pid, name=pl.set_index("player_id").name.get(pid), club=club, moved=moved,
                club_level=0.7 * (new - 1600), minutes=got["minutes"] * (2.0 ** ((old - new) / 400) if moved else 1.0),
                goals=got["goals"], nt=got["nt"], absence=got["absence"], TM=tmv.get(pid, np.nan))
listed = set()
for club, names in OWN.items():
    for i, n in enumerate(names):
        pid = find(n)
        if pid is None: missing.append(f"{n} ({club})"); continue
        r = comp(pid, club)
        if r is None: missing.append(f"{n} ({club})"); continue
        r["own_rank"] = i + 1; rows.append(r); listed.add(pid)
# unlisted players still at these clubs in the data (combined: should be lower)
for club, t in TEAMS.items():
    for pid in recent[recent.team_id == t].player_id.unique():
        pid = int(pid)
        if pid in listed or mins.get(pid, 0) < 900: continue
        s_ = ctx.by_team  # noqa
        r = comp(pid, club)
        if r is None or r["moved"]: continue
        r["own_rank"] = np.nan; rows.append(r)
d = pd.DataFrame(rows)
print("not found in the data:", missing)
print(f"{d.own_rank.notna().sum()} listed players, {d.own_rank.isna().sum()} unlisted players at these clubs")
X = d[["club_level", "minutes", "goals", "nt", "absence"]]
def spear(a, b): return pd.Series(a).rank().corr(pd.Series(b).rank())
GRID = dict(club=[0.5, 1.0, 1.5], minutes=[0, 0.5, 1, 1.5, 2, 3], goals=[0, 0.25, 0.5, 0.75, 1, 1.5, 2], nt=[0, 0.5, 1, 2, 3], absence=[0, 0.5, 1, 2])
combos = list(itertools.product(*GRID.values()))
CURRENT = (1.0, 1.0, 0.7, 1.0, 0.0)   # assists in at 0.7 (goals 158, assists 79), no absence
def score_club(sub, w):
    r = sub.club_level * w[0] + sub.minutes * w[1] + sub.goals * w[2] + sub.nt * w[3] - sub.absence * w[4]
    return spear(r.values, -sub.own_rank.values)
print("\nPER CLUB: Spearman with your order (1 = identical); current weights vs best weights (minutes, goals, NT, absence)")
best_all = {}
L = d[d.own_rank.notna()]
for club in OWN:
    sub = L[L.club == club]
    if len(sub) < 3: continue
    sc = [(score_club(sub, w), w) for w in combos if w[0] == 1.0]
    sc.sort(key=lambda x: -x[0]); b = sc[0]
    tm = spear(sub.TM.fillna(0).values, -sub.own_rank.values)
    print(f"  {club:12} n={len(sub):2}  current {score_club(sub, CURRENT):+.2f}  best {b[0]:+.2f} at minutes {b[1][1]}, goals {b[1][2]}, NT {b[1][3]}, absence {b[1][4]}   (TM value {tm:+.2f})")
    best_all[club] = sc[:15]
def score_comb(w):
    r = X @ np.array([w[0], w[1], w[2], w[3], -w[4]])
    lst = d.own_rank.notna()
    order = pd.Series(np.nan, index=d.index); order[lst] = [COMBINED.index(n) if n in COMBINED else len(COMBINED) for n in d.name[lst]]
    sp = spear(r[lst].values, -order[lst].values)
    hi = r[lst & order.lt(len(COMBINED))].values; lo = r[~lst].values
    pairs = (hi[:, None] > lo[None, :]).mean()
    return sp, pairs
res = sorted(((np.mean(score_comb(w)), score_comb(w), w) for w in combos), key=lambda x: -x[0])
print("\nCOMBINED: Spearman with your combined order (players outside it ranked after) | share of (your combined list, unlisted) pairs in the right order")
c0 = score_comb(CURRENT); print(f"  current weights: Spearman {c0[0]:+.2f}, pairs {c0[1]:.2f}")
for m, (sp, pr), w in res[:5]:
    print(f"  club {w[0]}, minutes {w[1]}, goals {w[2]}, NT {w[3]}, absence {w[4]}: Spearman {sp:+.2f}, pairs {pr:.2f}")
bw = res[0][2]
d["best"] = X @ np.array([bw[0], bw[1], bw[2], bw[3], -bw[4]])
d["current"] = X @ np.array([1, 1, 0.75, 1, -1])
d.to_csv("adhoc/owner_order_fit2.csv", index=False)
top = d[d.own_rank.notna()].sort_values("best", ascending=False)
print("\nCOMBINED with best weights (listed players), vs your order:")
for i, r in enumerate(top.itertuples(), 1):
    yo = COMBINED.index(r.name) + 1 if r.name in COMBINED else "-"
    print(f"  {i:2} {r.name:24} {r.club:12} yours {yo}  | minutes {r.minutes:+5.0f} goals {r.goals:4.0f} NT {r.nt:4.0f} absence {r.absence:4.0f}{'  (moved)' if r.moved else ''}")
