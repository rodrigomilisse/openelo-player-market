"""OpenElo: a player's published rating on a date (FINDINGS.md §6).

The rating is computed by the exact integer reference (exact.py, run by
`evaluate.py exact`), which publishes an as-of snapshot on the first of every
month. This returns the latest snapshot on or before the date, in milli-Elo
(1 Elo point = 1000), or None when the player has no rating yet.
"""

import bisect
import datetime
import pickle
from functools import lru_cache

import store

EXACT_PATH = store.RESULTS_DIR / "exact.pkl"


@lru_cache(maxsize=1)
def _series() -> dict[int, tuple[list[int], list[int]]]:
    if not EXACT_PATH.exists():
        raise SystemExit("No ratings yet. Run the commands in README.md up to `evaluate.py exact`.")
    with open(EXACT_PATH, "rb") as source:
        snapshots = pickle.load(source).player_snapshots.sort_values("day")
    return {int(player): (group.day.tolist(), group.rating.tolist()) for player, group in snapshots.groupby("player_id")}


def openelo(tm_player_id: int, as_of: datetime.date) -> int | None:
    series = _series().get(int(tm_player_id))
    if series is None:
        return None
    days, ratings = series
    day = (as_of - store.EPOCH.date()).days
    position = bisect.bisect_right(days, day) - 1
    return ratings[position] if position >= 0 else None
