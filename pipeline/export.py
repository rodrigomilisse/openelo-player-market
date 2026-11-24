"""Export OpenElo for the public site as static JSON (the site's read-API shapes, site README "Data contract").

    python export.py --out ../frontend/web/site/data

Runs the same models and constants as rate.py over the ingestion database, keeping each player's rating
after every club match (with its parts: club, selection, goals, national, absence) and each club's rating
history, then writes:

    meta.json  rankings.json  clubs.json  leagues.json  week.json  search.json
    players/<id>.json  clubs/<id>.json

Ids are slug-<provider id> (e.g. bruno-fernandes-1485), stable across runs. Market prices are not exported:
the site simulates them until the market exists. The files are the whole published state; a static host
serves them as they are.
"""
import argparse
import json
import re
import sys
import unicodedata
import warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "research"))   # last: research has its own db.py
import store_pg  # noqa: E402
sys.modules["store"] = store_pg
import teamelo as te  # noqa: E402
import player_v2 as v2  # noqa: E402

import db  # noqa: E402
from rate import TEAM, PLAYER  # noqa: E402

FORMULA = "OpenElo beta 0.1"
POSITIONS = {"G": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Forward"}

# Player.published, with its parts kept: total = club + selection + goals + national + absence.
PARTS: dict[tuple[int, int], dict] = {}
_published = v2.Player.published


def _published_with_parts(self, day, context):
    total = _published(self, day, context)
    raw = self.rating()
    bonus, national, goals = self.bonus(day, context), self.national_points(day, context), self.output_points(context)
    PARTS[(getattr(self, "player_id", None), day)] = {"raw": raw, "absence": total - bonus - national - goals - raw,
                                                     "bonus": bonus, "national": national, "goals": goals,
                                                     "window": list(self.output_window or [])}
    return total


v2.Player.published = _published_with_parts


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def iso(day: int) -> str:
    return (store_pg.EPOCH + pd.Timedelta(days=int(day))).date().isoformat()


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="directory for the JSON files (the site's data/ folder)")
    parser.add_argument("--site-url", help="e.g. https://openelo.com: also write sitemap.xml next to the data folder")
    args = parser.parse_args()
    out = Path(args.out)

    games = store_pg.club_games()
    if games.empty:
        sys.exit("No finished matches in the ingestion database: run fetch.py and normalize.py first.")
    te.BURN_IN_BEFORE = int(games.season.min()) + 1
    as_of_day = int(games.day.max()) + 1

    with db.connect() as conn:
        q = lambda sql: pd.read_sql(sql, conn)  # noqa: E731
        teams = q("SELECT team_id, name FROM teams")
        leagues = q("SELECT league_id, name, country FROM leagues")
        fixtures = q("""SELECT f.fixture_id, f.league_id, f.season, f.round, f.kickoff, f.home_team_id, f.away_team_id,
                               r.home_goals, r.away_goals
                        FROM fixtures f JOIN fixture_results r USING (fixture_id)""")
        players = q("SELECT player_id, name FROM players")
        apps = q("SELECT * FROM appearances")

    fixtures["day"] = (fixtures.kickoff.dt.tz_convert(None).dt.normalize() - store_pg.EPOCH).dt.days
    team_name = dict(zip(teams.team_id, teams.name))
    team_id = {t: f"{slug(n)}-{t}" for t, n in team_name.items()}
    player_name = dict(zip(players.player_id, players.name))
    player_id = {p: f"{slug(n)}-{p}" for p, n in player_name.items()}
    position = apps.groupby("player_id").position.agg(lambda s: s.mode().iat[0]).map(POSITIONS).to_dict()

    # the club's league: where it played most in its latest season
    latest = fixtures[fixtures.season == fixtures.season.max()]
    league_of = pd.concat([latest[["home_team_id", "league_id"]].rename(columns={"home_team_id": "team"}),
                           latest[["away_team_id", "league_id"]].rename(columns={"away_team_id": "team"})]
                          ).groupby("team").league_id.agg(lambda s: s.mode().iat[0]).to_dict()
    league_info = {r.league_id: {"id": f"{slug(r.name)}-{r.league_id}", "name": r.name, "country": r.country} for r in leagues.itertuples()}

    # club ratings after every match
    context = v2.Context(TEAM)
    tm = context.team_matches.merge(fixtures[["fixture_id", "home_team_id", "away_team_id", "home_goals", "away_goals"]],
                                    left_on="game_id", right_on="fixture_id")
    tm["after"] = tm.rating + tm.swing
    tm = tm.sort_values(["team_id", "day", "game_id"])
    club_hist = {t: g for t, g in tm.groupby("team_id")}
    club_now = {t: float(g.after.iloc[-1]) for t, g in club_hist.items()}

    def club_rating_on(team, day):
        g = club_hist.get(team)
        if g is None:
            return None
        before = g[g.day < day]
        return float(before.after.iloc[-1]) if len(before) else float(g.rating.iloc[0])

    # league tables, latest season
    table = defaultdict(lambda: {"points": 0, "gd": 0, "played": 0})
    for f in latest.itertuples():
        for t, gf, ga in ((f.home_team_id, f.home_goals, f.away_goals), (f.away_team_id, f.away_goals, f.home_goals)):
            row = table[t]
            row["played"] += 1
            row["gd"] += gf - ga
            row["points"] += 3 if gf > ga else 1 if gf == ga else 0

    # players: rating after each of his club's matches since his first appearance
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        series = {}
        for pid in sorted(context.lineups.player_id.unique()):
            pid = int(pid)
            mine = apps[apps.player_id == pid]
            if mine.empty:
                continue
            first = int(fixtures[fixtures.fixture_id.isin(mine.fixture_id)].day.min())
            team = int(mine.team_id.mode().iat[0])
            days = sorted({int(d) + 1 for d in club_hist[team].day if d >= first} | {as_of_day}) if team in club_hist else [as_of_day]
            s = v2.series(pid, PLAYER, context, days)
            s = s[s.rating.notna() & s.team_rating.notna()]
            if len(s):
                series[pid] = s

    def parts_of(pid, day, club_rating, club_label):
        p = PARTS.get((pid, day))
        if p is None:
            return []
        selection = p["raw"] - club_rating + p["bonus"]
        goals = sum(g for _, g, _ in p["window"])
        assists = sum(a for _, _, a in p["window"])
        return [
            {"key": "club", "value": round(club_rating), "label": club_label,
             "explain": "His club's rating after its last match. Every player starts from his team: OpenElo rates teams from results, then adjusts for each player."},
            {"key": "selection", "value": round(selection),
             "label": "Regular starter" if selection >= 40 else "In and out of the side" if selection > -40 else "Mostly on the bench",
             "explain": f"How often he is picked and starts, against what {club_label}'s 16 most-used players get on average."},
            {"key": "goals", "value": round(p["goals"]), "label": "Goals and assists",
             "explain": f"{goals:g} goals and {assists:g} assists in his recent squads, per 90 minutes, with 5 scoreless matches added so a few lucky minutes can't carry it."},
            {"key": "national", "value": round(p["national"]), "label": "National-team call-ups" if round(p["national"]) else "No national call-ups",
             "explain": "Being selected by a strong national team adds points; not being picked never takes any away."},
            {"key": "absence", "value": round(p["absence"]), "label": "Recent absence" if round(p["absence"]) <= -1 else "No recent absence",
             "explain": "Matches missed recently cost a little, recovered as he plays again." if round(p["absence"]) <= -1 else "He has not missed matches recently."},
        ]

    def fix_parts(parts, total):   # rounding: the parts must add up to the published number
        if parts:
            parts[1]["value"] += total - sum(x["value"] for x in parts)
        return parts

    fx = fixtures.set_index("fixture_id")
    player_docs = {}
    for pid, s in series.items():
        mine = apps[apps.player_id == pid].set_index("fixture_id")
        team = int(s.team_id.iloc[-1])
        hist, matches = [], []
        prev = None
        for r in s.itertuples():
            if r.day == as_of_day and len(hist) and hist[-1]["_day"] == r.day - 1:
                continue
            game = club_hist[int(r.team_id)]
            played = game[game.day == r.day - 1]
            rating, club_r = round(r.rating), round(r.team_rating)
            if len(played):
                g = played.iloc[-1]
                f = fx.loc[int(g.game_id)]
                home = int(f.home_team_id) == int(r.team_id)
                a = mine.loc[int(g.game_id)] if int(g.game_id) in mine.index else None
                if isinstance(a, pd.DataFrame):
                    a = a.iloc[0]
                matches.append({"date": iso(r.day - 1), "opponent": team_name.get(int(f.away_team_id if home else f.home_team_id), "?"),
                                "home": home, "goalsFor": int(f.home_goals if home else f.away_goals), "goalsAgainst": int(f.away_goals if home else f.home_goals),
                                "listed": a is not None, "started": bool(a.started) if a is not None else False,
                                "minutes": int(a.minutes) if a is not None else 0, "goals": int(a.goals) if a is not None else 0,
                                "assists": int(a.assists) if a is not None else 0,
                                "change": rating - prev if prev is not None else 0, "rating": rating, "clubRating": club_r})
                hist.append({"date": iso(r.day - 1), "rating": rating, "clubRating": club_r, "_day": r.day})
            prev = rating
        if not hist:
            continue
        last = s.iloc[-1]
        total = round(last.rating)
        name = player_name.get(pid, str(pid))
        player_docs[pid] = {
            "id": player_id[pid], "name": name, "shortName": name.split()[-1], "position": position.get(pid, "Midfielder"),
            "age": None, "nation": None, "team": team,
            "rating": total, "formula": FORMULA,
            "parts": fix_parts(parts_of(pid, int(last.day), float(last.team_rating), team_name.get(team, "His club")), total),
            "history": [{k: v for k, v in h.items() if k != "_day"} for h in hist], "matches": matches, "moments": [], "rumours": [],
            "change": {"lastMatch": matches[-1]["change"] if matches else 0, "season": total - hist[0]["rating"] + (matches[0]["change"] if matches else 0)},
        }

    as_of = iso(as_of_day - 1)
    ranked = sorted(player_docs.values(), key=lambda d: -d["rating"])
    clubs_ranked = sorted(club_now, key=lambda t: -club_now[t])

    def week_change(doc):
        cutoff = as_of_day - 1 - 7
        before = [h for h in doc["history"] if pd.Timestamp(h["date"]) <= store_pg.EPOCH + pd.Timedelta(days=cutoff)]
        return doc["rating"] - (before[-1]["rating"] if before else doc["history"][0]["rating"])

    def club_week(t):
        return round(club_now[t] - (club_rating_on(t, as_of_day - 7) or club_now[t]))

    def club_ref(t):
        lg = league_info.get(league_of.get(t), {"id": "other", "name": "Other", "country": ""})
        return {"id": team_id[t], "name": team_name.get(t, str(t)), "rating": round(club_now[t]), "league": {"id": lg["id"], "name": lg["name"]}}

    by_position = defaultdict(list)
    by_team = defaultdict(list)
    for d in ranked:
        by_position[d["position"]].append(d)
        by_team[d["team"]].append(d)

    for i, d in enumerate(ranked):
        t = d.pop("team")
        d["club"] = club_ref(t)
        d["asOf"] = as_of
        d["rank"] = {"world": i + 1, "worldOf": len(ranked), "position": by_position[d["position"]].index(d) + 1,
                     "positionOf": len(by_position[d["position"]]), "club": by_team[t].index(d) + 1, "clubOf": len(by_team[t])}
        d["neighbours"] = [{"rank": j + 1, "id": n["id"], "name": n["name"], "club": team_name.get(n.get("team", t), "") if "team" in n else n["club"]["name"] if "club" in n else "", "rating": n["rating"]}
                           for j, n in enumerate(ranked) if abs(j - i) <= 3]
        d["_team"] = t
        d["_week"] = week_change(d)
    for d in ranked:   # neighbours were built while some clubs were still unset
        for n in d["neighbours"]:
            n["club"] = next(x["club"]["name"] for x in ranked if x["id"] == n["id"])
        write(out / "players" / f"{d['id']}.json", {k: v for k, v in d.items() if not k.startswith("_")})

    def club_doc(t, rank):
        g = club_hist[t]
        lg_id = league_of.get(t)
        same_league = [x for x in clubs_ranked if league_of.get(x) == lg_id]
        standings = sorted(same_league, key=lambda x: (-table[x]["points"], -table[x]["gd"]))
        hist = [{"date": iso(r.day), "rating": round(r.after)} for r in g.itertuples()]
        matches = []
        for r in g.itertuples():
            home = int(r.home_team_id) == t
            opp = int(r.away_team_id if home else r.home_team_id)
            matches.append({"date": iso(r.day), "opponent": team_name.get(opp, "?"), "opponentId": team_id.get(opp), "home": home,
                            "goalsFor": int(r.home_goals if home else r.away_goals), "goalsAgainst": int(r.away_goals if home else r.home_goals),
                            "change": round(r.swing), "rating": round(r.after)})
        squad = [{"id": d["id"], "name": d["name"], "position": d["position"], "age": None, "rating": d["rating"],
                  "gap": d["rating"] - round(club_now[t]), "parts": d["parts"],
                  "starts": sum(1 for m in d["matches"] if m["started"]), "lastMatch": d["change"]["lastMatch"]} for d in by_team[t]]
        return {**club_ref(t), "asOf": as_of,
                "rank": {"world": rank, "worldOf": len(clubs_ranked), "league": same_league.index(t) + 1, "leagueOf": len(same_league),
                         "table": standings.index(t) + 1, "points": table[t]["points"]},
                "change": {"lastMatch": matches[-1]["change"] if matches else 0, "season": hist[-1]["rating"] - round(g.rating.iloc[0]) if hist else 0},
                "history": hist, "matches": matches, "squad": squad}

    club_docs = {t: club_doc(t, i + 1) for i, t in enumerate(clubs_ranked)}
    for d in club_docs.values():
        write(out / "clubs" / f"{d['id']}.json", d)

    write(out / "rankings.json", {"asOf": as_of, "players": [
        {"rank": d["rank"]["world"], "id": d["id"], "name": d["name"], "club": d["club"]["name"], "clubId": d["club"]["id"],
         "league": d["club"]["league"]["name"], "leagueId": d["club"]["league"]["id"], "position": d["position"], "age": None, "nation": None,
         "rating": d["rating"], "week": d["_week"], "season": d["change"]["season"]} for d in ranked]})
    write(out / "clubs.json", [{"id": team_id[t], "name": team_name.get(t), "rating": round(club_now[t]), "league": club_ref(t)["league"],
                                "rank": i + 1, "week": club_week(t), "points": table[t]["points"]} for i, t in enumerate(clubs_ranked)])
    lgs = []
    for lg_id, info in league_info.items():
        members = [t for t in clubs_ranked if league_of.get(t) == lg_id]
        if not members:
            continue
        standings = sorted(members, key=lambda x: (-table[x]["points"], -table[x]["gd"]))
        lgs.append({**info, "rating": round(sum(club_now[t] for t in members) / len(members)),
                    "clubs": [{"id": team_id[t], "name": team_name.get(t), "rating": round(club_now[t]), "week": club_week(t),
                               "table": standings.index(t) + 1, "points": table[t]["points"], "gd": table[t]["gd"]} for t in members]})
    write(out / "leagues.json", {"asOf": as_of, "leagues": sorted(lgs, key=lambda x: -x["rating"])})

    rounds = latest[latest.day <= as_of_day - 1]["round"].str.extract(r"(\d+)\s*$")[0].dropna().astype(int)
    movers = sorted(ranked, key=lambda d: -d["_week"])
    row = lambda d: {"id": d["id"], "name": d["name"], "club": d["club"]["name"], "clubId": d["club"]["id"], "rating": d["rating"], "change": d["_week"]}  # noqa: E731
    star = movers[0] if movers else None
    write(out / "week.json", {
        "asOf": as_of, "matchday": int(rounds.max()) if len(rounds) else None,
        "risers": [row(d) for d in movers[:5]], "fallers": [row(d) for d in movers[::-1][:5]],
        "top": [row(d) for d in ranked[:10]],
        "clubs": [{"id": team_id[t], "name": team_name.get(t), "note": club_ref(t)["league"]["name"], "rating": round(club_now[t]), "change": club_week(t)}
                  for t in sorted(clubs_ranked, key=lambda t: -abs(club_week(t)))[:5]],
        "story": ({"playerId": star["id"], "title": f"{star['name']} climbs {star['_week']} this week",
                   "text": f"He is now rated {star['rating']}, #{star['rank']['world']} of {len(ranked)}."} if star["_week"] > 0 else
                  {"playerId": ranked[0]["id"], "title": f"{ranked[0]['name']} is the top-rated player",
                   "text": f"Rated {ranked[0]['rating']}, playing for {ranked[0]['club']['name']}."}) if star else None,
    })
    write(out / "search.json", [{"kind": "player", "id": d["id"], "name": d["name"], "detail": d["club"]["name"], "rating": d["rating"]} for d in ranked]
          + [{"kind": "club", "id": team_id[t], "name": team_name.get(t), "detail": club_ref(t)["league"]["name"], "rating": round(club_now[t])} for t in clubs_ranked])
    write(out / "meta.json", {"asOf": as_of, "formula": FORMULA, "players": len(ranked), "clubs": len(clubs_ranked)})
    if args.site_url:
        base = args.site_url.rstrip("/")
        urls = [f"{base}/{p}" for p in ("index.html", "rankings.html", "leagues.html", "compare.html", "how.html", "about.html")]
        urls += [f"{base}/player.html?id={d['id']}" for d in ranked] + [f"{base}/club.html?id={team_id[t]}" for t in clubs_ranked]
        (out.parent / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{u.replace('&', '&amp;')}</loc><lastmod>{as_of}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    print(f"exported {len(ranked)} players, {len(clubs_ranked)} clubs, {len(lgs)} leagues as of {as_of} to {out}")


if __name__ == "__main__":
    warnings.simplefilter("ignore")   # empty national-team data and pandas' DBAPI notice
    main()
