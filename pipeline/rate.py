"""Compute OpenElo from the ingestion database and store a rating snapshot.

    python rate.py                 # team and player ratings as of the day after the last finished match
    python rate.py --teams-only
    python rate.py --as-of 2025-01-01

Runs the research models unchanged (research/teamelo.py, research/player_v2.py),
fed by store_pg instead of the research store, with the current candidate's
constants (research/NEXT.md, RESULTS-communication.md "Current candidate").
Snapshots are provisional: floats, not the exact integer reference, and nothing
settles money on them. Each run appends a snapshot; nothing is overwritten.
"""
import argparse
import multiprocessing
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
from psycopg.types.json import Jsonb

sys.path.append(str(Path(__file__).resolve().parent.parent / "research"))   # last: research has its own db.py
import store_pg  # noqa: E402
sys.modules["store"] = store_pg   # the research models read their data through `store`
import teamelo as te  # noqa: E402
import player_v2 as v2  # noqa: E402

import db  # noqa: E402

# Team Elo with uncertainty, forward only (FINDINGS.md §4.2), process noise 3 (NEXT.md).
TEAM = te.TeamConstants(uncertainty=True, process_noise=3.0, initial_variance=400.0 ** 2, home_advantage=50.0,
                        goal_difference=True, league_seed_offset=100.0, unknown_seed_offset=300.0)
# The direct model as decided (NEXT.md "Decided"; fit_light.py BASE).
PLAYER = v2.Variant(direct=True, absence=True, selection=True, window=50, squad_window=True, squad_top=16,
                    national="clubs", bonus_scale=400.0, national_scale=100.0, nt_matches=20, nt_credit=0.2,
                    nt_days=730, share_rule="starter", gk_reference=True, output="weighted",
                    goal_scale=100.0, assist_scale=100.0, output_prior=5.0)

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS rating;
CREATE TABLE IF NOT EXISTS rating.snapshots (
    snapshot_id bigserial   PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    as_of       date        NOT NULL,               -- ratings as of the start of this day
    data_cutoff timestamptz NOT NULL,               -- newest raw payload the run could see
    kind        text        NOT NULL,               -- 'provisional'
    constants   jsonb       NOT NULL                -- team and player constants used
);
CREATE TABLE IF NOT EXISTS rating.team_ratings (
    snapshot_id bigint           NOT NULL REFERENCES rating.snapshots,
    team_id     integer          NOT NULL,
    rating      double precision NOT NULL,
    variance    double precision NOT NULL,
    matches     integer          NOT NULL,
    PRIMARY KEY (snapshot_id, team_id)
);
CREATE TABLE IF NOT EXISTS rating.player_ratings (
    snapshot_id bigint           NOT NULL REFERENCES rating.snapshots,
    player_id   integer          NOT NULL,
    team_id     integer          NOT NULL,
    rating      double precision NOT NULL,
    team_rating double precision NOT NULL,
    PRIMARY KEY (snapshot_id, player_id)
);
"""


_CONTEXT = None      # set before the pool forks, so workers share it copy-on-write
_AS_OF_DAY = None


def _rate_players(player_ids: list[int]) -> list[tuple]:
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # empty national-team data: means of nothing
        for player_id in player_ids:
            series = v2.series(int(player_id), PLAYER, _CONTEXT, [_AS_OF_DAY])
            for row in series.itertuples():
                if pd.notna(row.rating) and pd.notna(row.team_rating):
                    rows.append((int(player_id), int(row.team_id), float(row.rating), float(row.team_rating)))
    return rows


def rate_players(context, as_of_day: int, workers: int) -> list[tuple]:
    """Players are independent once the context is built: rate them in `workers`
    processes (fork), keeping the serial order of the results."""
    global _CONTEXT, _AS_OF_DAY
    _CONTEXT, _AS_OF_DAY = context, as_of_day
    ids = [int(p) for p in sorted(context.lineups.player_id.unique())]
    if ids:                                                       # build the shared tables before forking
        context.listings(ids[0], PLAYER.fill)
        for team in context.by_team:
            context.squad_mean_at(team, 0, PLAYER.squad_top, PLAYER.share_rule, PLAYER.sub_credit)
    if workers <= 1 or len(ids) < 2 * workers or "fork" not in multiprocessing.get_all_start_methods():
        return _rate_players(ids)
    chunks = [ids[i::workers * 8] for i in range(workers * 8)]
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        results = pool.map(_rate_players, chunks, chunksize=1)
    return sorted((row for chunk in results for row in chunk), key=lambda r: r[0])


def as_dict(constants) -> dict:
    return {k: v for k, v in vars(constants).items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", help="YYYY-MM-DD; default: the day after the last finished match")
    parser.add_argument("--teams-only", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="processes for the player ratings (default: all cores; 1 = serial)")
    args = parser.parse_args()

    games = store_pg.club_games()
    if games.empty:
        sys.exit("No finished matches in the ingestion database: run fetch.py and normalize.py first.")
    te.BURN_IN_BEFORE = int(games.season.min()) + 1   # the first season in the data is the burn-in
    as_of_day = int((pd.Timestamp(args.as_of) - store_pg.EPOCH).days) if args.as_of else int(games.day.max()) + 1
    as_of = (store_pg.EPOCH + pd.Timedelta(days=as_of_day)).date()

    matches = [m for m in te.load_matches() if m.day < as_of_day]
    _, states = te.run(matches, TEAM)
    team_rows = [(t, s.rating, s.variance, s.matches) for t, s in states.items()]

    player_rows = []
    if not args.teams_only:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # empty national-team data: means of nothing
            context = v2.Context(TEAM)
        player_rows = rate_players(context, as_of_day, args.workers)

    with db.connect() as conn:
        db.create_schema(conn)
        conn.execute(SCHEMA)
        cutoff = conn.execute("SELECT max(received_at) FROM raw_payloads").fetchone()[0]
        snapshot_id = conn.execute(
            """INSERT INTO rating.snapshots (as_of, data_cutoff, kind, constants) VALUES (%s, %s, 'provisional', %s)
               RETURNING snapshot_id""",
            (as_of, cutoff, Jsonb({"team": as_dict(TEAM), "player": as_dict(PLAYER),
                                   "burn_in_before": te.BURN_IN_BEFORE}))).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO rating.team_ratings VALUES (%s, %s, %s, %s, %s)",
                            [(snapshot_id, *r) for r in team_rows])
            cur.executemany("INSERT INTO rating.player_ratings VALUES (%s, %s, %s, %s, %s)",
                            [(snapshot_id, *r) for r in player_rows])
        conn.commit()
    print(f"snapshot {snapshot_id} as of {as_of}: {len(matches)} matches, {len(team_rows)} teams, "
          f"{len(player_rows)} players")


if __name__ == "__main__":
    main()
