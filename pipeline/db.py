"""Connection to the ingestion database.

OPENELO_DB is a libpq connection string. The default matches infra/compose.yml's
Postgres on localhost (user and password `market`) with a database named `ingestion`.
"""
import os
from pathlib import Path

import psycopg

DEFAULT_DSN = "postgresql://market:market@localhost:5432/ingestion"
SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ.get("OPENELO_DB", DEFAULT_DSN))


def create_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text())
    conn.commit()
