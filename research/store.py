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
    return query("SELECT game_id, player_id, team_id, minutes, goals, yellow, red FROM appearance")


def lineups() -> pd.DataFrame:
    return query("SELECT game_id, player_id, team_id, starter, position FROM lineup")


def teams() -> pd.DataFrame:
    return query("SELECT team_id, name, kind, domestic_competition_id FROM team")


def players() -> pd.DataFrame:
    return query("SELECT player_id, name, position, sub_position, date_of_birth, citizenship FROM player")


def valuations(age_adjusted: bool | None = None) -> pd.DataFrame:
    """Transfermarkt values. With `age_adjusted` (default: environment variable
    OPENELO_TM_AGE_ADJUST=1) every value is restated at the age-25 level (see
    `age_curve`), so a rating is scored against value changes that are not just a
    player getting older or younger. Evaluation only; ratings never see this."""
    values = query("SELECT player_id, date, value_eur, team_id FROM valuation")
    if age_adjusted is None:
        age_adjusted = os.environ.get("OPENELO_TM_AGE_ADJUST") == "1"
    if not age_adjusted:
        return values
    born = query("SELECT player_id, date_of_birth FROM player").dropna()
    values = values.merge(born, on="player_id")
    age = (pd.to_datetime(values.date) - pd.to_datetime(values.date_of_birth)).dt.days / 365.25
    ages, cumulative = age_curve()
    values["value_eur"] = (values.value_eur * np.exp(-np.interp(age, ages, cumulative))).round().astype("int64")
    return values.drop(columns="date_of_birth")


REFERENCE_AGE = 25
_age_curve = None


def age_curve():
    """(ages, cumulative log value change from the reference age): the typical way a
    Transfermarkt value drifts with age, from the 12-month log change of every
    valued player (value at least €500k) averaged by age in whole years, then
    summed outwards from age 25. Players who stop being valued drop out, so the
    old-age decline is understated."""
    global _age_curve
    if _age_curve is not None:
        return _age_curve
    values = query("SELECT v.player_id, v.date, v.value_eur, p.date_of_birth FROM valuation v "
                   "JOIN player p USING (player_id) WHERE p.date_of_birth IS NOT NULL AND v.value_eur >= 500000")
    values["t"] = pd.to_datetime(values.date)
    values = values.sort_values("t")
    later = values[["player_id", "t", "value_eur"]].rename(columns={"t": "t_later", "value_eur": "later"})
    ahead = values.assign(t_later=values.t + pd.Timedelta(days=365))
    pairs = pd.merge_asof(ahead.sort_values("t_later"), later.sort_values("t_later"), on="t_later",
                          by="player_id", direction="backward", tolerance=pd.Timedelta(days=120))
    pairs = pairs[pairs.t_later <= values.t.max()].dropna(subset=["later"])
    pairs = pairs[pairs.later > 0]
    pairs["age"] = ((pairs.t - pd.to_datetime(pairs.date_of_birth)).dt.days / 365.25).astype(int).clip(16, 38)
    pairs["change"] = np.log(pairs.later / pairs.value_eur)
    drift = pairs.groupby("age").change.mean()
    ages = np.arange(16, 40)
    step = drift.reindex(range(16, 39)).interpolate().to_numpy()      # drift over age a → a+1
    centre = {a: 0.0 for a in ages}
    for a in range(REFERENCE_AGE + 1, 40):
        centre[a] = centre[a - 1] + step[a - 1 - 16]
    for a in range(REFERENCE_AGE - 1, 15, -1):
        centre[a] = centre[a + 1] - step[a - 16]
    _age_curve = (ages.astype(float), np.array([centre[a] for a in ages]))
    return _age_curve


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
