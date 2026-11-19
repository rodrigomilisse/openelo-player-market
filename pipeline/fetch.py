"""Fetch match data from API-Football into the ingestion database, each request once.

    python fetch.py status                                  # today's quota (free, not counted)
    python fetch.py fixtures --league 39 --season 2024      # one request: a league-season's fixtures and scores
    python fetch.py players  --league 39 --season 2024      # one request per finished match: squads and minutes
    python fetch.py players  --league 39 --season 2024 --limit 20

Every response is stored as received in raw_payloads. A request already stored is
skipped, so a run can be repeated or resumed freely; `fixtures --refresh` stores a new
version of a fixture list (for a season still being played). Responses carrying an
error (quota, plan, bad parameters) are not stored, and the run stops.

The key is read from APIFOOTBALL_KEY and sent in the x-apisports-key header. In a
cloud session whose proxy injects the key, any placeholder value works.
Free plan limits: 100 requests a day, 10 a minute; seasons 2022 to 2024.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from psycopg.types.json import Jsonb

import db

BASE = "https://v3.football.api-sports.io"
PROVIDER = "api-football"
FINISHED = ("FT", "AET", "PEN")
MIN_INTERVAL = 6.5          # seconds between counted requests: stays under 10 a minute
RESERVE = 2                 # leave a couple of requests unused for manual checks

_last_call = 0.0


class ApiError(Exception):
    pass


def call(endpoint: str, params: dict) -> tuple[dict, dict]:
    """GET one endpoint; returns (body, headers). Raises ApiError when the body reports errors."""
    global _last_call
    key = os.environ.get("APIFOOTBALL_KEY")
    if not key:
        sys.exit("Set APIFOOTBALL_KEY (any placeholder if a proxy injects the real key).")
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0 and endpoint != "/status":
        time.sleep(wait)
    url = f"{BASE}{endpoint}?{urllib.parse.urlencode(params)}" if params else f"{BASE}{endpoint}"
    request = urllib.request.Request(url, headers={"x-apisports-key": key})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
        headers = {k.lower(): v for k, v in response.headers.items()}
    _last_call = time.monotonic()
    errors = body.get("errors")
    if errors:
        raise ApiError(json.dumps(errors))
    return body, headers


def remaining(headers: dict) -> int | None:
    value = headers.get("x-ratelimit-requests-remaining")
    return int(value) if value is not None else None


def stored(conn, endpoint: str, params: dict) -> bool:
    row = conn.execute(
        "SELECT 1 FROM raw_payloads WHERE provider = %s AND endpoint = %s AND params = %s LIMIT 1",
        (PROVIDER, endpoint, Jsonb(params))).fetchone()
    return row is not None


def store(conn, endpoint: str, params: dict, body: dict) -> None:
    conn.execute("INSERT INTO raw_payloads (provider, endpoint, params, body) VALUES (%s, %s, %s, %s)",
                 (PROVIDER, endpoint, Jsonb(params), Jsonb(body)))
    conn.commit()


def latest_fixture_list(conn, league: int, season: int) -> list[dict]:
    row = conn.execute(
        """SELECT body FROM raw_payloads WHERE provider = %s AND endpoint = '/fixtures' AND params = %s
           ORDER BY received_at DESC, id DESC LIMIT 1""",
        (PROVIDER, Jsonb({"league": league, "season": season}))).fetchone()
    if row is None:
        sys.exit(f"No fixture list stored for league {league}, season {season}: run `fetch.py fixtures` first.")
    return row[0]["response"]


def cmd_status(_conn, _args) -> None:
    body, _ = call("/status", {})
    print(json.dumps(body["response"]["requests"]), body["response"]["subscription"]["plan"])


def cmd_fixtures(conn, args) -> None:
    params = {"league": args.league, "season": args.season}
    if stored(conn, "/fixtures", params) and not args.refresh:
        print("fixture list already stored (use --refresh for a new version)")
        return
    body, headers = call("/fixtures", params)
    store(conn, "/fixtures", params, body)
    print(f"stored {body['results']} fixtures; {remaining(headers)} requests left today")


def cmd_players(conn, args) -> None:
    fixtures = latest_fixture_list(conn, args.league, args.season)
    todo = [f["fixture"]["id"] for f in fixtures if f["fixture"]["status"]["short"] in FINISHED]
    todo = [i for i in todo if not stored(conn, "/fixtures/players", {"fixture": i})]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} finished matches to fetch")
    done = 0
    for fixture_id in todo:
        params = {"fixture": fixture_id}
        try:
            body, headers = call("/fixtures/players", params)
        except ApiError as error:
            print(f"stopped at fixture {fixture_id}: {error}")
            break
        store(conn, "/fixtures/players", params, body)
        done += 1
        left = remaining(headers)
        if done % 10 == 0:
            print(f"  {done} fetched, {left} requests left today", flush=True)
        if left is not None and left <= RESERVE:
            print(f"stopping with {left} requests left today; run again tomorrow to continue")
            break
    print(f"fetched {done} matches")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for name in ("fixtures", "players"):
        p = sub.add_parser(name)
        p.add_argument("--league", type=int, required=True)
        p.add_argument("--season", type=int, required=True)
        if name == "fixtures":
            p.add_argument("--refresh", action="store_true")
        else:
            p.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    with db.connect() as conn:
        db.create_schema(conn)
        {"status": cmd_status, "fixtures": cmd_fixtures, "players": cmd_players}[args.command](conn, args)


if __name__ == "__main__":
    main()
