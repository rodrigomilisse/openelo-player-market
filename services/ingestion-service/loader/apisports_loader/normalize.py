"""Raw API-Football payloads to tables. Pure translation: the same code rebuilds the tables from
stored payloads (`rebuild`) without a single request."""

FINISHED = {"FT", "AET", "PEN"}                       # played to a result
AWARDED_OR_VOID = {"AWD", "WO", "CANC", "ABD", "PST"}  # nothing more will happen to this fixture
FINAL_STATUSES = FINISHED | AWARDED_OR_VOID


def store_fixtures(conn, payload_id: int, items: list) -> None:
    for item in items:
        fx, lg, teams, goals, score = item["fixture"], item["league"], item["teams"], item["goals"], item["score"]
        conn.execute("INSERT INTO league VALUES (%s, %s, %s) ON CONFLICT (league_id) DO UPDATE SET name = EXCLUDED.name",
                     (lg["id"], lg["name"], lg.get("country")))
        for side in ("home", "away"):
            conn.execute("INSERT INTO team VALUES (%s, %s) ON CONFLICT (team_id) DO UPDATE SET name = EXCLUDED.name",
                         (teams[side]["id"], teams[side]["name"]))
        status = fx["status"]["short"]
        extra_time = status in ("AET", "PEN") or (score.get("extratime") or {}).get("home") is not None
        conn.execute("""
            INSERT INTO fixture (fixture_id, league_id, season, round, kickoff, status, home_team_id, away_team_id,
                                 home_goals, away_goals, extra_time, shootout, payload_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fixture_id) DO UPDATE SET status = EXCLUDED.status, kickoff = EXCLUDED.kickoff,
                home_goals = EXCLUDED.home_goals, away_goals = EXCLUDED.away_goals,
                extra_time = EXCLUDED.extra_time, shootout = EXCLUDED.shootout, payload_id = EXCLUDED.payload_id""",
                     (fx["id"], lg["id"], lg["season"], lg.get("round"), fx["date"], status,
                      teams["home"]["id"], teams["away"]["id"], goals.get("home"), goals.get("away"),
                      extra_time, status == "PEN", payload_id))


def store_players(conn, payload_id: int, fixture_id: int, items: list) -> int:
    """items: one entry per team with its players (/fixtures/players). Returns rows stored."""
    stored = 0
    for side in items:
        team_id = side["team"]["id"]
        for entry in side["players"]:
            stats = (entry.get("statistics") or [{}])[0]
            games, goals = stats.get("games") or {}, stats.get("goals") or {}
            player = entry["player"]
            conn.execute("INSERT INTO player VALUES (%s, %s) ON CONFLICT (player_id) DO UPDATE SET name = EXCLUDED.name",
                         (player["id"], player["name"]))
            conn.execute("""
                INSERT INTO appearance (fixture_id, player_id, team_id, started, minutes, goals, assists, position, payload_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fixture_id, player_id) DO UPDATE SET started = EXCLUDED.started, minutes = EXCLUDED.minutes,
                    goals = EXCLUDED.goals, assists = EXCLUDED.assists, position = EXCLUDED.position,
                    team_id = EXCLUDED.team_id, payload_id = EXCLUDED.payload_id""",
                         (fixture_id, player["id"], team_id, not games.get("substitute", True),
                          games.get("minutes") or 0, goals.get("total") or 0, goals.get("assists") or 0,
                          games.get("position"), payload_id))
            stored += 1
    return stored
