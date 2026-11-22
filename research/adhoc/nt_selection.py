"""Does club level + pecking order predict national-team squad selection, and at what weight?

For two tournaments (Euro/Copa/Asian Cup 2024 snapshot 2024-06-01; AFCON 25-26 and World Cup 2026
snapshot 2026-06-01): candidates are outfield players aged 19-35 with that citizenship and at least
5 covered league matches for their current club in the year before. Selected = in any tournament
line-up (starter or bench). Rating = current club team rating + k x trust, for three trust measures:
  share  starts / club league matches since he joined (raw share)
  rel    starts / the club's most-started player's starts (rotation divides out)
  rank   pecking order: rank 1-6 = 1, falling linearly to 0 at rank 20
Reports mean within-nation AUC and top-N precision, and how national coaches choose between a
top-club fringe player and a mid-club regular. Also the Transfermarkt table with bands by our team
rating and roles by pecking-order rank.

    python adhoc/nt_selection.py          # from research/, about 1-2 minutes (loads the cached context)
"""
import pickle, sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import store

ctx = pickle.loads((store.RAW_DIR / "cache" / "context_current.pkl").read_bytes())
tm = ctx.team_matches[["team_id", "day", "rating"]].sort_values("day")
import sqlite3; con = sqlite3.connect(store.RAW_DIR / "openelo_research.sqlite3")
q = lambda s: pd.read_sql(s, con)
games = q("SELECT g.game_id, g.date, g.national, g.competition_id, co.type FROM game g LEFT JOIN competition co USING(competition_id)")
games["date"] = pd.to_datetime(games.date)
lineup = q("SELECT game_id, player_id, team_id, starter FROM lineup").merge(games, on="game_id")
players = q("SELECT player_id, name, position, date_of_birth, citizenship FROM player")
players["dob"] = pd.to_datetime(players.date_of_birth, errors="coerce")
teams = q("SELECT team_id, name FROM team")
vals = q("SELECT player_id, date, value_eur FROM valuation"); vals["date"] = pd.to_datetime(vals.date)
nt_extra = q("SELECT l.game_id, l.player_id, l.team_id, l.starter, g.date, g.competition_id FROM nt_lineup l JOIN nt_game g USING(game_id)")
nt_extra["date"] = pd.to_datetime(nt_extra.date)
nt_names = dict(zip(teams.team_id, teams.name)) | dict(q("SELECT team_id, name FROM nt_team").values)
EPOCH = store.EPOCH


def team_rating(team, snap):
    d = int((snap - EPOCH).days)
    r = tm[(tm.team_id == team) & (tm.day < d)]
    return r.rating.iloc[-1] if len(r) else np.nan


def snapshot(snap, comps):
    snap = pd.Timestamp(snap)
    club = lineup[(lineup.national == 0) & (lineup.type == "domestic_league") & (lineup.date < snap) & (lineup.date >= snap - pd.Timedelta(days=365))]
    last = club.sort_values("date").groupby("player_id").tail(1)[["player_id", "team_id"]]
    joined = club.groupby(["player_id", "team_id"]).date.min().rename("joined").reset_index()
    cur = last.merge(joined, on=["player_id", "team_id"])
    rows = []
    for team, sq in cur.groupby("team_id"):
        tg = club[club.team_id == team][["game_id", "date"]].drop_duplicates()
        st = club[club.team_id == team].groupby("player_id").starter.sum()
        ranks = st.rank(ascending=False, method="min")
        for p, j in zip(sq.player_id, sq.joined):
            n = int((tg.date >= j).sum())
            if n < 5:
                continue
            rows.append((p, team, st.get(p, 0) / n, st.get(p, 0) / st.max(), ranks.get(p, 99)))
    c = pd.DataFrame(rows, columns=["player_id", "team_id", "share", "rel", "rank"])
    c["rank_t"] = np.clip((20 - c["rank"]) / 14, 0, 1)
    c["club"] = [team_rating(t, snap) for t in c.team_id]
    c = c.merge(players, on="player_id")
    c["age"] = (snap - c.dob).dt.days / 365.25
    c = c[(c.age >= 19) & (c.age <= 35) & (c.position != "Goalkeeper") & c.club.notna()]
    v = vals[vals.date < snap].sort_values("date").groupby("player_id").tail(1)[["player_id", "value_eur"]]
    c = c.merge(v, on="player_id", how="left")
    nt = lineup[(lineup.national == 1) & lineup.competition_id.isin(comps) & (lineup.date >= snap - pd.Timedelta(days=200))][["player_id", "team_id"]]
    nt = pd.concat([nt, nt_extra[nt_extra.competition_id.isin(comps) & (nt_extra.date.dt.year == snap.year)][["player_id", "team_id"]]])
    nt["nation"] = nt.team_id.map(nt_names)
    sel = nt.drop_duplicates("player_id")
    c["selected"] = c.player_id.isin(sel.player_id)
    nations = sel.nation.unique()
    c = c[c.citizenship.isin(nations)]
    # keep nations where at least 8 selected players are candidates (decent club coverage)
    k = c.groupby("citizenship").selected.sum()
    return c[c.citizenship.isin(k[k >= 8].index)].copy()


def auc(score, y):
    r = pd.Series(score).rank().values; y = np.asarray(y)
    n1, n0 = y.sum(), (~y).sum()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan


def evaluate(c, score):
    a, p = [], []
    for _, g in c.groupby("citizenship"):
        s = score.loc[g.index]
        a.append(auc(s.values, g.selected.values))
        n = int(g.selected.sum()); p.append(g.selected[s.sort_values(ascending=False).index[:n]].mean())
    return np.nanmean(a), np.mean(p)


SNAPS = {"2024 (Euro, Copa, Asian Cup)": ("2024-06-01", ["EURO", "COPA", "AFAC"]),
         "2026 (AFCON 25-26, World Cup)": ("2026-06-01", ["FIWC", "AFCN"])}
KS = [0, 80, 160, 250, 400, 800, 1600]
for label, (snap, comps) in SNAPS.items():
    c = snapshot(snap, comps)
    print(f"\n=== {label}: {c.citizenship.nunique()} nations, {len(c)} candidates, {int(c.selected.sum())} selected")
    print("mean within-nation AUC / top-N precision")
    print(f"  club rating only        {evaluate(c, c.club)[0]:.3f} / {evaluate(c, c.club)[1]:.3f}")
    for t in ("share", "rel", "rank_t"):
        print(f"  trust only ({t:6})     {evaluate(c, c[t])[0]:.3f} / {evaluate(c, c[t])[1]:.3f}")
    tv = c.value_eur.fillna(0)
    print(f"  Transfermarkt value     {evaluate(c, tv)[0]:.3f} / {evaluate(c, tv)[1]:.3f}")
    print("  club + k x trust   k:  " + "  ".join(f"{k:>11}" for k in KS))
    for t in ("share", "rel", "rank_t"):
        print(f"    {t:6}              " + "  ".join("{:.3f}/{:.3f}".format(*evaluate(c, c.club + k * c[t])) for k in KS))
    # top-club fringe vs mid-club regular, same nation
    order = c.drop_duplicates("team_id").sort_values("club", ascending=False).team_id.tolist()
    allteams = tm[tm.day < int((pd.Timestamp(snap) - EPOCH).days)].groupby("team_id").rating.last().sort_values(ascending=False)
    rk = {t: i + 1 for i, t in enumerate(allteams.index)}
    c["band"] = c.team_id.map(rk)
    fr = c[(c.band <= 10) & (c.rank_t < 0.5)]
    rg = c[(c.band > 10) & (c.band <= 40) & (c.rank_t >= 1)]
    gap = allteams.iloc[:10].median() - allteams.iloc[10:40].median()
    print(f"  team-rating gap, median top-10 vs median 11-40 clubs: {gap:.0f}")
    print(f"  selection rate: top-10 club fringe (rank 13+) {fr.selected.mean():.2f} (n={len(fr)}), "
          f"11-40 club regular (rank 1-6) {rg.selected.mean():.2f} (n={len(rg)})")
    w = l = 0
    for nat in set(fr.citizenship) & set(rg.citizenship):
        a, b = fr[fr.citizenship == nat].selected.values, rg[rg.citizenship == nat].selected.values
        w += (b[:, None] & ~a[None, :]).sum(); l += (a[None, :] & ~b[:, None]).sum()
    print(f"  pairs where coach picked exactly one: mid-club regular picked {w}, top-club fringe picked {l}")

    if label.startswith("2026"):
        c["club_band"] = pd.cut(c.band, [0, 10, 30, 60, 120, 10**6], labels=["top 10", "11-30", "31-60", "61-120", "rest"])
        c["role"] = pd.cut(c["rank"], [0, 6, 11, 16, 99], labels=["rank 1-6", "7-11", "12-16", "17+"])
        y = c[(c.age >= 23) & (c.age <= 29)]
        print("\nTM median value (EURm), all citizenships here, age 23-29: bands by OUR team rating, roles by pecking-order rank")
        print((y.pivot_table(index="club_band", columns="role", values="value_eur", aggfunc="median", observed=False) / 1e6).round(1).to_string())
        print(y.pivot_table(index="club_band", columns="role", values="value_eur", aggfunc="count", observed=False).to_string())
