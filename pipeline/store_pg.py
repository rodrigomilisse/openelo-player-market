"""The research models' `store` interface, served from the ingestion database.

research/teamelo.py and research/player_v2.py read their data only through
`store` (club_games, appearances, lineups, players and the national-team
functions). This module offers the same functions and column names over the
pipeline's Postgres tables; rate.py installs it as `store` before importing the
models, so the models run unchanged.

Translation from API-Football:
- competition_id: research codes for the leagues the research data used (GB1, ES1,
  ...), CL / EL / UCOL for the UEFA competitions, AF<id> for anything else.
- stage: from the competition's kind and the round's name (see STAGE rules below).
- neutral: finals of cups, super cups and continental competitions, and the Club
  World Cup. API-Football has no neutral-venue flag.
- Second legs are not linked (leg 1, no first leg): the candidate does not use
  competition state (state_floor 1.0).
- appearance: squad entries with minutes > 0; lineup: every squad entry, with
  starter 1 or 0, as in the research data.
- National-team tables are empty until national results are added.
"""
from collections import Counter
from pathlib import Path

import pandas as pd

import db

EPOCH = pd.Timestamp("2012-07-01")
RAW_DIR = Path(__file__).parent / "data"
RESULTS_DIR = RAW_DIR / "results"
CHARTS_DIR = RAW_DIR / "charts"

RESEARCH_CODE = {39: "GB1", 140: "ES1", 135: "IT1", 78: "L1", 61: "FR1", 94: "PO1", 88: "NL1",
                 144: "BE1", 203: "TR1", 179: "SC1", 2: "CL", 3: "EL", 848: "UCOL"}
CONTINENTAL = {2, 3, 848}
SUPER_CUPS = {528, 556, 547, 529, 526, 531}          # Community Shield, Supercopa, Supercoppa, DFL, Trophée, UEFA
CLUB_WORLD_CUP = {15}
POSITION = {"G": "Goalkeeper", "D": "Defender", "M": "Midfield", "F": "Attack"}


def competition_code(league_id: int) -> str:
    return RESEARCH_CODE.get(league_id, f"AF{league_id}")


def stage_of(league_id: int, round_name: str) -> str:
    r = round_name.lower()
    if league_id in CLUB_WORLD_CUP:
        return "club_world_cup"
    if league_id in SUPER_CUPS:
        return "super_cup"
    if league_id in CONTINENTAL:
        if "qualifying" in r or "preliminary" in r or r.startswith("play-offs"):
            return "continental_qualifying"
        if "group" in r or "league stage" in r:
            return "continental_group"
        if r == "final":
            return "continental_final"
        return "continental_knockout"
    if r.startswith("regular season"):
        return "league"
    if r in ("final", "semi-finals", "quarter-finals"):
        return "cup_late"
    return "cup_early"


def neutral_of(stage: str, round_name: str) -> bool:
    return stage in ("super_cup", "club_world_cup", "continental_final") or round_name.lower() == "final"


def _frame(sql: str, columns: list[str]) -> pd.DataFrame:
    with db.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return pd.DataFrame(rows, columns=columns)


def club_games() -> pd.DataFrame:
    games = _frame("""
        SELECT f.fixture_id, (f.kickoff AT TIME ZONE 'UTC')::date, f.season, f.league_id, f.round,
               f.home_team_id, f.away_team_id, r.home_goals - r.away_goals
        FROM fixtures f JOIN fixture_results r USING (fixture_id)
        ORDER BY 2, 1""",
        ["game_id", "date", "season", "league_id", "round", "home_team_id", "away_team_id", "goal_difference"])
    games["date"] = pd.to_datetime(games.date)
    games["competition_id"] = games.league_id.map(competition_code)
    games["stage"] = [stage_of(l, r) for l, r in zip(games.league_id, games["round"])]
    games["neutral"] = [int(neutral_of(s, r)) for s, r in zip(games.stage, games["round"])]
    games["leg"] = 1
    games["first_leg_game_id"] = None
    games["data_issue"] = None
    games["national"] = 0
    for column in ("home_corners", "away_corners", "home_yellow", "away_yellow", "home_red", "away_red",
                   "odd_home", "odd_draw", "odd_away"):
        games[column] = None
    games["day"] = (games.date - EPOCH).dt.days
    games["date"] = games.date.dt.strftime("%Y-%m-%d")
    return games


def _squads() -> pd.DataFrame:
    return _frame("SELECT fixture_id, player_id, team_id, position, started, minutes, goals, assists FROM appearances",
                  ["game_id", "player_id", "team_id", "position", "started", "minutes", "goals", "assists"])


def appearances() -> pd.DataFrame:
    rows = _squads()
    rows = rows[rows.minutes > 0].copy()
    rows["yellow"], rows["red"] = 0, 0
    return rows[["game_id", "player_id", "team_id", "minutes", "goals", "assists", "yellow", "red"]]


def lineups() -> pd.DataFrame:
    rows = _squads()
    rows["starter"] = rows.started.astype(int)
    rows["position"] = rows.position.map(POSITION)
    return rows[["game_id", "player_id", "team_id", "starter", "position"]]


def teams() -> pd.DataFrame:
    rows = _frame("SELECT team_id, name FROM teams", ["team_id", "name"])
    rows["kind"], rows["domestic_competition_id"] = "club", None
    return rows


def players() -> pd.DataFrame:
    """A player's position is the one the provider lists him at most often."""
    rows = _frame("SELECT player_id, name FROM players", ["player_id", "name"])
    squads = _squads()
    usual = {p: POSITION.get(Counter(g.position).most_common(1)[0][0]) for p, g in squads.groupby("player_id")}
    rows["position"] = rows.player_id.map(usual)
    rows["sub_position"], rows["date_of_birth"], rows["citizenship"] = None, None, None
    return rows


GAME_COLUMNS = ["game_id", "date", "day", "season", "competition_id", "stage", "home_team_id", "away_team_id",
                "goal_difference", "neutral", "national"]


def national_games() -> pd.DataFrame:
    return pd.DataFrame(columns=GAME_COLUMNS)


def national_extra() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games = pd.DataFrame(columns=GAME_COLUMNS + ["length", "in_store"])
    lineup = pd.DataFrame(columns=["game_id", "player_id", "team_id", "starter"])
    minutes = pd.DataFrame(columns=["game_id", "player_id", "team_id", "minutes"])
    return games, lineup, minutes


def international_results() -> pd.DataFrame:
    return pd.DataFrame()


def national_team_names() -> dict:
    return {}


def output_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name
