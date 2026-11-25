"""Copies the research store (research/data/raw/openelo_research.sqlite3) into Postgres, schema `research`.

Same tables, same columns, same Transfermarkt ids the model uses; dates become real dates.
Idempotent: a row whose primary key is already in Postgres is left alone, so running it again
after `make update` in research/ adds only what is new. Tables without a primary key
(transfer, international_result) load only into an empty table, or with --replace.
"""

import sqlite3
from pathlib import Path

DEFAULT_STORE = Path(__file__).resolve().parents[4] / "research" / "data" / "raw" / "openelo_research.sqlite3"
INDEXES = ["CREATE INDEX IF NOT EXISTS appearance_player ON research.appearance (player_id)",
           "CREATE INDEX IF NOT EXISTS lineup_player ON research.lineup (player_id)",
           "CREATE INDEX IF NOT EXISTS valuation_player ON research.valuation (player_id)",
           "CREATE INDEX IF NOT EXISTS game_date ON research.game (date)"]


def pg_type(name: str, sqlite_type: str) -> str:
    if name == "date":
        return "date"
    return {"INTEGER": "bigint", "REAL": "double precision"}.get(sqlite_type.upper(), "text")


def tables_of(lite: sqlite3.Connection) -> dict[str, list[tuple]]:
    names = [r[0] for r in lite.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    return {n: lite.execute(f"PRAGMA table_info({n})").fetchall() for n in names}   # cid,name,type,notnull,dflt,pk


def create_table(conn, table: str, columns: list[tuple]) -> list[str]:
    defs = [f'"{c[1]}" {pg_type(c[1], c[2])}{" NOT NULL" if c[3] or c[5] else ""}' for c in columns]
    keys = [f'"{c[1]}"' for c in sorted((c for c in columns if c[5]), key=lambda c: c[5])]
    if keys:
        defs.append(f"PRIMARY KEY ({', '.join(keys)})")
    conn.execute(f"CREATE TABLE IF NOT EXISTS research.{table} ({', '.join(defs)})")
    return keys


def copy_table(conn, lite, table: str, columns: list[tuple], keys: list[str], replace: bool, log) -> int:
    names = ", ".join(f'"{c[1]}"' for c in columns)
    if not keys:
        existing = conn.execute(f"SELECT count(*) FROM research.{table}").fetchone()[0]
        if existing and not replace:
            log(f"  {table}: {existing} rows already there, no primary key to tell new from old (use --replace {table})")
            return 0
        if existing:
            conn.execute(f"TRUNCATE research.{table}")
    conn.execute(f"CREATE TEMP TABLE staging (LIKE research.{table} INCLUDING DEFAULTS) ON COMMIT DROP")
    with conn.cursor().copy(f"COPY staging ({names}) FROM STDIN") as copy:
        for row in lite.execute(f"SELECT {names} FROM {table}"):
            copy.write_row(row)
    conflict = f"ON CONFLICT ({', '.join(keys)}) DO NOTHING" if keys else ""
    added = conn.execute(f"INSERT INTO research.{table} ({names}) SELECT {names} FROM staging {conflict}").rowcount
    log(f"  {table}: {added} new rows")
    return added


def import_store(conn, store: Path = DEFAULT_STORE, replace: list[str] | None = None, log=print) -> dict:
    if not store.exists():
        raise SystemExit(f"{store} not found. Build it first: cd research && make warmup")
    lite = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    conn.execute("CREATE SCHEMA IF NOT EXISTS research")
    conn.execute("""CREATE TABLE IF NOT EXISTS research.import_log (
        id bigserial PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(), source text NOT NULL,
        newest_club_match date, rows_added jsonb NOT NULL)""")
    added = {}
    for table, columns in tables_of(lite).items():
        keys = create_table(conn, table, columns)
        added[table] = copy_table(conn, lite, table, columns, keys, table in (replace or []), log)
        conn.commit()
    present = tables_of(lite)
    for statement in INDEXES:
        if statement.split(" ON research.")[1].split(" ")[0] in present:
            conn.execute(statement)
    newest = lite.execute("SELECT MAX(date) FROM game WHERE national = 0").fetchone()[0]
    import json
    conn.execute("INSERT INTO research.import_log (source, newest_club_match, rows_added) VALUES (%s, %s, %s)",
                 (str(store), newest, json.dumps(added)))
    conn.commit()
    log(f"research data in Postgres now runs to the club match of {newest}")
    return {"added": added, "newest": newest}
