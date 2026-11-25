"""The two populate jobs. Both only ever ask the API for what Postgres does not have."""

import datetime as dt
import json
from importlib import resources

from . import normalize
from .client import QuotaExhausted
from .fetcher import Fetcher


def tracked_leagues(only: list[int] | None = None) -> dict[int, str]:
    data = json.loads(resources.files("apisports_loader").joinpath("leagues.json").read_text())
    leagues = {x["id"]: x["name"] for x in data["leagues"]}
    if only:
        leagues = {i: leagues.get(i, str(i)) for i in only}
    return leagues


def current_season(today: dt.date) -> int:
    return today.year if today.month >= 7 else today.year - 1


def _all_final(items: list) -> bool:
    return bool(items) and all(i["fixture"]["status"]["short"] in normalize.FINAL_STATUSES for i in items)


def pending_fixtures(conn, where: str, args: tuple, include_done: bool = False) -> list[tuple[int, dt.datetime]]:
    """Played fixtures with no complete players payload on record, newest first.
    `include_done` (only for an explicit --refetch) lists the ones already stored too."""
    skip = "" if include_done else """AND NOT EXISTS (SELECT 1 FROM raw_payload r WHERE r.endpoint = 'fixtures/players'
                          AND r.final AND r.params_key = 'fixture=' || f.fixture_id)"""
    return conn.execute(f"""
        SELECT f.fixture_id, f.kickoff FROM fixture f
        WHERE f.status IN ('FT', 'AET', 'PEN') AND {where} {skip}
        ORDER BY f.kickoff DESC""", args).fetchall()


def fetch_players(fetcher: Fetcher, fixture_id: int, kickoff: dt.datetime, settle_hours: int | None) -> bool:
    """One request per match. With `settle_hours`, an empty answer is only final once the
    match is that old (line-ups can arrive late); without it, empty is final at once."""
    def final(items):
        if items or settle_hours is None:
            return True
        return dt.datetime.now(dt.timezone.utc) - kickoff > dt.timedelta(hours=settle_hours)

    got = fetcher.get("fixtures/players", {"fixture": fixture_id}, final)
    if got is None:
        return False
    payload_id, items = got
    normalize.store_players(fetcher.conn, payload_id, fixture_id, items)
    fetcher.conn.commit()
    return True


def history(fetcher: Fetcher, leagues: dict[int, str], seasons: list[int], max_matches: int | None, log=print) -> str:
    """Completed seasons, newest first, one league-season at a time: its fixture list (1 request),
    then each played match's players (1 request each). Stops when the budget or quota ends."""
    matches = 0
    try:
        for season in seasons:
            for league, name in leagues.items():
                got = fetcher.get("fixtures", {"league": league, "season": season}, lambda items: True)
                if got is None:
                    log(f"  {name} {season}: not available on this plan, skipped")
                    continue
                normalize.store_fixtures(fetcher.conn, got[0], got[1])
                fetcher.conn.commit()
                todo = pending_fixtures(fetcher.conn, "f.league_id = %s AND f.season = %s", (league, season),
                                       include_done=fetcher.refetch)
                log(f"  {name} {season}: {len(todo)} matches still to fetch")
                for fixture_id, kickoff in todo:
                    if max_matches is not None and matches >= max_matches:
                        return "requested number of matches done"
                    if fetch_players(fetcher, fixture_id, kickoff, settle_hours=None):
                        matches += 1
    except QuotaExhausted as why:
        return f"stopped: {why}"
    return "everything requested is in Postgres"


def recent(fetcher: Fetcher, leagues: dict[int, str], since: dt.date, today: dt.date, log=print) -> str:
    """Per day since `since` (1 request a day for every competition), then the players of the
    played matches in tracked leagues. A day is complete once every match on it is over."""
    try:
        day = since
        while day <= today:
            got = fetcher.get("fixtures", {"date": day.isoformat()}, _all_final)
            if got is not None:
                items = [i for i in got[1] if i["league"]["id"] in leagues]
                normalize.store_fixtures(fetcher.conn, got[0], items)
                fetcher.conn.commit()
            day += dt.timedelta(days=1)
        start = dt.datetime.combine(since, dt.time.min, tzinfo=dt.timezone.utc)
        todo = pending_fixtures(fetcher.conn, "f.kickoff >= %s AND f.league_id = ANY(%s)", (start, list(leagues)),
                                       include_done=fetcher.refetch)
        log(f"  {len(todo)} played matches since {since} still need players")
        for fixture_id, kickoff in reversed(todo):          # oldest first, so no gap opens in the middle
            fetch_players(fetcher, fixture_id, kickoff, settle_hours=72)
    except QuotaExhausted as why:
        return f"stopped: {why}"
    return "up to date"


def rebuild(conn, log=print) -> None:
    """Re-derive the tables from stored payloads. No requests."""
    conn.execute("TRUNCATE appearance, fixture")
    for payload_id, body in conn.execute(
            "SELECT id, body FROM raw_payload WHERE endpoint = 'fixtures' AND final ORDER BY id").fetchall():
        normalize.store_fixtures(conn, payload_id, body.get("response") or [])
    count = 0
    for payload_id, params, body in conn.execute(
            "SELECT id, params, body FROM raw_payload WHERE endpoint = 'fixtures/players' AND final ORDER BY id").fetchall():
        normalize.store_players(conn, payload_id, int(params["fixture"]), body.get("response") or [])
        count += 1
    conn.commit()
    log(f"rebuilt fixtures and {count} matches of players from stored payloads")
