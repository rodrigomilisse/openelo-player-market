"""Player-level evaluation (FINDINGS.md §5)."""

import itertools
import json
import math
import pickle
from multiprocessing import Pool

import numpy as np
import pandas as pd

import playerelo as pe
import players as tracked_players
import store
import team_checks
import teamelo as te

PLAYER_CONSTANTS_PATH = store.RESULTS_DIR / "player_constants.json"
SNAPSHOTS_PATH = store.RESULTS_DIR / "snapshots.pkl"
CHANGES_PATH = store.RESULTS_DIR / "changes.pkl"

ANCHOR_RATES = [0.02, 0.05, 0.1, 0.2]
LINEUP_WEIGHTS = [0.1, 0.2, 0.3, 0.4, 0.5]
BONUS_SCALES = [0, 25, 50, 100, 200, 400]

MONTH = 30.44


def set_a_ids() -> dict[int, str]:
    import sqlite3
    conn = sqlite3.connect(f"file:{store.Path(__file__).parent / 'data' / 'openelo_market.sqlite3'}?mode=ro", uri=True)
    rows = conn.execute("SELECT tm_id, name FROM players WHERE tm_id IS NOT NULL").fetchall()
    conn.close()
    return {int(tm_id): name for tm_id, name in rows}


def set_b_groups() -> dict[int, str]:
    groups = {}
    for group, names in tracked_players.SET_B_GROUPS.items():
        for name in names:
            groups[tracked_players.SET_B_TM_IDS[name]] = group
    return groups


def tracked_ids() -> set[int]:
    return set(set_a_ids()) | set(set_b_groups())


# ---------------------------------------------------------------------------
# Fitting (C6)

_SHARED = {}


def _init_worker():
    constants = team_checks.load_candidate()
    _SHARED["team_constants"] = constants
    _SHARED["matches"] = te.load_matches()
    _SHARED["predictions"], _ = te.run(_SHARED["matches"], constants)
    _SHARED["inputs"] = pe.PlayerInputs.load()


def _lineup_scores(config):
    anchor_rate, lineup_weight, bonus_scale = config
    constants = pe.PlayerConstants(anchor_rate=anchor_rate, lineup_weight=lineup_weight, bonus_scale=bonus_scale)
    _, lineup = pe.run(_SHARED["matches"], _SHARED["predictions"], _SHARED["inputs"], constants,
                       _SHARED["team_constants"], score_lineups=True)
    return pe.lineup_scores(lineup)


def _lineup_job(config) -> dict:
    team_only, with_lineup = _lineup_scores(config)
    mean, low, high = te.paired_difference(with_lineup.test_losses, team_only.test_losses)
    anchor_rate, lineup_weight, bonus_scale = config
    return {"anchor_rate": anchor_rate, "lineup_weight": lineup_weight, "bonus_scale": bonus_scale,
            "fit gain": with_lineup.fit_log_loss - team_only.fit_log_loss,
            "test gain": mean, "low": low, "high": high}


def _bonus_job(chosen: dict) -> dict:
    """The chosen bonus against no bonus at the same other constants, paired on the
    test matches: the adoption rule of FINDINGS.md §1.1."""
    config = (chosen["anchor_rate"], chosen["lineup_weight"], chosen["bonus_scale"])
    _, with_bonus = _lineup_scores(config)
    _, without = _lineup_scores((config[0], config[1], 0))
    mean, low, high = te.paired_difference(with_bonus.test_losses, without.test_losses)
    return {"gain": mean, "low": low, "high": high, "adopted": bool(high < 0)}


def fit_players(processes: int = 3) -> dict:
    configs = list(itertools.product(ANCHOR_RATES, LINEUP_WEIGHTS, BONUS_SCALES))
    with Pool(processes, initializer=_init_worker) as pool:
        rows = pool.map(_lineup_job, configs)
        chosen = min(rows, key=lambda r: r["fit gain"])
        bonus = pool.apply(_bonus_job, (chosen,)) if chosen["bonus_scale"] > 0 else {"adopted": False}
    without_bonus = min((r for r in rows if r["bonus_scale"] == 0), key=lambda r: r["fit gain"])
    result = {"grid": rows, "chosen": chosen, "best without bonus": without_bonus, "bonus test": bonus,
              "constants": pe.PlayerConstants(anchor_rate=chosen["anchor_rate"],
                                              lineup_weight=chosen["lineup_weight"],
                                              bonus_scale=chosen["bonus_scale"] if bonus["adopted"] else 0).__dict__}
    store.output_path(store.RESULTS_DIR, PLAYER_CONSTANTS_PATH.name).write_text(json.dumps(result, indent=1))
    return result


def load_player_constants() -> pe.PlayerConstants:
    if not PLAYER_CONSTANTS_PATH.exists():
        raise SystemExit("Run `evaluate.py players` first.")
    return pe.PlayerConstants(**json.loads(PLAYER_CONSTANTS_PATH.read_text())["constants"])


# ---------------------------------------------------------------------------
# As-of snapshots


class ChangeRecorder:
    """Per-match rating change of every player who appeared (§5.8, §5.10)."""

    def __init__(self):
        self.rows: list[tuple] = []

    def before(self, players: dict, model: pe.PlayerModel) -> dict:
        return {p: (model.states[p].rating if p in model.states else None)
                for team_players in players.values() for p, _ in team_players}

    def after(self, match: te.Match, players: dict, before: dict, model: pe.PlayerModel) -> None:
        for team, team_players in players.items():
            for player, minutes in team_players:
                previous = before[player]
                if previous is not None:
                    self.rows.append((player, match.day, match.season, team, minutes,
                                      model.states[player].rating - previous))


def fork(runner: pe.PlayerRunner) -> pe.PlayerRunner:
    """A copy that shares the inputs but owns its player states."""
    copy = pe.PlayerRunner.__new__(pe.PlayerRunner)
    copy.__dict__.update(runner.__dict__)
    copy.recorder = None
    copy.lineup_predictions = []
    model = pe.PlayerModel(runner.model.constants, runner.model.team_constants)
    model.states = {p: pe.PlayerState(s.rating, s.last_day, s.team) for p, s in runner.model.states.items()}
    window = runner.model.minutes
    model.minutes.matches = {t: type(d)(d) for t, d in window.matches.items()}
    model.minutes.share_sum = dict(window.share_sum)
    model.minutes.squad = {t: set(s) for t, s in window.squad.items()}
    model.ledger.rows = dict(runner.model.ledger.rows)
    copy.model = model
    return copy


def rate() -> dict:
    """As-of player ratings on the first of every month: history older than the lag
    uses settled swings, the last lag uses that day's corrected swings. The forward
    filter's series is computed alongside for comparison."""
    team_constants = team_checks.load_candidate()
    constants = load_player_constants()
    lag, _ = team_checks.chosen_hindsight()
    replay = team_checks.load_replay()
    matches = te.load_matches()
    predictions, _ = te.run(matches, team_constants)
    inputs = pe.PlayerInputs.load()
    tracked = tracked_ids()

    def settled_sides(index):
        match = matches[index]
        return {team: pe.TeamSide(*replay.settled_swings[(index, team)]) for team in (match.home, match.away)}

    recorder = ChangeRecorder()
    settled = pe.PlayerRunner(matches, predictions, inputs, constants, team_constants)
    forward = pe.PlayerRunner(matches, predictions, inputs, constants, team_constants, recorder)
    rows, pool = [], []
    for snapshot in team_checks.month_starts():
        window = replay.snapshot_window_swings.get(snapshot, {})
        settled.advance_to(snapshot - lag, settled_sides)
        current = fork(settled)

        def window_sides(index, window=window):
            match = matches[index]
            return {team: pe.TeamSide(*(window.get((index, team)) or replay.settled_swings[(index, team)]))
                    for team in (match.home, match.away)}

        current.advance_to(snapshot, window_sides)
        forward.advance_to(snapshot, pe.forward_sides(predictions))
        for player in tracked:
            state = current.model.states.get(player)
            if state is None:
                continue
            rows.append((snapshot, player, current.model.published(player, snapshot),
                         forward.model.published(player, snapshot), state.team, state.last_day))
        if pd.Timestamp(store.EPOCH + pd.Timedelta(days=snapshot)).strftime("%m-%d") == "06-01":
            for player, state in current.model.states.items():
                if snapshot - state.last_day <= 365:
                    pool.append((snapshot, player, current.model.published(player, snapshot), state.team))
    snapshots = pd.DataFrame(rows, columns=["day", "player_id", "rating", "forward_rating", "team_id", "last_day"])
    pool_frame = pd.DataFrame(pool, columns=["day", "player_id", "rating", "team_id"])
    changes = pd.DataFrame(recorder.rows, columns=["player_id", "day", "season", "team_id", "minutes", "change"])
    with open(store.output_path(store.RESULTS_DIR, SNAPSHOTS_PATH.name), "wb") as out:
        pickle.dump({"tracked": snapshots, "pool": pool_frame, "ledger": settled.model.ledger.rows}, out)
    with open(store.output_path(store.RESULTS_DIR, CHANGES_PATH.name), "wb") as out:
        pickle.dump(changes, out)
    gap = (snapshots.rating - snapshots.forward_rating).abs()
    return {"snapshots": int(snapshots.day.nunique()), "tracked players": int(snapshots.player_id.nunique()),
            "hindsight minus forward, |difference|": {"mean": float(gap.mean()), "p90": float(gap.quantile(0.9)),
                                                      "max": float(gap.max())}}


def load_snapshots() -> dict:
    if not SNAPSHOTS_PATH.exists():
        raise SystemExit("Run `evaluate.py rate` first.")
    with open(SNAPSHOTS_PATH, "rb") as source:
        return pickle.load(source)


def load_changes() -> pd.DataFrame:
    with open(CHANGES_PATH, "rb") as source:
        return pickle.load(source)


def day_of(date) -> int:
    return int((pd.Timestamp(date) - store.EPOCH).days)


# ---------------------------------------------------------------------------
# C7: direction against Transfermarkt


def substantial_moves(players: set[int]) -> pd.DataFrame:
    values = store.valuations()
    values = values[values.player_id.isin(players)].sort_values(["player_id", "date"])
    rows = []
    for player, group in values.groupby("player_id"):
        dates, amounts = group.date.to_list(), group.value_eur.to_list()
        for i in range(1, len(dates)):
            before, after = amounts[i - 1], amounts[i]
            if before <= 0 or after <= 0 or max(before, after) < 5_000_000:
                continue
            if abs(math.log(after / before)) >= math.log(1.25):
                rows.append((player, day_of(dates[i]), 1 if after > before else -1))
    return pd.DataFrame(rows, columns=["player_id", "day", "direction"])


class RatingSeries:
    """The as-of rating of each tracked player on any day: the latest monthly
    snapshot on or before it."""

    def __init__(self, snapshots: pd.DataFrame, column: str = "rating"):
        self.series = {p: (g.day.to_numpy(), g[column].to_numpy()) for p, g in snapshots.sort_values("day").groupby("player_id")}

    def at(self, player: int, day: int):
        series = self.series.get(player)
        if series is None:
            return None
        days, ratings = series
        position = np.searchsorted(days, day, side="right") - 1
        if position < 0:
            return None
        return float(ratings[position])


class Coverage:
    """Whether a player appeared in a covered club match within a period."""

    def __init__(self, players: set[int]):
        rows = store.query("""SELECT a.player_id, g.date FROM appearance a JOIN game g ON g.game_id = a.game_id
                              WHERE g.national = 0 AND a.minutes > 0""")
        rows = rows[rows.player_id.isin(players)]
        rows["day"] = (pd.to_datetime(rows.date) - store.EPOCH).dt.days
        self.days = {p: np.sort(g.day.to_numpy()) for p, g in rows.groupby("player_id")}

    def played_between(self, player: int, start: int, end: int) -> bool:
        days = self.days.get(player)
        if days is None:
            return False
        position = np.searchsorted(days, start, side="left")
        return position < len(days) and days[position] < end


def directional(moves: pd.DataFrame, series: RatingSeries, coverage: Coverage, before_months: float,
                after_months: float, lag_months: float = 0) -> dict:
    agree = total = excluded = 0
    last_snapshot = max(days[-1] for days, _ in series.series.values())
    for move in moves.itertuples():
        start = int(move.day + (lag_months - before_months) * MONTH)
        end = int(move.day + (lag_months + after_months) * MONTH)
        if end > last_snapshot or not (coverage.played_between(move.player_id, start, move.day)
                                       and coverage.played_between(move.player_id, move.day, end)):
            excluded += 1
            continue
        first, last = series.at(move.player_id, start), series.at(move.player_id, end)
        if first is None or last is None:
            excluded += 1
            continue
        total += 1
        change = last - first
        if abs(change) >= 1.0 and math.copysign(1, change) == move.direction:
            agree += 1
    share = agree / total if total else float("nan")
    return {"moves": total, "excluded": excluded, "agree": agree, "share": share,
            "p_value": binomial_tail(agree, total)}


def binomial_tail(successes: int, trials: int) -> float:
    """P(X ≥ successes) for X ~ Binomial(trials, 1/2), exactly."""
    if trials == 0:
        return float("nan")
    tail = sum(math.comb(trials, k) for k in range(successes, trials + 1))
    return tail / 2 ** trials


def transfermarkt() -> dict:
    snapshots = load_snapshots()["tracked"]
    result = {}
    for set_name, players in (("set A", set(set_a_ids())), ("set B", set(set_b_groups()))):
        moves = substantial_moves(players)
        coverage = Coverage(players)
        hindsight = RatingSeries(snapshots[snapshots.player_id.isin(players)])
        forward = RatingSeries(snapshots[snapshots.player_id.isin(players)], "forward_rating")
        result[set_name] = {
            "primary window (−6, +6 months)": directional(moves, hindsight, coverage, 6, 6),
            "forward-only series, primary window": directional(moves, forward, coverage, 6, 6),
            "window scan": {f"−{b}/+{a}": directional(moves, hindsight, coverage, b, a)["share"]
                            for b, a in [(3, 3), (6, 6), (6, 12), (12, 12)]},
            "lag scan (centre of a 12-month window)": {
                f"{lag:+d}": directional(moves, hindsight, coverage, 6, 6, lag)["share"] for lag in range(-12, 13, 3)},
            "rises": directional(moves[moves.direction > 0], hindsight, coverage, 6, 6),
            "falls": directional(moves[moves.direction < 0], hindsight, coverage, 6, 6),
        }
    return result


# ---------------------------------------------------------------------------
# C8: convergence


def separating_events(players: set[int]) -> dict[int, list[int]]:
    """Days on which each player was split from his usual context: a team match during
    his stint that he missed or played under half of, a move to another team, or a
    national-team match."""
    rows = store.query("""SELECT a.player_id, a.team_id, a.minutes, g.date, g.national FROM appearance a
                          JOIN game g ON g.game_id = a.game_id""")
    rows = rows[rows.player_id.isin(players)]
    rows["day"] = (pd.to_datetime(rows.date) - store.EPOCH).dt.days
    games = store.club_games()
    team_days = {}
    for team, group in pd.concat([games[["home_team_id", "day"]].set_axis(["team", "day"], axis=1),
                                  games[["away_team_id", "day"]].set_axis(["team", "day"], axis=1)]).groupby("team"):
        team_days[team] = np.sort(group.day.unique())
    events = {}
    for player, group in rows.groupby("player_id"):
        days = []
        club = group[group.national == 0].sort_values("day")
        days += group[group.national == 1].day.tolist()
        previous_team = None
        for team, stint in club.groupby((club.team_id != club.team_id.shift()).cumsum()):
            team_id = int(stint.team_id.iloc[0])
            if previous_team is not None and team_id != previous_team:
                days.append(int(stint.day.iloc[0]))
            previous_team = team_id
            played = dict(zip(stint.day, stint.minutes))
            schedule = team_days.get(team_id, np.array([]))
            inside = schedule[(schedule >= stint.day.min()) & (schedule <= stint.day.max())]
            days += [int(d) for d in inside if played.get(d, 0) < 45]
        events[player] = sorted(set(days))
    return events


def convergence() -> dict:
    groups = player_groups()
    players = set(groups)
    events = separating_events(players)
    coverage = Coverage(players)
    first_seen = {p: int(d[0]) for p, d in coverage.days.items() if len(d)}
    waits, within_season, gaps = [], 0, []
    eligible = 0
    for player, first in first_seen.items():
        last = coverage.days[player][-1]
        if last - first < 365:
            continue
        eligible += 1
        later = [d for d in events.get(player, []) if d >= first]
        if later:
            waits.append(later[0] - first)
            within_season += later[0] - first <= 365
            gaps += list(np.diff(later))
    snapshots = load_snapshots()["tracked"]
    series = RatingSeries(snapshots)
    moves = substantial_moves(players)
    catch_up = catch_up_times(moves, series, coverage)
    per_player = catch_up.groupby("player_id").agg(moves=("caught", "size"), caught=("caught", "mean"),
                                                   median_months=("months", "median"))
    per_player["group"] = [groups[p] for p in per_player.index]
    by_group = per_player.groupby("group").agg(players=("moves", "size"), moves=("moves", "sum"),
                                               caught=("caught", "mean"), median_months=("median_months", "median"))
    failing = by_group[(by_group.players >= 5) & (by_group.caught < 0.4)]
    names = store.players().set_index("player_id")["name"].to_dict()
    never = per_player[per_player.caught == 0].index
    return {
        "a": {"eligible players": eligible, "separating event within first covered season": within_season / eligible,
              "mean days to first event": float(np.mean(waits)), "max days to first event": int(np.max(waits)),
              "mean days between events": float(np.mean(gaps)), "p90 days between events": float(np.percentile(gaps, 90)),
              "longest stretch without an event (days)": int(np.max(gaps))},
        "b": {"catch-up rate by group": by_group.round(3).reset_index().to_dict("records"),
              "groups below 40%": failing.reset_index().to_dict("records"),
              "players never caught up": [names.get(p, p) for p in never]},
        "longest stretches": longest_stretches(events, coverage, names),
    }


def player_groups() -> dict[int, str]:
    positions = store.players().set_index("player_id").position.to_dict()
    groups = {p: f"set A {str(positions.get(p, 'Missing')).lower()}" for p in set_a_ids()}
    groups.update({p: f"set B {g}" for p, g in set_b_groups().items()})
    return groups


def catch_up_times(moves: pd.DataFrame, series: RatingSeries, coverage: Coverage) -> pd.DataFrame:
    """For each substantial Transfermarkt move: the first month, up to 24, at which the
    rating has moved at least 10 points the same way since 6 months before it."""
    rows = []
    last_snapshot = max(days[-1] for days, _ in series.series.values())
    for move in moves.itertuples():
        start = int(move.day - 6 * MONTH)
        if move.day + 24 * MONTH > last_snapshot or not coverage.played_between(move.player_id, start, move.day):
            continue
        base = series.at(move.player_id, start)
        if base is None:
            continue
        months = None
        for month in range(0, 25):
            later = series.at(move.player_id, int(move.day + month * MONTH))
            if later is not None and (later - base) * move.direction >= 10:
                months = month
                break
        rows.append((move.player_id, move.day, move.direction, months is not None, months))
    return pd.DataFrame(rows, columns=["player_id", "day", "direction", "caught", "months"])


def longest_stretches(events: dict, coverage: Coverage, names: dict) -> list:
    stretches = []
    for player, days in events.items():
        played = coverage.days.get(player)
        if played is None or len(days) < 2:
            continue
        inside = [d for d in days if played[0] <= d <= played[-1]]
        if len(inside) < 2:
            continue
        gap = np.diff(inside)
        position = int(np.argmax(gap))
        stretches.append((names.get(player, player), int(gap[position]),
                          str((store.EPOCH + pd.Timedelta(days=int(inside[position]))).date())))
    return sorted(stretches, key=lambda s: -s[1])[:10]


# ---------------------------------------------------------------------------
# C10: pairs that never separate


def collinearity() -> dict:
    """Pairs of team-mates who, over a whole season of at least 20 team matches,
    always played the same share of every match (both full, or both absent)."""
    appearances = store.query("""SELECT a.player_id, a.team_id, a.minutes, g.game_id, g.season, g.date
                                 FROM appearance a JOIN game g ON g.game_id = a.game_id WHERE g.national = 0""")
    games = store.club_games()
    team_games = pd.concat([games[["game_id", "season", "home_team_id"]].set_axis(["game_id", "season", "team_id"], axis=1),
                            games[["game_id", "season", "away_team_id"]].set_axis(["game_id", "season", "team_id"], axis=1)])
    covered = set(appearances.game_id)
    team_games = team_games[team_games.game_id.isin(covered)]
    changes = load_changes()
    change_index = changes.set_index(["player_id", "day"]).change
    names = store.players().set_index("player_id")["name"].to_dict()
    teams = store.teams().set_index("team_id")["name"].to_dict()
    pairs = []
    for (team, season), schedule in team_games.groupby(["team_id", "season"]):
        if len(schedule) < 20:
            continue
        played = appearances[(appearances.team_id == team) & (appearances.season == season)]
        share = played.pivot_table(index="game_id", columns="player_id", values="minutes", aggfunc="sum")
        share = share.reindex(schedule.game_id).fillna(0) / 90.0
        regulars = [p for p in share.columns if (share[p] > 0).sum() >= 15]
        for a, b in itertools.combinations(regulars, 2):
            if (share[a] - share[b]).abs().max() <= 0.1:
                pairs.append((team, season, a, b))
    rows = []
    dates = games.set_index("game_id").day
    for team, season, a, b in pairs:
        schedule = team_games[(team_games.team_id == team) & (team_games.season == season)].game_id
        days = sorted(dates.loc[schedule].tolist())
        first = change_index.reindex([(a, d) for d in days]).to_numpy()
        second = change_index.reindex([(b, d) for d in days]).to_numpy()
        both = ~np.isnan(first) & ~np.isnan(second)
        if both.sum() < 10:
            continue
        correlation = float(np.corrcoef(first[both], second[both])[0, 1])
        rows.append({"team": teams.get(team, team), "season": f"{season}/{(season + 1) % 100:02d}",
                     "first": names.get(a, a), "second": names.get(b, b), "matches": int(both.sum()),
                     "correlation": round(correlation, 4)})
    frame = pd.DataFrame(rows)
    return {"pairs": len(frame), "share with correlation ≥ 0.99": float((frame.correlation >= 0.99).mean()) if len(frame) else None,
            "lowest correlations": frame.sort_values("correlation").head(5).to_dict("records") if len(frame) else [],
            "examples": frame.sort_values("matches", ascending=False).head(10).to_dict("records") if len(frame) else []}


# ---------------------------------------------------------------------------
# Minutes bonus: confounds


def confounds() -> dict:
    """Does a regular's absence hurt his team as much as his minutes say? Regress each
    team's surprise in a match (actual minus expected score, team-only prediction) on
    the absences of its regular starters, weighted by their start share. A smaller
    coefficient for one group means its minutes say less about its quality."""
    constants = team_checks.load_candidate()
    matches = te.load_matches()
    predictions, _ = te.run(matches, constants)
    lineups = store.lineups()
    starters = lineups[lineups.starter == 1].groupby(["game_id", "team_id"]).player_id.apply(set).to_dict()
    fees = signing_fees()
    positions = store.players().set_index("player_id").position.to_dict()
    rows = []
    by_team_season = {}
    for prediction in predictions:
        match = prediction.match
        for team in (match.home, match.away):
            if (match.game_id, team) in starters:
                by_team_season.setdefault((team, match.season), []).append((prediction, team))
    for (team, season), entries in by_team_season.items():
        if len(entries) < 20:
            continue
        counts = {}
        for prediction, _ in entries:
            for player in starters[(prediction.match.game_id, team)]:
                counts[player] = counts.get(player, 0) + 1
        share = {p: c / len(entries) for p, c in counts.items()}
        regulars = [p for p, s in share.items() if s >= 0.6]
        squad_fees = sorted(((fees.get((p, team), 0), p) for p in share), reverse=True)
        fee_rank = {p: rank for rank, (fee, p) in enumerate(squad_fees, start=1) if fee > 0}
        depth = {}
        for p, s in share.items():
            group = positions.get(p, "Missing")
            depth[group] = depth.get(group, 0) + (s >= 0.1)
        for prediction, _ in entries:
            match = prediction.match
            expected = te.expected_score(prediction.rating_difference)
            surprise = te.score_of(match.goal_difference) - expected
            if team == match.away:
                surprise = -surprise
            if min(prediction.home_prior_matches, prediction.away_prior_matches) < te.MIN_PRIOR_MATCHES:
                continue
            eleven = starters[(match.game_id, team)]
            features = {"top 2 by fee": 0.0, "fee rank 3–5": 0.0, "other regulars": 0.0, "thin position": 0.0,
                        "deep position": 0.0}
            for player in regulars:
                if player in eleven:
                    continue
                rank = fee_rank.get(player)
                group = "top 2 by fee" if rank is not None and rank <= 2 else (
                    "fee rank 3–5" if rank is not None and rank <= 5 else "other regulars")
                features[group] += share[player]
                thin = depth.get(positions.get(player, "Missing"), 0) <= 2
                features["thin position" if thin else "deep position"] += share[player]
            rows.append({**features, "surprise": surprise})
    frame = pd.DataFrame(rows)
    return {"team matches": len(frame),
            "by fee rank": regression(frame, ["top 2 by fee", "fee rank 3–5", "other regulars"]),
            "by squad depth": regression(frame, ["thin position", "deep position"])}


def signing_fees() -> dict[tuple[int, int], int]:
    """The fee a team paid to sign a player (its latest signing of him)."""
    transfers = store.transfers().dropna(subset=["fee_eur", "to_team_id"]).sort_values("date")
    return {(int(p), int(t)): int(f) for p, t, f in zip(transfers.player_id, transfers.to_team_id, transfers.fee_eur)}


def regression(frame: pd.DataFrame, columns: list[str], resamples: int = 500) -> dict:
    """Least squares with an intercept; 95% bootstrap intervals."""
    x = np.column_stack([np.ones(len(frame))] + [frame[c].to_numpy() for c in columns])
    y = frame.surprise.to_numpy()
    coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    rng = np.random.default_rng(11)
    draws = []
    for _ in range(resamples):
        sample = rng.integers(0, len(y), len(y))
        draws.append(np.linalg.lstsq(x[sample], y[sample], rcond=None)[0])
    draws = np.array(draws)
    result = {}
    for i, column in enumerate(columns, start=1):
        low, high = np.percentile(draws[:, i], [2.5, 97.5])
        result[column] = {"per unit of start share": round(float(coefficients[i]), 4),
                          "interval": [round(float(low), 4), round(float(high), 4)],
                          "absences counted": int((frame[column] > 0).sum())}
    return result


# ---------------------------------------------------------------------------
# Positions


def positions() -> dict:
    changes = load_changes()
    position = store.players().set_index("player_id").position.to_dict()
    changes["position"] = changes.player_id.map(position).fillna("Missing")
    seasons = changes.groupby(["player_id", "season"]).filter(lambda g: len(g) >= 15)
    per_match = seasons.groupby("position").change.agg(
        matches="size", std="std", skew=lambda s: float(pd.Series(s).skew()),
        p05=lambda s: float(np.percentile(s, 5)), p95=lambda s: float(np.percentile(s, 95)))
    rolling = (seasons.sort_values("day").groupby(["player_id", "season"]).change
               .apply(lambda s: s.rolling(10).sum().dropna()).reset_index(level=[0, 1]))
    rolling["position"] = rolling.player_id.map(position).fillna("Missing")
    ten = rolling.groupby("position").change.agg(
        p05=lambda s: float(np.percentile(s, 5)), p95=lambda s: float(np.percentile(s, 95)),
        skew=lambda s: float(pd.Series(s).skew()))
    minutes = seasons.groupby("position").minutes.mean()
    table = per_match.join(ten, rsuffix=" over 10 matches").join(minutes.rename("mean minutes"))
    return {"table": table.round(3).reset_index().to_dict("records")}


# ---------------------------------------------------------------------------
# National teams


def national() -> dict:
    """National-team matches with line-ups: how well the club-derived line-up predicts
    them, and how much the calibration moves ratings."""
    team_constants = team_checks.load_candidate()
    constants = load_player_constants()
    matches = te.load_matches()
    predictions, _ = te.run(matches, team_constants)
    inputs = pe.PlayerInputs.load()
    games = inputs.national_games
    covered = games[games.game_id.isin(inputs.appearances)]
    runner = pe.PlayerRunner(matches, predictions, inputs, constants, team_constants)
    rows = []
    for game in covered.itertuples():
        runner.advance_to(game.day, pe.forward_sides(predictions))
        strengths = {}
        for team in (game.home_team_id, game.away_team_id):
            lineup = inputs.appearances[game.game_id].get(team, [])
            rated = [(runner.model.published(p, game.day), m) for p, m in lineup]
            known = [(r, m) for r, m in rated if r is not None]
            total = sum(m for _, m in rated)
            if total and sum(m for _, m in known) >= 0.6 * total:
                strengths[team] = sum(r * m for r, m in known) / sum(m for _, m in known)
        if len(strengths) == 2:
            home_advantage = 0.0 if game.neutral else team_constants.home_advantage
            rows.append({"competition": game.competition_id,
                         "difference": strengths[game.home_team_id] + home_advantage - strengths[game.away_team_id],
                         "outcome": te.outcome_of(game.goal_difference)})
    frame = pd.DataFrame(rows)
    logit = te.OrderedLogit(**json.loads(team_checks.CONSTANTS_PATH.read_text())["logit"])
    probabilities = logit.probabilities(frame.difference.to_numpy())
    loss, _ = te.match_losses(probabilities, frame.outcome.to_numpy())
    base = np.bincount(frame.outcome, minlength=3) / len(frame)
    naive, _ = te.match_losses(np.tile(base, (len(frame), 1)), frame.outcome.to_numpy())
    ledger = runner.model.ledger.rows
    calibration = sum(v for (s, source), v in ledger.items() if source == "national-team calibration")
    return {"matches with line-ups": int(len(covered)), "matches rated (≥60% of minutes known)": int(len(frame)),
            "by competition": frame.competition.value_counts().to_dict(),
            "log loss, club-derived line-up strength": float(loss.mean()),
            "log loss, outcome frequencies only (in-sample)": float(naive.mean()),
            "net calibration flow (Elo points, all players)": float(calibration)}
