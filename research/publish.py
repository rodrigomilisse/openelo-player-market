"""Publishes the current candidate's player ratings, as of a day, for every active player.

The current candidate is the one in RESULTS-communication.md ("Current candidate"):
team Elo with process noise 3, minutes rule B, national-team term over 20 matches,
goal term 100 / 100. Its settings are `CANDIDATE` and `TEAM_OVERRIDES` below; change
them there when the candidate changes.

    .venv/bin/python publish.py                     # as of the day after the last club match in the store
    .venv/bin/python publish.py --as-of 2026-08-01  # as of a given day (matches before it count)
    .venv/bin/python publish.py --history           # also every month start since 2013 (slow, run once)

Writes to data/raw/published/ (gitignored, like all derived data):

    ratings_YYYY-MM-DD.csv   one row per active player
    latest.csv               a copy of the newest run
    published.sqlite3        table `rating` (as_of, player_id, rating, team_id), one batch per run;
                             re-running the same day replaces that day's batch

Ratings are in Elo points (not milli-Elo); the integer reference in exact.py is a
separate, older candidate and is not used here.
"""

import argparse
import hashlib
import pickle
import shutil
import sqlite3
import sys
import time
from multiprocessing import get_context

import pandas as pd

import candidate
import player_v2 as v2
import store
import team_checks

TEAM_OVERRIDES = {"process_noise": 3}
CANDIDATE = dict(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16,
                 national="clubs", bonus_scale=400.0, share_rule="starter", gk_reference=True,
                 nt_matches=20, nt_days=730, nt_credit=0.2, national_scale=100.0, output="weighted")
OUT_DIR = store.RAW_DIR / "published"
CACHE_DIR = store.RAW_DIR / "cache"
STALE_AFTER_DAYS = 14  # warn when the store's newest club match is older than this

_STATE = {}


def store_fingerprint() -> str:
    """The context cache is only valid for the store it was built from."""
    stat = store.STORE_PATH.stat()
    return hashlib.sha1(f"{stat.st_size}:{stat.st_mtime_ns}:{TEAM_OVERRIDES}".encode()).hexdigest()[:12]


def load_context() -> v2.Context:
    cache = CACHE_DIR / f"publish_context_{store_fingerprint()}.pkl"
    if cache.exists():
        print(f"context: cached ({cache.name})", flush=True)
        return pickle.loads(cache.read_bytes())
    started = time.time()
    print("context: building (team Elo over every club match, ~minutes)", flush=True)
    ctx = v2.Context(candidate.team_constants().with_(**TEAM_OVERRIDES))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in CACHE_DIR.glob("publish_context_*.pkl"):
        old.unlink()
    cache.write_bytes(pickle.dumps(ctx, protocol=5))
    print(f"context: built in {time.time() - started:.0f}s", flush=True)
    return ctx


def index_listings(ctx: v2.Context) -> None:
    """Context.listings scans every appearance for each call; group by player once instead."""
    apps = {p: g for p, g in ctx.appearances.groupby("player_id")}
    lins = {p: g for p, g in ctx.lineups.groupby("player_id")}
    empty_a, empty_l = ctx.appearances.iloc[0:0], ctx.lineups.iloc[0:0]
    original = v2.Context.listings

    def listings(player, fill):
        ctx_view = _View(ctx, apps.get(player, empty_a), lins.get(player, empty_l))
        return original(ctx_view, player, fill)

    ctx.listings = listings


class _View:
    """The slice of a Context that `listings` reads, narrowed to one player."""
    def __init__(self, ctx, appearances, lineups):
        self.appearances, self.lineups = appearances, lineups
        self.day, self.length = ctx.day, ctx.length


def _rate(player_id: int) -> pd.DataFrame:
    ctx, days = _STATE["ctx"], _STATE["days"]
    return v2.series(player_id, v2.Variant(**CANDIDATE), ctx, days)


def active_players(ctx: v2.Context, as_of: int, active_days: int) -> list[int]:
    apps = ctx.appearances.assign(day=ctx.appearances.game_id.map(ctx.day))
    lins = ctx.lineups.assign(day=ctx.lineups.game_id.map(ctx.day))
    seen = pd.concat([apps[["player_id", "day"]], lins[["player_id", "day"]]]).dropna()
    recent = seen[(seen.day < as_of) & (seen.day >= as_of - active_days)]
    return sorted(int(p) for p in recent.player_id.unique())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", help="YYYY-MM-DD; default: the day after the newest club match in the store")
    parser.add_argument("--active-days", type=int, default=300,
                        help="publish players listed for a club in the last N days (300 = the model's retirement rule)")
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--history", action="store_true", help="also publish every month start since 2013-01")
    parser.add_argument("--limit", type=int, help="only the first N players (smoke test)")
    args = parser.parse_args()

    if not store.STORE_PATH.exists():
        sys.exit(f"{store.STORE_PATH} is missing. Run `make warmup` (or ingest.py --fetch, then national.py).")
    newest = store.query("SELECT MAX(date) AS d FROM game WHERE national = 0").d.iloc[0]
    as_of_date = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp(newest) + pd.Timedelta(days=1)
    age = (pd.Timestamp.today().normalize() - pd.Timestamp(newest)).days
    print(f"store: newest club match {newest} ({age} days ago); publishing as of {as_of_date.date()}")
    if age > STALE_AFTER_DAYS:
        print(f"WARNING: the data is {age} days old. Run `make update` to pull the latest dataset "
              f"(the upstream dataset itself is refreshed about weekly).", file=sys.stderr)

    ctx = load_context()
    index_listings(ctx)
    as_of = int((as_of_date - store.EPOCH).days)
    players = active_players(ctx, as_of, args.active_days)
    if args.limit:
        players = players[:args.limit]
    days = ([d for d in team_checks.month_starts(last=str(as_of_date.date())) if d < as_of] if args.history else []) + [as_of]
    print(f"{len(players)} active players, {len(days)} snapshot(s)", flush=True)

    _STATE.update(ctx=ctx, days=days)
    started = time.time()
    with get_context("fork").Pool(args.processes) as pool:
        frames = []
        for i, frame in enumerate(pool.imap_unordered(_rate, players, chunksize=50), 1):
            frames.append(frame)
            if i % 2000 == 0:
                print(f"  {i}/{len(players)} players, {time.time() - started:.0f}s", flush=True)
    result = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    print(f"rated in {time.time() - started:.0f}s")

    write(result, as_of, as_of_date, newest)


def write(result: pd.DataFrame, as_of: int, as_of_date: pd.Timestamp, newest: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = result.assign(as_of=(store.EPOCH + pd.to_timedelta(result.day, unit="D")).dt.strftime("%Y-%m-%d"))
    names = store.players().set_index("player_id")[["name", "position"]]
    teams = store.teams().set_index("team_id").name.rename("team")
    current = result[result.day == as_of].join(names, on="player_id").join(teams, on="team_id")
    current["rating"] = current.rating.round(1)
    current["team_rating"] = current.team_rating.round(1)
    current = current.sort_values("rating", ascending=False)
    current["rank"] = range(1, len(current) + 1)
    columns = ["rank", "player_id", "name", "position", "team_id", "team", "rating", "team_rating", "as_of"]
    csv = OUT_DIR / f"ratings_{as_of_date.date()}.csv"
    current[columns].to_csv(csv, index=False)
    shutil.copyfile(csv, OUT_DIR / "latest.csv")

    with sqlite3.connect(OUT_DIR / "published.sqlite3") as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS rating (
            as_of TEXT NOT NULL, player_id INTEGER NOT NULL, rating REAL NOT NULL, team_id INTEGER,
            PRIMARY KEY (as_of, player_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS run (
            as_of TEXT PRIMARY KEY, ran_at TEXT NOT NULL, newest_match TEXT NOT NULL, players INTEGER NOT NULL)""")
        for day, frame in result.groupby("as_of"):
            conn.execute("DELETE FROM rating WHERE as_of = ?", (day,))
            conn.executemany("INSERT INTO rating VALUES (?, ?, ?, ?)",
                             [(day, int(r.player_id), float(r.rating), int(r.team_id)) for r in frame.itertuples()])
        conn.execute("INSERT OR REPLACE INTO run VALUES (?, ?, ?, ?)",
                     (str(as_of_date.date()), pd.Timestamp.now("UTC").isoformat(timespec="seconds"), newest, len(current)))
    print(f"wrote {csv} ({len(current)} players) and {OUT_DIR / 'latest.csv'}")
    print(current[["rank", "name", "team", "rating"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
