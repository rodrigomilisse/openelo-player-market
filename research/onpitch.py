"""On-pitch goal difference per player and club match, into the research store.

For every club match with a line-up: each player's minutes on the pitch (start or
coming on, until substituted, sent off or the end) and the goals his team scored
and conceded while he was on. Built from transfermarkt-datasets' game events.

    .venv/bin/python -I onpitch.py

Imports nothing from this directory, so it runs in isolated mode (-I).
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent / "data" / "raw"
STORE = ROOT / "openelo_research.sqlite3"
EVENTS = ROOT / "downloads" / "transfermarkt-datasets" / "game_events.csv.gz"


def build() -> None:
    conn = sqlite3.connect(STORE)
    games = pd.read_sql("SELECT game_id, home_team_id h, away_team_id a, home_goals hg, away_goals ag "
                        "FROM game WHERE national = 0", conn).set_index("game_id")
    lineups = pd.read_sql("SELECT game_id, player_id, team_id, starter FROM lineup", conn)
    lineups = lineups[lineups.game_id.isin(games.index)]
    longest = pd.read_sql("SELECT game_id, MAX(minutes) m FROM appearance GROUP BY game_id", conn).set_index("game_id").m
    ev = pd.read_csv(EVENTS, usecols=["game_id", "minute", "type", "club_id", "player_id", "player_in_id", "description"])
    ev = ev[ev.game_id.isin(games.index)]

    goals = ev[ev.type == "Goals"][["game_id", "minute", "club_id"]]
    # check the convention: the club on a goal event (own goals included) is the club credited with it
    counted = goals.groupby(["game_id", "club_id"]).size()
    scored = pd.concat([games.reset_index()[["game_id", "h", "hg"]].set_axis(["game_id", "club_id", "n"], axis=1),
                        games.reset_index()[["game_id", "a", "ag"]].set_axis(["game_id", "club_id", "n"], axis=1)])
    scored = scored.set_index(["game_id", "club_id"]).n
    with_goals = scored[scored.index.get_level_values(0).isin(goals.game_id.unique())]
    agree = (counted.reindex(with_goals.index).fillna(0) == with_goals).mean()
    print(f"goal events match the final score for {agree:.1%} of club-matches")

    subs = ev[ev.type == "Substitutions"]
    reds = ev[(ev.type == "Cards") & ev.description.str.contains("Red card|Second yellow", na=False)]
    off = pd.concat([subs[["game_id", "player_id", "minute"]], reds[["game_id", "player_id", "minute"]]])
    off = off.groupby(["game_id", "player_id"]).minute.min()
    on = subs[["game_id", "player_in_id", "minute"]].dropna().astype({"player_in_id": int})
    on = on.groupby(["game_id", "player_in_id"]).minute.min()

    goals_by_game = {g: list(zip(x.minute, x.club_id)) for g, x in goals.groupby("game_id")}
    rows = []
    for (game, team), squad in lineups.groupby(["game_id", "team_id"]):
        length = 120 if longest.get(game, 90) > 100 else 90
        events = goals_by_game.get(game, [])
        for player, starter in zip(squad.player_id, squad.starter):
            start = 0 if starter == 1 else on.get((game, player))
            if start is None or (isinstance(start, float) and np.isnan(start)):
                continue                                   # unused substitute
            end = off.get((game, player), length)
            end = min(end, length)
            if end <= start:
                continue
            gf = sum(1 for m, c in events if start < m <= end and c == team)
            ga = sum(1 for m, c in events if start < m <= end and c != team)
            rows.append((int(game), int(player), int(team), int(end - start), gf, ga))
    conn.execute("DROP TABLE IF EXISTS onpitch")
    conn.execute("CREATE TABLE onpitch (game_id INTEGER, player_id INTEGER, team_id INTEGER, minutes_on INTEGER, "
                 "goals_for INTEGER, goals_against INTEGER, PRIMARY KEY (game_id, player_id))")
    conn.executemany("INSERT OR REPLACE INTO onpitch VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"{len(rows)} player-matches written")
    conn.close()


if __name__ == "__main__":
    build()
