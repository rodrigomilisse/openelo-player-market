"""python -m apisports_loader <migrate|status|history|recent|rebuild|import-research>"""

import argparse
import datetime as dt
import sys

from . import db, jobs
from .client import Client, Fatal
from .fetcher import Fetcher


def make_client(args) -> Client:
    return Client(max_requests=getattr(args, "max_requests", None), reserve=getattr(args, "reserve", 3))


def start(args, conn, need_scope=False):
    """Client and fetcher, with the day's quota read first (the status call is free)."""
    client = make_client(args)
    info = client.status()
    quota = info.get("requests", {})
    print(f"API quota today: {quota.get('current', '?')}/{quota.get('limit_day', '?')} used; "
          f"this run may use {args.max_requests if args.max_requests is not None else 'all but the reserve of ' + str(args.reserve)}")
    return client, Fetcher(conn, client, refetch=args.refetch, retry_blocked=args.retry_blocked)


def report(fetcher, why: str) -> None:
    print(f"{why}. This run: {fetcher.fetched} requests to the API, {fetcher.cached} answered from Postgres, "
          f"{fetcher.blocked} skipped (provider refuses them).")
    if fetcher.client.remaining_day is not None:
        print(f"Requests left today: {fetcher.client.remaining_day}")


def cmd_history(args) -> int:
    if args.refetch and not (args.league and args.season):
        sys.exit("--refetch downloads data that is already in Postgres again. It needs an explicit scope: "
                 "--league ID --season YEAR.")
    conn = db.connect()
    db.migrate(conn)
    client, fetcher = start(args, conn)
    last_done = jobs.current_season(dt.date.today()) - 1
    seasons = [args.season] if args.season else list(range(last_done, args.from_season - 1, -1))
    print(f"history: seasons {seasons[0]} down to {seasons[-1]}, {len(jobs.tracked_leagues(args.league))} leagues")
    report(fetcher, jobs.history(fetcher, jobs.tracked_leagues(args.league), seasons, args.max_matches))
    return 0


def cmd_recent(args) -> int:
    conn = db.connect()
    db.migrate(conn)
    client, fetcher = start(args, conn)
    today = dt.datetime.now(dt.timezone.utc).date()
    since = dt.date.fromisoformat(args.since) if args.since else today - dt.timedelta(days=args.days)
    print(f"recent: {since} to {today}")
    report(fetcher, jobs.recent(fetcher, jobs.tracked_leagues(), since, today))
    return 0


def cmd_status(args) -> int:
    conn = db.connect()
    db.migrate(conn)
    rows = conn.execute("""
        SELECT l.name, f.season, count(*) FILTER (WHERE f.status IN ('FT','AET','PEN')) AS played,
               count(DISTINCT a.fixture_id) AS with_players
        FROM fixture f JOIN league l USING (league_id) LEFT JOIN appearance a USING (fixture_id)
        GROUP BY l.name, f.season ORDER BY f.season DESC, l.name""").fetchall()
    print(f"{'league':<32}{'season':>7}{'played':>8}{'with players':>14}{'missing':>9}")
    for name, season, played, have in rows:
        print(f"{name:<32}{season:>7}{played:>8}{have:>14}{played - have:>9}")
    blocked = conn.execute("SELECT count(*) FROM fetch_block").fetchone()[0]
    total = conn.execute("SELECT count(*), count(*) FILTER (WHERE final) FROM raw_payload").fetchone()
    print(f"\nstored responses: {total[0]} ({total[1]} complete); refused by the plan: {blocked}")
    if not args.offline:
        try:
            quota = Client().status().get("requests", {})
            print(f"API quota today: {quota.get('current')}/{quota.get('limit_day')}")
        except Fatal as why:
            print(f"API: {why}")
    return 0


def cmd_import_research(args) -> int:
    from pathlib import Path
    from . import research_import
    conn = db.connect()
    store = Path(args.store) if args.store else research_import.DEFAULT_STORE
    print(f"importing {store} into schema research")
    research_import.import_store(conn, store, args.replace or [])
    return 0


def cmd_rebuild(args) -> int:
    conn = db.connect()
    db.migrate(conn)
    jobs.rebuild(conn)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="apisports_loader", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def budget(p):
        p.add_argument("--max-requests", type=int, help="stop after this many API requests (default: use the day's quota)")
        p.add_argument("--reserve", type=int, default=3, help="always leave this many requests of the day unused")
        p.add_argument("--retry-blocked", action="store_true", help="ask again for requests the plan refused earlier")

    p = sub.add_parser("migrate", help="create or update the tables")
    p.set_defaults(func=lambda a: (db.migrate(db.connect()), print("schema is up to date"), 0)[2])

    p = sub.add_parser("history", help="add completed seasons, newest first, never re-fetching what is stored")
    budget(p)
    p.add_argument("--from-season", type=int, default=2018, help="oldest season to go back to (default 2018)")
    p.add_argument("--season", type=int, help="only this season")
    p.add_argument("--league", type=int, action="append", help="only this league id (repeatable)")
    p.add_argument("--max-matches", type=int, help="stop after fetching the players of this many matches")
    p.add_argument("--refetch", action="store_true", help="EXPLICIT: download again what is stored (needs --league and --season)")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("recent", help="add the latest matches")
    budget(p)
    p.add_argument("--days", type=int, default=7, help="how many days back (default 7)")
    p.add_argument("--since", help="YYYY-MM-DD instead of --days")
    p.add_argument("--refetch", action="store_true", help="EXPLICIT: download the window again even if stored")
    p.set_defaults(func=cmd_recent)

    p = sub.add_parser("status", help="what is in Postgres and what is missing")
    p.add_argument("--offline", action="store_true", help="do not call the API for the quota")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("import-research", help="copy the research store (Transfermarkt data the model uses) into Postgres schema `research`")
    p.add_argument("--store", help="path to openelo_research.sqlite3 (default: research/data/raw/)")
    p.add_argument("--replace", action="append", help="EXPLICIT: reload this table with no primary key (transfer, international_result)")
    p.set_defaults(func=cmd_import_research)

    p = sub.add_parser("rebuild", help="re-derive tables from stored payloads (no API requests)")
    p.set_defaults(func=cmd_rebuild)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except Fatal as why:
        sys.exit(f"STOPPED: {why}")


if __name__ == "__main__":
    main()
