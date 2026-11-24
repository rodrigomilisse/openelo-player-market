"""Rebuild the derived tables from raw_payloads, without calling the API.

    python normalize.py

Uses the latest stored version of each request. The derived tables are truncated
and rebuilt in one transaction, so the run can be repeated at any time.
"""
import db

FINISHED = ("FT", "AET", "PEN")


def latest(conn, endpoint: str):
    return conn.execute(
        """SELECT DISTINCT ON (params) body FROM raw_payloads
           WHERE provider = 'api-football' AND endpoint = %s
           ORDER BY params, received_at DESC, id DESC""", (endpoint,)).fetchall()


def number(value) -> int:
    return int(value) if value is not None else 0


def main() -> None:
    with db.connect() as conn:
        db.create_schema(conn)
        leagues, teams, fixtures, results, shootouts, players, appearances = {}, {}, {}, {}, {}, {}, {}
        for (body,) in latest(conn, "/fixtures"):
            for f in body["response"]:
                league, fixture, home, away = f["league"], f["fixture"], f["teams"]["home"], f["teams"]["away"]
                leagues[league["id"]] = (league["name"], league["country"] or "")
                teams[home["id"]] = home["name"]
                teams[away["id"]] = away["name"]
                status = fixture["status"]["short"]
                fixtures[fixture["id"]] = (league["id"], league["season"], league["round"] or "", fixture["date"],
                                           home["id"], away["id"], status)
                if status in FINISHED and f["goals"]["home"] is not None:
                    results[fixture["id"]] = (f["goals"]["home"], f["goals"]["away"], status in ("AET", "PEN"))
                    penalty = f["score"]["penalty"]
                    if status == "PEN" and penalty["home"] is not None:
                        shootouts[fixture["id"]] = (penalty["home"], penalty["away"])
        skipped = 0
        for (body,) in latest(conn, "/fixtures/players"):
            fixture_id = int(body["parameters"]["fixture"])
            if fixture_id not in fixtures:
                skipped += 1
                continue
            for side in body["response"]:
                team_id = side["team"]["id"]
                teams.setdefault(team_id, side["team"]["name"])
                for entry in side["players"]:
                    player, stats = entry["player"], entry["statistics"][0]
                    players[player["id"]] = player["name"] or ""
                    games, goals = stats["games"], stats["goals"]
                    appearances[(fixture_id, player["id"])] = (
                        team_id, games["position"] or "", not games["substitute"], number(games["minutes"]),
                        number(goals["total"]), number(goals["assists"]))

        with conn.transaction():
            conn.execute("TRUNCATE appearances, players, shootouts, fixture_results, fixtures, teams, leagues")
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO leagues VALUES (%s, %s, %s)", [(k, *v) for k, v in leagues.items()])
                cur.executemany("INSERT INTO teams VALUES (%s, %s)", list(teams.items()))
                cur.executemany("INSERT INTO fixtures VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                [(k, *v) for k, v in fixtures.items()])
                cur.executemany("INSERT INTO fixture_results VALUES (%s, %s, %s, %s)", [(k, *v) for k, v in results.items()])
                cur.executemany("INSERT INTO shootouts VALUES (%s, %s, %s)", [(k, *v) for k, v in shootouts.items()])
                cur.executemany("INSERT INTO players VALUES (%s, %s)", list(players.items()))
                cur.executemany("""INSERT INTO appearances (fixture_id, player_id, team_id, position, started,
                                   minutes, goals, assists) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                                [(f, p, *v) for (f, p), v in appearances.items()])
        print(f"{len(leagues)} leagues, {len(teams)} teams, {len(fixtures)} fixtures ({len(results)} finished, "
              f"{len(shootouts)} shoot-outs), {len(players)} players, {len(appearances)} squad entries"
              + (f"; {skipped} player payloads skipped (their fixture list is not stored)" if skipped else ""))


if __name__ == "__main__":
    main()
