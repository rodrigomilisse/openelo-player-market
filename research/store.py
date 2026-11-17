"""Read access to the research store built by ingest.py.

The store lives under data/raw/, which is gitignored: it is derived from scraped
data and the repository is public.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
STORE_PATH = RAW_DIR / "openelo_research.sqlite3"
CHARTS_DIR = RAW_DIR / "charts"
RESULTS_DIR = RAW_DIR / "results"

EPOCH = pd.Timestamp("2012-07-01")


@contextmanager
def connect(writable: bool = False):
    if not STORE_PATH.exists():
        raise SystemExit(f"{STORE_PATH} is missing. Run `.venv/bin/python -I ingest.py --fetch` first.")
    mode = "rw" if writable else "ro"
    conn = sqlite3.connect(f"file:{STORE_PATH}?mode={mode}", uri=True)
    try:
        yield conn
        if writable:
            conn.commit()
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql(sql, conn, params=params)


def club_games() -> pd.DataFrame:
    """Club matches in processing order: by date, then by game id within a day. The
    model batches each day, so the order within a day never changes a result."""
    games = query("""
        SELECT g.*, s.home_corners, s.away_corners, s.home_yellow, s.away_yellow,
               s.home_red, s.away_red, s.odd_home, s.odd_draw, s.odd_away
        FROM game g LEFT JOIN match_stats s ON s.game_id = g.game_id
        WHERE g.national = 0
        ORDER BY g.date, g.game_id
    """)
    games["day"] = (pd.to_datetime(games.date) - EPOCH).dt.days
    return games


def national_games() -> pd.DataFrame:
    games = query("SELECT * FROM game WHERE national = 1 ORDER BY date, game_id")
    games["day"] = (pd.to_datetime(games.date) - EPOCH).dt.days
    return games


def appearances() -> pd.DataFrame:
    columns = {r[1] for r in _connect_columns("appearance")}
    assists = "assists" if "assists" in columns else "0 AS assists"
    return query(f"SELECT game_id, player_id, team_id, minutes, goals, {assists}, yellow, red FROM appearance")


def _connect_columns(table: str) -> list:
    return query(f"PRAGMA table_info({table})").values.tolist()


def lineups() -> pd.DataFrame:
    return query("SELECT game_id, player_id, team_id, starter, position FROM lineup")


def teams() -> pd.DataFrame:
    return query("SELECT team_id, name, kind, domestic_competition_id FROM team")


def players() -> pd.DataFrame:
    return query("SELECT player_id, name, position, sub_position, date_of_birth, citizenship FROM player")


def valuations(age_adjust: str | None = None) -> pd.DataFrame:
    """Transfermarkt values. With an `age_adjust` spec (default: the environment
    variable OPENELO_TM_AGE_ADJUST, empty for none) every value is divided by
    `age_factor`, so a rating is scored against value changes that are not just a
    player getting older or younger. Evaluation only; ratings never see this."""
    values = query("SELECT player_id, date, value_eur, team_id FROM valuation")
    if age_adjust is None:
        age_adjust = os.environ.get("OPENELO_TM_AGE_ADJUST", "")
    if age_adjust in ("", "0", "none"):
        return values
    born = query("SELECT player_id, date_of_birth FROM player").dropna()
    values = values.merge(born, on="player_id")
    age = (pd.to_datetime(values.date) - pd.to_datetime(values.date_of_birth)).dt.days / 365.25
    values["value_eur"] = (values.value_eur / age_factor(age.to_numpy(), age_adjust)).round().astype("int64")
    return values.drop(columns="date_of_birth")


AGE_FACTOR_FLOOR = 0.1


def age_factor(age: np.ndarray, spec: str) -> np.ndarray:
    """How much more a player of this age is worth than the same player at 25.
    `linear:R` falls in a straight line, R times as much at 20 as at 30 (R = 2 is
    zero at 40: 1.47 at 18, 1.0 at 25, 0.67 at 30, 0.33 at 35). `exp:R` loses
    the same share every year, R times as much at 20 as at 30. Floored at 0.1."""
    kind, _, ratio = spec.partition(":")
    ratio = float(ratio or 2)
    if kind == "linear":
        zero = (30 * ratio - 20) / (ratio - 1)
        factor = (zero - age) / (zero - 25)
    elif kind == "exp":
        factor = ratio ** ((25 - age) / 10)
    else:
        raise ValueError(f"unknown age adjustment {spec!r}: use linear:R or exp:R")
    return np.maximum(factor, AGE_FACTOR_FLOOR)


def transfers() -> pd.DataFrame:
    return query("SELECT player_id, date, from_team_id, to_team_id, fee_eur, market_value_eur FROM transfer")


def clubelo() -> pd.DataFrame:
    return query("SELECT date, team_id, elo FROM clubelo")


def output_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def national_extra() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """National-team games, line-ups and minutes added by national.py (empty when it
    has not been run). Games the store already holds keep their game id."""
    try:
        games = query("SELECT * FROM nt_game ORDER BY date, game_id")
    except Exception:
        empty = pd.DataFrame(columns=["game_id", "player_id", "team_id"])
        return pd.DataFrame(columns=["game_id", "date", "day", "home_team_id", "away_team_id", "length",
                                     "in_store"]), empty.assign(starter=[]), empty.assign(minutes=[])
    games["day"] = (pd.to_datetime(games.date) - EPOCH).dt.days
    games["goal_difference"] = games.home_goals - games.away_goals
    return games, query("SELECT * FROM nt_lineup"), query("SELECT * FROM nt_appearance")


def international_results() -> pd.DataFrame:
    """Every international result (martj42), team names as the store spells them."""
    try:
        results = query("SELECT * FROM international_result ORDER BY date")
    except Exception:
        return pd.DataFrame()
    results["day"] = (pd.to_datetime(results.date) - EPOCH).dt.days
    return results


def national_team_names() -> dict:
    names = dict(query("SELECT team_id, name FROM team WHERE kind = 'national'").values)
    try:
        names.update(dict(query("SELECT team_id, name FROM nt_team").values))
    except Exception:
        pass
    return names
