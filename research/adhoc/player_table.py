"""Player table with the current formula at 2026-06-01: club + 250 x pecking order + 200 x availability
+ 100 x recent squad (no national or goal term yet), for a mix of clubs, with Transfermarkt value.
    python adhoc/player_table.py   # from research/, under a minute
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/nt_selection2.py").read().split("def order_t")[0])
def order_t(rank): return np.clip((20 - rank) / 14, 0, 1)
SNAP = pd.Timestamp("2026-06-01"); day = int((SNAP - store.EPOCH).days)
CLUBS = ["Bayern Munich", "Paris Saint-Germain", "Manchester City", "Arsenal FC", "Sporting CP", "Brighton & Hove Albion", "SC Braga"]
ids = {n: t for t, n in zip(teams.team_id, teams.name) if n in CLUBS}
rating = tm[tm.day < day].groupby("team_id").rating.last()
yr = lineup[(lineup.national == 0) & (lineup.date < SNAP) & (lineup.date >= SNAP - pd.Timedelta(days=365))]
lg = yr[yr.type == "domestic_league"]
cur = lg.sort_values("date").groupby("player_id").tail(1)
recent = set(yr[yr.date >= SNAP - pd.Timedelta(days=42)].player_id)
rows = []
for name, t in ids.items():
    tl = lg[lg.team_id == t]; tg = tl[["game_id", "date"]].drop_duplicates().sort_values("date")
    squad = cur[cur.team_id == t].player_id
    per = []
    for p in squad:
        mine = tl[tl.player_id == p]; j = mine.date.min()
        seq = tg[tg.date >= j].game_id.values; ins = np.isin(seq, mine.game_id.values)
        inj = np.zeros(len(seq), bool); i = 0
        while i < len(seq):
            if not ins[i]:
                k = i
                while k < len(seq) and not ins[k]: k += 1
                if k - i >= 4: inj[i:k] = True
                i = k
            else: i += 1
        st = dict(zip(mine.game_id, mine.starter))
        fitg = seq[~inj]
        per.append((p, len(seq), (sum(st.get(g, 0) for g in fitg) + 1) / (len(fitg) + 2), 1 - inj.mean() if len(seq) else 0, p in recent))
    d = pd.DataFrame(per, columns=["player_id", "n", "rate", "avail", "recent"])
    d = d[d.n >= 5]
    d["rank"] = d.rate.rank(ascending=False, method="min"); d["club"] = name; d["club_rating"] = rating.get(t)
    rows.append(d)
d = pd.concat(rows).merge(players[["player_id", "name", "position", "dob"]], on="player_id")
vals = q("SELECT player_id, date, value_eur FROM valuation"); vals["date"] = pd.to_datetime(vals.date)
v = vals[vals.date < SNAP].sort_values("date").groupby("player_id").tail(1)
d["TM €m"] = d.player_id.map(dict(zip(v.player_id, v.value_eur))) / 1e6
d["age"] = ((SNAP - d.dob).dt.days / 365.25).round(0)
d["order pts"] = 250 * order_t(d["rank"]); d["avail pts"] = 200 * d.avail; d["recent pts"] = 100 * d.recent
d["rating"] = d.club_rating + d["order pts"] + d["avail pts"] + d["recent pts"]
d = d[d.position != "Goalkeeper"].sort_values("rating", ascending=False)
d["rank TM"] = d["TM €m"].rank(ascending=False, method="min")
cols = ["name", "club", "position", "age", "rating", "club_rating", "order pts", "avail pts", "recent pts", "TM €m", "rank TM"]
out = d[cols].head(50).round(0); out.insert(0, "#", range(1, len(out) + 1))
print(out.to_string(index=False))
print(f"\nrank correlation with TM (all {len(d)} outfield players): {d.rating.rank().corr(d['TM €m'].rank()):.2f}")
