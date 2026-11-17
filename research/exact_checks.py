"""Checks on the integer reference (FINDINGS.md §6): C1, C9, C11, C12, and how the
zero of the scale moves a proportional dividend split."""

import pickle

import numpy as np
import pandas as pd

import exact
import player_checks
import playerelo as pe
import store
import team_checks

EXACT_PATH = store.RESULTS_DIR / "exact.pkl"
CHECK_DAY = int((pd.Timestamp("2016-01-01") - store.EPOCH).days)


def constants():
    team = team_checks.load_candidate()
    lag, iterations = team_checks.chosen_hindsight()
    return (exact.ExactTeamConstants.from_float(team, lag, iterations),
            exact.ExactPlayerConstants.from_float(player_checks.load_player_constants()))


def run_full(log=print) -> exact.ExactRun:
    team, player = constants()
    result = exact.run(team, player, pe.PlayerInputs.load(), team_checks.month_starts(),
                       player_checks.tracked_ids(), log=log)
    with open(store.output_path(store.RESULTS_DIR, EXACT_PATH.name), "wb") as out:
        pickle.dump(result, out)
    return result


def load_exact() -> exact.ExactRun:
    if not EXACT_PATH.exists():
        raise SystemExit("Run `evaluate.py exact` first.")
    with open(EXACT_PATH, "rb") as source:
        return pickle.load(source)


def truncated_runs(log=print) -> dict:
    """C1 and C12 on the data before 2016-01-01, where a run takes minutes: the
    as-of ratings for that day from a run that never saw a later match must equal
    the full run's, and shuffling every input list must change nothing."""
    team, player = constants()
    inputs = pe.PlayerInputs.load()
    days = [d for d in team_checks.month_starts() if d <= CHECK_DAY]
    tracked = player_checks.tracked_ids()
    plain = exact.run(team, player, inputs, days, tracked, until_day=CHECK_DAY, log=log)
    shuffled = exact.run(team, player, inputs, days, tracked, until_day=CHECK_DAY, shuffle_seed=7, log=log)
    full = load_exact()
    same_order = (plain.team_snapshots == shuffled.team_snapshots
                  and plain.player_snapshots.sort_values(["day", "player_id"]).reset_index(drop=True).equals(
                      shuffled.player_snapshots.sort_values(["day", "player_id"]).reset_index(drop=True))
                  and plain.ledger == shuffled.ledger)
    full_players = full.player_snapshots[full.player_snapshots.day == CHECK_DAY].set_index("player_id").rating
    cut_players = plain.player_snapshots[plain.player_snapshots.day == CHECK_DAY].set_index("player_id").rating
    no_look_ahead = (full.team_snapshots[CHECK_DAY] == plain.team_snapshots[CHECK_DAY]
                     and full_players.sort_index().equals(cut_players.sort_index()))
    return {"C1 as-of identical without later matches": bool(no_look_ahead),
            "C12 identical after shuffling inputs": bool(same_order),
            "teams compared": len(plain.team_snapshots[CHECK_DAY]), "players compared": int(len(cut_players))}


def compare_with_float(result: exact.ExactRun) -> dict:
    """C11: the integer run against the float run with the same constants."""
    replay = team_checks.load_replay()
    team_gaps = []
    for day, states in result.team_snapshots.items():
        floats = replay.snapshot_states.get(day, {})
        team_gaps += [abs(rating / exact.RATING_UNIT - floats[team]) for team, rating in states.items() if team in floats]
    snapshots = player_checks.load_snapshots()["tracked"].set_index(["day", "player_id"]).rating
    integers = result.player_snapshots.set_index(["day", "player_id"]).rating / exact.RATING_UNIT
    common = integers.index.intersection(snapshots.index)
    player_gaps = (integers.loc[common] - snapshots.loc[common]).abs()
    differences = np.array([abs(result.as_of_differences[i] / exact.RATING_UNIT - replay.as_of_differences[i])
                            for i in range(len(result.match_game_ids))])
    return {"team ratings: max |integer − float|": float(max(team_gaps)),
            "team ratings: mean": float(np.mean(team_gaps)),
            "player ratings: max": float(player_gaps.max()), "player ratings: mean": float(player_gaps.mean()),
            "pre-match differences: max": float(differences.max()), "values compared": len(team_gaps) + len(player_gaps)}


def conservation(result: exact.ExactRun) -> dict:
    """C9: the stored pool at each 1 July equals the sum of every ledger entry before
    it, exactly; and each source's flow per season."""
    ledger = pd.Series(result.ledger)
    ledger.index = pd.MultiIndex.from_tuples(ledger.index, names=["season", "source"])
    flows = ledger.unstack("source").fillna(0).astype("int64")
    residuals = {}
    for day, pool in sorted(result.stored_pool_by_season_end.items()):
        season_ended = exact.season_of(day - 1)
        explained = int(flows.loc[flows.index <= season_ended].to_numpy().sum())
        residuals[str((store.EPOCH + pd.Timedelta(days=day)).date())] = pool - explained
    active = active_players_per_season(result)
    per_player = (flows / exact.RATING_UNIT).div(pd.Series(active), axis=0)
    rounding = {season: float(value) / exact.RATING_UNIT for season, value in result.rounding.items()}
    published = {str((store.EPOCH + pd.Timedelta(days=d)).date()): (p - result.stored_pool_by_season_end[d]) / exact.RATING_UNIT
                 for d, p in sorted(result.published_pool_by_season_end.items())}
    return {"unexplained residual at each 1 July (milli-Elo)": residuals,
            "flows per season (Elo points, whole pool)": (flows / exact.RATING_UNIT).round(0).reset_index().to_dict("records"),
            "flows per active player per season (Elo points)": per_player.round(2).reset_index().to_dict("records"),
            "rounding residue per season (Elo points, exact)": rounding,
            "published minus stored pool at 1 July (unsettled decay, Elo points)": published}


def active_players_per_season(result: exact.ExactRun) -> dict:
    appearances = store.query("""SELECT a.player_id, g.date FROM appearance a JOIN game g ON g.game_id = a.game_id
                                 WHERE a.minutes > 0""")
    appearances["season"] = [d.year if d.month >= 7 else d.year - 1 for d in pd.to_datetime(appearances.date)]
    return appearances.groupby("season").player_id.nunique().to_dict()


def scale_zero(result: exact.ExactRun) -> dict:
    """How a split proportional to the rating level depends on where zero sits,
    against splits by standing in the pool. Not a dividend design (§6.6)."""
    rows = []
    for day, pool in result.pool.groupby("day"):
        ratings = pool.rating.to_numpy() / exact.RATING_UNIT
        date = str((store.EPOCH + pd.Timedelta(days=int(day))).date())
        mean = ratings.mean()
        rules = {
            "level (zero at 0)": ratings,
            "level − 1000": np.clip(ratings - 1000, 0, None),
            "level − 1250 (replacement level)": np.clip(ratings - 1250, 0, None),
            "level − 1400": np.clip(ratings - 1400, 0, None),
            "above pool mean": np.clip(ratings - mean, 0, None),
            "percentile in pool": pd.Series(ratings).rank(pct=True).to_numpy(),
        }
        for rule, weights in rules.items():
            shares = weights / weights.sum()
            ordered = np.sort(shares)[::-1]
            rows.append({"date": date, "rule": rule, "players": len(ratings),
                         "top 1% of players get": float(ordered[: max(1, len(ordered) // 100)].sum()),
                         "top 10% get": float(ordered[: max(1, len(ordered) // 10)].sum()),
                         "best ÷ median player": float(ordered[0] / np.median(shares)) if np.median(shares) > 0 else float("inf"),
                         "players paid nothing": float(np.mean(shares == 0)),
                         "gini": gini(shares)})
    frame = pd.DataFrame(rows)
    latest = frame[frame.date == frame.date.max()]
    return {"latest": latest.round(4).to_dict("records"),
            "level (zero at 0), by year": frame[frame.rule == "level (zero at 0)"][["date", "best ÷ median player", "top 10% get"]].round(3).to_dict("records"),
            "mean and spread of active ratings by year": pool_level(result)}


def gini(shares: np.ndarray) -> float:
    ordered = np.sort(shares)
    count = len(ordered)
    cumulative = np.cumsum(ordered)
    return float((count + 1 - 2 * np.sum(cumulative) / cumulative[-1]) / count)


def pool_level(result: exact.ExactRun) -> list:
    rows = []
    for day, pool in result.pool.groupby("day"):
        ratings = pool.rating / exact.RATING_UNIT
        rows.append({"date": str((store.EPOCH + pd.Timedelta(days=int(day))).date()), "players": len(ratings),
                     "mean": round(float(ratings.mean()), 1), "std": round(float(ratings.std()), 1),
                     "p1": round(float(ratings.quantile(0.01)), 1), "p99": round(float(ratings.quantile(0.99)), 1)})
    return rows
