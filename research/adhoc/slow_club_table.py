"""The previous player_v2 candidate with the regular team Elo and with a slow seasonal club Elo
(each club's rating = mean of its rating over the previous 365 days; the recruitment-level idea).
Candidate: direct model, team weight 0.7, minutes bonus 400 x (share - top-16 squad reference) over the
last 50 matchday squads (starts full, subs minutes/length, keeper reference 1), national 100 (20 matches,
2 years, unused 0.2), goals 226 and assists 113 per 90 (prior 5 x 90), absence 2 per missed match in 150.
    python adhoc/slow_club_table.py   # from research/, about 1-3 minutes
"""
import sys, pickle, copy; sys.path.insert(0, ".")
import numpy as np, pandas as pd, player_v2 as v2, store
P = store.RAW_DIR / "cache" / "context_current.pkl"
ctx = pickle.loads(P.read_bytes()); slow = pickle.loads(P.read_bytes())
tm = slow.team_matches.sort_values(["team_id", "day"]).copy()
tm["r"] = tm.rating + tm.swing
def roll(g):
    d, r = g.day.values, g.r.values
    lo = np.searchsorted(d, d - 365, side="left"); cs = np.concatenate([[0], np.cumsum(r)])
    return pd.Series((cs[np.arange(len(d)) + 1] - cs[lo]) / (np.arange(len(d)) + 1 - lo), index=g.index)
tm["rating"] = tm.groupby("team_id", group_keys=False).apply(roll); tm["swing"] = 0.0
slow.team_matches = tm.drop(columns="r")
slow.by_team = {t: g.reset_index(drop=True) for t, g in slow.team_matches.groupby("team_id")}
CAND = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16, national="clubs",
            bonus_scale=400.0, share_rule="starter", gk_reference=True, nt_matches=20, nt_days=730, nt_credit=0.2,
            national_scale=100.0, output="weighted", team_weight=0.7, goal_scale=226.0, assist_scale=113.0,
            absence_mode="window", absence_window=150, absence_scale=2.0)
var = v2.Variant(**CAND)
CLUBS = {27: "Bayern", 11: "Arsenal", 281: "City", 583: "PSG", 336: "Sporting", 1237: "Brighton", 1075: "Braga"}
snap = (pd.Timestamp("2026-07-07") - store.EPOCH).days
apps = ctx.appearances.copy(); apps["day"] = apps.game_id.map(ctx.day)
pl = store.players().set_index("player_id")
vals = store.query("SELECT player_id, date, value_eur FROM valuation"); vals = vals[pd.to_datetime(vals.date) < "2026-07-07"]
tmv = vals.sort_values("date").groupby("player_id").value_eur.last() / 1e6
rows = []
for team, club in CLUBS.items():
    for pid in apps[(apps.team_id == team) & (apps.day >= snap - 365) & (apps.minutes > 0)].player_id.unique():
        a = v2.series(int(pid), var, ctx, [snap]); b = v2.series(int(pid), var, slow, [snap])
        if a.empty or b.empty or int(a.team_id.iloc[0]) != team or pl.position.get(pid) == "Goalkeeper": continue
        rows.append(dict(player=pl.name.get(pid, pid), club=club, regular=round(float(a.rating.iloc[0])), slow=round(float(b.rating.iloc[0])),
                         club_regular=round(float(a.team_rating.iloc[0])), club_slow=round(float(b.team_rating.iloc[0])), TM=tmv.get(pid, np.nan)))
    print(club, "done", flush=True)
d = pd.DataFrame(rows)
print("\nclub ratings (regular / slow):")
print(d.groupby("club")[["club_regular", "club_slow"]].first().sort_values("club_regular", ascending=False).to_string())
d["rank_club"] = d.groupby("club").regular.rank(ascending=False, method="first")
n = d.groupby("club").regular.transform("size")
pick = d[(d.rank_club <= 5) | (d.rank_club > n - 5)].copy()
pick["# regular"] = pick.regular.rank(ascending=False, method="min").astype(int)
pick["# slow"] = pick.slow.rank(ascending=False, method="min").astype(int)
print("\n" + pick.sort_values("regular", ascending=False)[["# regular", "# slow", "player", "club", "regular", "slow", "TM"]].to_string(index=False))
print("\nrank corr with TM, all outfield:", round(d.regular.rank().corr(d.TM.rank()), 2), "regular /", round(d.slow.rank().corr(d.TM.rank()), 2), "slow")
