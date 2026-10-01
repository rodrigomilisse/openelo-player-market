"""SQLite storage for scraped Transfermarkt data.

Scraping is expensive/rate-limited and Transfermarkt history for a retired
or veteran player never changes, so this dataset is meant to be scraped once
and reused indefinitely. Everything downstream (comparison graphs, average
graphs, correlation) reads from here, never from the network directly.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "openelo_market.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    tm_id TEXT,
    tm_name TEXT,
    resolved_at TEXT,
    scraped_at TEXT
);

CREATE TABLE IF NOT EXISTS market_values (
    player_id INTEGER NOT NULL REFERENCES players(id),
    date TEXT NOT NULL,
    market_value_eur INTEGER,
    club_name TEXT,
    age INTEGER,
    PRIMARY KEY (player_id, date)
);
"""


@contextmanager
def connect(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def get_or_create_player(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()
    if row:
        return row
    conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
    return conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()


def set_resolution(conn: sqlite3.Connection, player_id: int, tm_id: str, tm_name: str) -> None:
    conn.execute(
        "UPDATE players SET tm_id = ?, tm_name = ?, resolved_at = datetime('now') WHERE id = ?",
        (tm_id, tm_name, player_id),
    )


def replace_market_values(conn: sqlite3.Connection, player_id: int, rows: list[dict]) -> None:
    conn.execute("DELETE FROM market_values WHERE player_id = ?", (player_id,))
    conn.executemany(
        """INSERT OR REPLACE INTO market_values
           (player_id, date, market_value_eur, club_name, age)
           VALUES (:player_id, :date, :market_value_eur, :club_name, :age)""",
        [{**r, "player_id": player_id} for r in rows],
    )
    conn.execute("UPDATE players SET scraped_at = datetime('now') WHERE id = ?", (player_id,))


def get_player_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()


def get_all_players(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM players ORDER BY name").fetchall()


def get_scraped_players(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM players WHERE scraped_at IS NOT NULL ORDER BY name"
    ).fetchall()


def get_market_values(conn: sqlite3.Connection, player_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM market_values WHERE player_id = ? ORDER BY date", (player_id,)
    ).fetchall()
