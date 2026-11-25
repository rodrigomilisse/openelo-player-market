"""Goal factors are centred (goal_r0) so the average goal across all club matches keeps factor 1.
Candidate options on the 7-club table, each shifted so the mean rating of all these players equals
the base (same average points given out). Plus: our club ratings vs clubelo at 2025-06-01.
    python adhoc/candidate_options.py   # from research/, about 3-4 minutes
"""
import sys, pickle; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current.pkl").read_bytes())
CAND = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
            bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
            national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=226.0, assist_scale=113.0,
            absence_mode="window", absence_window=150, absence_scale=2.0)
import os
ONLY = os.environ.get("ONLY")
OPT = {"base": {},
       "minutes x competition": {"match_importance": True},
       "minutes x competition x opponent": {"match_importance": True, "big_game": True},
       "minutes at club where earned (D400)": {"minutes_strength": True, "strength_d": 400.0},
       "minutes at club where earned (D800)": {"minutes_strength": True, "strength_d": 800.0},
       "goals x opposition (D200)": {"goal_scaling": "opp", "goal_d": 200.0, "goal_r0": 1647.0},
       "goals x own club (D200)": {"goal_scaling": "club", "goal_d": 200.0, "goal_r0": 1713.0},
       "goals x opposition (D400)": {"goal_scaling": "opp", "goal_d": 400.0, "goal_r0": 1624.0}}
if ONLY: OPT = {k: v for k, v in OPT.items() if k == "base" or k.startswith(ONLY)}
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 583: "PSG", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
pl = store.players().set_index("player_id")
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
pids = [(int(p), t) for t in CLUBS for p in apps[(apps.team_id == t) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique()
        if pl.position.get(p) != "Goalkeeper"]
R = {}
for name, over in OPT.items():
    var = v2.Variant(**{**CAND, **over}); r = {}
    for p, t in pids:
        s = v2.series(p, var, ctx, [snap])
        if not s.empty and int(s.team_id.iloc[0]) == t: r[p] = float(s.rating.iloc[0])
    R[name] = pd.Series(r); print(name, "done", flush=True)
d = pd.DataFrame(R).dropna()
shift = d.mean() - d["base"].mean(); d = d - shift
print("\nshift applied to keep the mean equal:", shift.round(0).to_dict())
d["player"] = d.index.map(pl.name); d["club"] = d.index.map(dict(pids)).map(CLUBS); d["TM"] = d.index.map(tmv)
ranks = d[list(OPT)].rank(ascending=False, method="min").astype(int)
SHOW = ["Harry Kane", "Michael Olise", "Erling Haaland", "Luis Díaz", "Ousmane Dembélé", "Declan Rice", "William Saliba", "João Neves",
        "Nuno Mendes", "Achraf Hakimi", "Gabriel", "Rodri", "Joshua Kimmich", "Vitinha", "Désiré Doué", "Bradley Barcola", "Bukayo Saka",
        "Jonathan Tah", "Antoine Semenyo", "Marc Guéhi", "Leandro Trossard", "Luis Suárez", "Francisco Trincão", "Maxi Araújo"]
short = {k: k.replace("minutes ", "m ").replace("club where earned", "earned") for k in OPT}
t = ranks[d.player.isin(SHOW)].rename(columns=short); t.insert(0, "player", d.player); t.insert(1, "club", d.club); t["TM"] = d.TM
print("\nRANK among all outfield players of the 7 clubs"); print(t.sort_values("base").to_string(index=False))
print("\nrank corr with TM:", {short[k]: round(d[k].rank().corr(d.TM.rank()), 3) for k in OPT})
print("\nmean rating by club (after shift) minus base:"); print((d.groupby("club")[list(OPT)].mean().sub(d.groupby("club").base.mean(), axis=0)).round(0).rename(columns=short).to_string())

# club ratings vs clubelo (open, same Elo idea, its own European adjustment), 2025-06-01
day = (pd.Timestamp("2025-06-01") - store.EPOCH).days
ours = ctx.team_matches[ctx.team_matches.day < day].sort_values("day").groupby("team_id").apply(lambda g: g.rating.iloc[-1] + g.swing.iloc[-1])
ce = store.query("SELECT team_id, elo FROM clubelo WHERE date = (SELECT MAX(date) FROM clubelo WHERE date <= '2025-06-01')").set_index("team_id").elo
names = store.query("SELECT team_id, name FROM team").set_index("team_id").name
x = pd.DataFrame({"ours": ours, "clubelo": ce}).dropna(); x = x[x.clubelo >= 1750]
x["ours - clubelo"] = x.ours - x.clubelo; x["club"] = x.index.map(names)
x["ours - clubelo, centred"] = x["ours - clubelo"] - x["ours - clubelo"].median()
lc = store.query("SELECT t.team_id, co.country FROM team t JOIN competition co ON co.competition_id = t.domestic_competition_id").set_index("team_id").country
x["league"] = x.index.map(lc)
print("\nclubs with clubelo >= 1750 on 2025-06-01: our rating - clubelo, centred on the median, mean by league")
print(x.groupby("league")["ours - clubelo, centred"].agg(["mean", "size"]).round(0).sort_values("mean").to_string())
print(x[x.club.isin(["Sporting CP", "SL Benfica", "FC Porto", "PSV Eindhoven", "Galatasaray", "Bayern Munich", "Paris Saint-Germain",
                     "Manchester City", "Arsenal FC", "Liverpool FC", "Real Madrid", "Inter Milan"])][["club", "ours", "clubelo", "ours - clubelo, centred"]].round(0).sort_values("ours", ascending=False).to_string(index=False))
