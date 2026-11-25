"""Postgres access and the fetch ledger (raw_payload)."""

import json
import os
from importlib import resources

import psycopg


def connect(url: str | None = None) -> psycopg.Connection:
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set, e.g. postgresql://user:pass@host:5432/openelo?sslmode=require")
    return psycopg.connect(url)


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(resources.files("apisports_loader").joinpath("schema.sql").read_text())
    conn.commit()


def params_key(params: dict) -> str:
    return "&".join(f"{k}={params[k]}" for k in sorted(params))


def stored_payload(conn, endpoint: str, key: str):
    """The newest *final* payload for this exact request, or None: the ledger lookup."""
    row = conn.execute("""SELECT id, body FROM raw_payload
                          WHERE provider = 'API_FOOTBALL' AND endpoint = %s AND params_key = %s AND final
                          ORDER BY id DESC LIMIT 1""", (endpoint, key)).fetchone()
    return row


def is_blocked(conn, endpoint: str, key: str) -> bool:
    return conn.execute("SELECT 1 FROM fetch_block WHERE endpoint = %s AND params_key = %s",
                        (endpoint, key)).fetchone() is not None


def save_block(conn, endpoint: str, key: str, reason: str, detail: str) -> None:
    conn.execute("""INSERT INTO fetch_block (endpoint, params_key, reason, detail) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (endpoint, params_key) DO UPDATE SET reason = EXCLUDED.reason,
                    detail = EXCLUDED.detail, blocked_at = now()""", (endpoint, key, reason, detail))
    conn.commit()


def clear_block(conn, endpoint: str, key: str) -> None:
    conn.execute("DELETE FROM fetch_block WHERE endpoint = %s AND params_key = %s", (endpoint, key))


def save_payload(conn, endpoint: str, params: dict, body: dict, results: int, final: bool,
                 remaining: int | None) -> int:
    row = conn.execute("""INSERT INTO raw_payload (endpoint, params_key, params, body, results, final, requests_remaining)
                          VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                       (endpoint, params_key(params), json.dumps(params), json.dumps(body), results, final,
                        remaining)).fetchone()
    return row[0]
