"""Player table. coach = importance-weighted start share (continuous) over the last 40 fit club matches,
all competitions: continental x3, league x1, cups x0.3, x opponent strength 2^((opp - own)/150) clipped [0.2, 5];
came on 0.3. Earlier version used rank buckets (rank 1-6 = max), which tied every regular.
Old header: the current formula at 2026-06-01: club + 250 x pecking order + 200 x availability
+ 100 x recent squad (no national or goal term yet), for a mix of clubs, with Transfermarkt value.
    python adhoc/player_table.py   # from research/, under a minute
"""
import sys; sys.path.insert(0, ".")
exec(open("adhoc/nt_selection2.py").read().split("def order_t")[0])
def order_t(rank): return np.clip((20 - rank) / 14, 0, 1)
SNAP = pd.Timestamp("2026-07-06"); day = int((SNAP - store.EPOCH).days)
CLUBS = ["Bayern Munich", "Paris Saint-Germain", "Manchester City", "Arsenal FC", "Sporting CP", "Brighton & Hove Albion", "SC Braga"]
ids = {n: t for t, n in zip(teams.team_id, teams.name) if n in CLUBS}
rating = tm[tm.day < day].groupby("team_id").rating.last()
yr = lineup[(lineup.national == 0) & (lineup.date < SNAP) & (lineup.date >= SNAP - pd.Timedelta(days=365))]
lg = yr[yr.type == "domestic_league"]
cur = lg.sort_values("date").groupby("player_id").tail(1)
recent = set(yr[yr.date >= SNAP - pd.Timedelta(days=70)].player_id) | set(nat[nat.date >= SNAP - pd.Timedelta(days=42)].player_id)
allc = lineup[(lineup.national == 0) & (lineup.date < SNAP) & (lineup.date >= SNAP - pd.Timedelta(days=3 * 365))]
rows = []
TMM = ctx.team_matches[["game_id", "team_id", "day", "rating", "opp_rating"]].merge(games[["game_id", "type", "date"]], on="game_id")
TMM["w"] = TMM.type.map({"international_cup": 3.0, "domestic_league": 1.0}).fillna(0.3) * np.clip(2.0 ** ((TMM.opp_rating - TMM.rating) / 150), 0.2, 5)
def coach(p, t):
    tg = TMM[(TMM.team_id == t) & (TMM.date < SNAP) & (TMM.date >= SNAP - pd.Timedelta(days=3 * 365))].sort_values("day")
    mine = allc[(allc.player_id == p) & (allc.team_id == t)]
    tg = tg[tg.date >= mine.date.min()]
    ins = tg.game_id.isin(mine.game_id).values
    cr = tg.game_id.map(dict(zip(mine.game_id, np.where(mine.starter == 1, 1.0, np.where(mine.minutes > 0, 0.3, 0.0))))).fillna(0).values
    inj = np.zeros(len(tg), bool); i = 0
    while i < len(tg):
        if not ins[i]:
            k = i
            while k < len(tg) and not ins[k]: k += 1
            if k - i >= 4: inj[i:k] = True
            i = k
        else: i += 1
    f = np.where(~inj)[0][-40:]
    w = tg.w.values[f]
    return float(cr[f] @ w / w.sum()) if len(f) else 0.0
for name, t in ids.items():
    tl = lg[lg.team_id == t]; tg = tl[["game_id", "date"]].drop_duplicates().sort_values("date")
    squad = cur[cur.team_id == t].player_id
    per = []
    for p in squad:
        first = allc[(allc.player_id == p) & (allc.team_id == t)].date.min()   # joined this club (3-year look-back)
        mine = tl[tl.player_id == p]; j = max(first, SNAP - pd.Timedelta(days=365))
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
    d["coach"] = [coach(p, t) for p in d.player_id]; d["club"] = name; d["club_rating"] = rating.get(t)
    rows.append(d)
d = pd.concat(rows).merge(players[["player_id", "name", "position", "dob"]], on="player_id")
vals = q("SELECT player_id, date, value_eur FROM valuation"); vals["date"] = pd.to_datetime(vals.date)
v = vals[vals.date < SNAP].sort_values("date").groupby("player_id").tail(1)
d["TM €m"] = d.player_id.map(dict(zip(v.player_id, v.value_eur))) / 1e6
d["age"] = ((SNAP - d.dob).dt.days / 365.25).round(0)
d["order pts"] = 250 * d.coach; d["avail pts"] = 200 * d.avail; d["recent pts"] = 100 * d.recent
d["rating"] = d.club_rating + d["order pts"] + d["avail pts"] + d["recent pts"]
# goals: club goals per 90 over the year, shrunk with 5 x 90 at the pooled rate; 226 per goal per 90 x club level
g = yr.groupby("player_id")[["goals", "minutes"]].sum(); pooled = g.goals.sum() / (g.minutes.sum() / 90)
d = d.join(g, on="player_id"); d[["goals", "minutes"]] = d[["goals", "minutes"]].fillna(0)
d["g90"] = d.goals / (d.minutes / 90 + 5)   # shrunk towards 0, so players who do not play get none
d["goal pts"] = 226 * d.g90 * np.clip((d.club_rating - 1250) / 850, 0, 1.2)
# national term: squad credit over the nation's covered matches in 2 years (start 1, on 0.6, unused 0.3)
# x nation strength (mean club rating of that nation's 11 best squad players by club, (x - 1600) / 400), scale 300
prev = nat[(nat.date < SNAP) & (nat.date >= SNAP - pd.Timedelta(days=730))]
gp = prev.groupby("nation").game_id.nunique()
cred = prev.groupby(["nation", "player_id"]).credit.sum().reset_index(); cred["share"] = cred.credit / cred.nation.map(gp)
cur_club = cur.set_index("player_id").team_id.map(rating)
strength = prev.drop_duplicates(["nation", "player_id"]).assign(r=lambda x: x.player_id.map(cur_club)).groupby("nation").r.mean()
cred["nt_pts"] = 100 * cred.share * np.clip((cred.nation.map(strength) - 1600) / 200, 0, None)   # decided rule: scale 100
best = cred.sort_values("nt_pts").groupby("player_id").tail(1).set_index("player_id")
d["NT"] = d.player_id.map(best.nation); d["nt pts"] = d.player_id.map(best.nt_pts).fillna(0)
d["rating"] = d.rating + d["goal pts"] + d["nt pts"]
d = d[d.position != "Goalkeeper"].sort_values("rating", ascending=False)
d["rank TM"] = d["TM €m"].rank(ascending=False, method="min")
cols = ["name", "club", "position", "age", "rating", "club_rating", "order pts", "avail pts", "recent pts", "goal pts", "nt pts", "NT", "TM €m", "rank TM"]
out = d[cols].head(50).round(0); out.insert(0, "#", range(1, len(out) + 1))
print(out.to_string(index=False))
mix = pd.concat([x.head(5) for _, x in d.groupby("club")] + [x.tail(5) for _, x in d.groupby("club")]).drop_duplicates("player_id").sort_values("rating", ascending=False)
mix = mix[cols + ["n", "minutes", "goals"]].round(0); mix.insert(0, "#", range(1, len(mix) + 1))
print("\nMIX: 5 highest and 5 lowest of each club"); print(mix.to_string(index=False))
INT = ["Harry Kane","Michael Olise","Erling Haaland","Luis Díaz","Ousmane Dembélé","Declan Rice","William Saliba","João Neves","Nuno Mendes","Achraf Hakimi","Gabriel","Rodri","Joshua Kimmich","Luis Suárez","Vitinha"]
d["#"] = range(1, len(d) + 1)
print("\nowner's list:"); print(d[d.name.isin(INT)][["#"] + cols].round(0).to_string(index=False))
print(f"\nrank correlation with TM (all {len(d)} outfield players): {d.rating.rank().corr(d['TM €m'].rank()):.2f}")
