"""National-team squad selection as a sanity check for player-rating ingredients.

Events: Euro + Copa America 2024 (snapshot 2024-06-01) and World Cup 2026 (snapshot 2026-06-01).
Candidates: outfield, aged 19-35, citizenship of a nation in the event, >= 5 covered league matches
for the current club since joining (within the year before). Selected = in any tournament line-up
(starting, on the bench or coming on).

Ingredients (current club, league matches since joining, within 365 days):
  club        team rating at the snapshot
  avail       matchday squads / club matches (not in the squad = injured or excluded)
  order       pecking order when available: rank by start rate in matches he was in the squad
              (shrunk: (starts + 1) / (squads + 2)); rank 1-6 -> 1, falling to 0 at rank 20
  goals       league + cup goals per 90 at clubs, shrunk to the pooled rate with 5 x 90 minutes
  nt          share of his nation's covered matches in the previous 2 years where he was in the
              squad (start 1, came on 0.6, unused 0.3, absent 0); circular by design, see notes
  fit         in the squad for >= 4 of the club's last 5 league matches before the snapshot

    python adhoc/nt_selection2.py         # from research/, about 1 minute
"""
import pickle, sqlite3, sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import store

ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current.pkl").read_bytes())
tm = ctx.team_matches[["team_id", "day", "rating"]].sort_values("day")
con = sqlite3.connect(store.RAW_DIR / "openelo_research.sqlite3")
q = lambda s: pd.read_sql(s, con)
games = q("SELECT g.game_id, g.date, g.national, g.competition_id, co.type FROM game g LEFT JOIN competition co USING(competition_id)")
games["date"] = pd.to_datetime(games.date)
lineup = q("SELECT game_id, player_id, team_id, starter FROM lineup").merge(games, on="game_id")
apps = q("SELECT game_id, player_id, minutes, goals FROM appearance")
lineup = lineup.merge(apps, on=["game_id", "player_id"], how="left").fillna({"minutes": 0, "goals": 0})
players = q("SELECT player_id, name, position, date_of_birth, citizenship FROM player")
players["dob"] = pd.to_datetime(players.date_of_birth, errors="coerce")
teams = q("SELECT team_id, name FROM team")
extra = q("SELECT l.game_id, l.player_id, l.team_id, l.starter, g.date, g.competition_id FROM nt_lineup l JOIN nt_game g USING(game_id)")
extra_m = q("SELECT game_id, player_id, minutes FROM nt_appearance")
extra = extra.merge(extra_m, on=["game_id", "player_id"], how="left").fillna({"minutes": 0})
extra["date"] = pd.to_datetime(extra.date)
names = dict(zip(teams.team_id, teams.name)) | dict(q("SELECT team_id, name FROM nt_team").values)
nat = pd.concat([lineup[lineup.national == 1][["game_id", "player_id", "team_id", "starter", "minutes", "date", "competition_id"]],
                 extra[["game_id", "player_id", "team_id", "starter", "minutes", "date", "competition_id"]]]).drop_duplicates(["game_id", "player_id"])
nat["nation"] = nat.team_id.map(names)
nat["credit"] = np.where(nat.starter == 1, 1.0, np.where(nat.minutes > 0, 0.6, 0.3))


def order_t(rank):
    return np.clip((20 - rank) / 14, 0, 1)


def snapshot(snap, comps):
    snap = pd.Timestamp(snap); day = int((snap - store.EPOCH).days)
    rating = tm[tm.day < day].groupby("team_id").rating.last()
    yr = lineup[(lineup.national == 0) & (lineup.date < snap) & (lineup.date >= snap - pd.Timedelta(days=365))]
    league = yr[yr.type == "domestic_league"]
    last = league.sort_values("date").groupby("player_id").tail(1)[["player_id", "team_id"]]
    joined = league.groupby(["player_id", "team_id"]).date.min().rename("joined").reset_index()
    cur = last.merge(joined, on=["player_id", "team_id"])
    rows = []
    for team, sq in cur.groupby("team_id"):
        tl = league[league.team_id == team]
        tg = tl[["game_id", "date"]].drop_duplicates().sort_values("date")
        last5 = set(tg.game_id.tail(5))
        per = []
        for p, j in zip(sq.player_id, sq.joined):
            n = int((tg.date >= j).sum())
            mine = tl[(tl.player_id == p) & (tl.date >= j)]
            squads, starts = len(mine), int(mine.starter.sum())
            fit = int(mine.game_id.isin(last5).sum()) >= 4
            per.append([p, team, n, squads, starts, (starts + 1) / (squads + 2), fit])
        per = pd.DataFrame(per, columns=["player_id", "team_id", "n", "squads", "starts", "rate", "fit"])
        per["rank_order"] = per.rate.where(per.squads >= 5, -1).rank(ascending=False, method="min")
        per["rank_starts"] = per.starts.rank(ascending=False, method="min")
        rows.append(per[per.n >= 5])
    c = pd.concat(rows)
    c["avail"] = c.squads / c.n
    c["order"] = order_t(c.rank_order); c["order_raw"] = order_t(c.rank_starts)
    c["club"] = c.team_id.map(rating)
    g = yr.groupby("player_id")[["goals", "minutes"]].sum()
    pooled = g.goals.sum() / (g.minutes.sum() / 90)
    c = c.merge(g, on="player_id", how="left").fillna({"goals": 0, "minutes": 0})
    c["goals90"] = (c.goals + 5 * pooled) / (c.minutes / 90 + 5)
    c = c.merge(players, on="player_id")
    c["age"] = (snap - c.dob).dt.days / 365.25
    c = c[(c.age >= 19) & (c.age <= 35) & (c.position != "Goalkeeper") & c.club.notna()].copy()
    ev = nat[nat.competition_id.isin(comps) & (nat.date >= snap) & (nat.date < snap + pd.Timedelta(days=60))]
    c["selected"] = c.player_id.isin(ev.player_id)
    c = c[c.citizenship.isin(ev.nation.unique())]
    prev = nat[(nat.date < snap) & (nat.date >= snap - pd.Timedelta(days=730))]
    games_per = prev.groupby("nation").game_id.nunique()
    cred = prev.groupby(["nation", "player_id"]).credit.sum().reset_index()
    cred["nt"] = cred.credit / cred.nation.map(games_per)
    c = c.merge(cred[["nation", "player_id", "nt"]], left_on=["citizenship", "player_id"], right_on=["nation", "player_id"], how="left").fillna({"nt": 0})
    c["nt_known"] = c.citizenship.map(games_per).fillna(0) >= 3
    k = c.groupby("citizenship").selected.sum()
    c = c[c.citizenship.isin(k[k >= 8].index)].reset_index(drop=True)
    c["band"] = c.team_id.map(rating.rank(ascending=False))
    return c


def auc(s, y):
    r = pd.Series(s).rank().values; y = np.asarray(y, bool)
    n1, n0 = y.sum(), (~y).sum()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan


def score(c, s):
    a, p = [], []
    for _, g in c.groupby("citizenship"):
        v = s.loc[g.index]
        a.append(auc(v.values, g.selected.values))
        n = int(g.selected.sum()); p.append(g.selected[v.sort_values(ascending=False).index[:n]].mean())
    return f"{np.nanmean(a):.3f}/{np.mean(p):.3f}"


def fringe_vs_regular(c, label):
    fr = c[(c.band <= 10) & (c.rank_order >= 13)]
    rg = c[(c.band > 10) & (c.band <= 40) & (c.rank_order <= 6)]
    w = l = 0
    for n in set(fr.citizenship) & set(rg.citizenship):
        a, b = fr[fr.citizenship == n].selected.values, rg[rg.citizenship == n].selected.values
        w += (b[:, None] & ~a[None, :]).sum(); l += (a[None, :] & ~b[:, None]).sum()
    print(f"  {label:34} top-10 fringe picked {fr.selected.mean():.2f} (n={len(fr)}), 11-40 regular {rg.selected.mean():.2f} "
          f"(n={len(rg)}); one-of-pair: regular {w}, fringe {l}")


EVENTS = {"2024 Euro + Copa": ("2024-06-01", ["EURO", "COPA"]), "2026 World Cup": ("2026-06-01", ["FIWC"])}
for label, (snap, comps) in EVENTS.items():
    c = snapshot(snap, comps)
    gap = c.drop_duplicates("team_id")
    print(f"\n=== {label}: {c.citizenship.nunique()} nations, {len(c)} candidates, {int(c.selected.sum())} selected  (AUC / top-N precision)")
    print("1) fringe at a top-10 club vs regular at a club ranked 11-40, by pecking order when available")
    fringe_vs_regular(c, "all")
    fringe_vs_regular(c[c.fit], "fit (in squad 4 of last 5)")
    fringe_vs_regular(c[c.fit & (c.avail >= 0.8)], "fit and available 80%+ of the year")

    print("2) pecking order and availability: club + k x order + a x avail")
    print(f"  {'':26}" + "".join(f"a={a:<12}" for a in (0, 100, 200, 400)))
    for name, col in (("order by starts (before)", "order_raw"), ("order when available", "order")):
        for k in (160, 250, 400):
            print(f"  {name:20} k={k:<4}" + "".join(f"{score(c, c.club + k * c[col] + a * c.avail):<14}" for a in (0, 100, 200, 400)))
    base = c.club + 250 * c.order + 200 * c.avail

    print("3) goals per 90 on top of club + 250 order + 200 avail (g points per goal per 90)")
    print("  plain  " + "  ".join(f"g={g}: {score(c, base + g * c.goals90)}" for g in (0, 100, 200, 400, 800)))
    lvl = (c.club - 1250).clip(lower=0) / 650
    print("  scaled " + "  ".join(f"g={g}: {score(c, base + g * c.goals90 * lvl)}" for g in (0, 100, 200, 400, 800)))
    fw = c.position == "Attack"
    for g in (0, 200, 400):
        s = base + g * c.goals90
        print(f"  g={g:<4} attackers only {score(c[fw], s[fw])}   others {score(c[~fw], s[~fw])}")

    print("4) national-team history (previous 2 years; circular: past squads predict the next one)")
    known = c[c.nt_known]
    b2 = base + 200 * c.goals90
    print(f"  nations with history: {known.citizenship.nunique()}   " +
          "  ".join(f"nt={n}: {score(known, b2[c.nt_known] + n * known.nt)}" for n in (0, 100, 200, 400, 800)))
