"""Hindsight correction of opponent strength, float reference (FINDINGS.md §4.4).

Each team's strength is a random walk: its variance grows by `process_noise` per
day. The forward filter (teamelo.run) estimates it from earlier matches only.
Then, as of every match day:

1. **Backward pass.** For every team, its own later matches are folded back in
   time (a Rauch-Tung-Striebel style smoother, written in information form).
   Folding back adds the random walk's variance for every day crossed, so a later
   result says less about an earlier date the more time lies between them. No
   decay is written by hand.
2. **Cavity.** At each match, the opponent's corrected strength is its forward
   estimate before the match combined with the backward information from its
   later matches, leaving out the match itself (the cavity distribution of
   expectation propagation). It is a precision-weighted blend, never a
   replacement: a later slump cannot tell "overrated then" from "declined since".
3. **Replay.** Each team's rating is recomputed forward with every opponent at
   its corrected strength. The end of the replay is the rating published that day.

Propagation depth: one iteration corrects an opponent by its own later matches
only. Each further iteration rebuilds the backward pass from the replay, so
corrections travel one more step through the connected history (towards the
joint fit TrueSkill Through Time computes).

Lag: a match older than `lag_days` is settled. Its opponent's correction then
used exactly `lag_days` of later matches and never changes again, so the rating
for any date is final once `lag_days` have passed.
"""

import math
from dataclasses import dataclass, field

import teamelo as te

INFINITE = math.inf


@dataclass
class ReplayResult:
    as_of_differences: dict = field(default_factory=dict)      # match index -> rating difference before kick-off
    settled_swings: dict = field(default_factory=dict)         # (match index, team) -> (rating before, swing) once settled
    snapshot_states: dict = field(default_factory=dict)        # snapshot day -> {team: rating}
    snapshot_window_swings: dict = field(default_factory=dict)  # snapshot day -> {(match index, team): (rating before, swing)}
    day_off_moves: list = field(default_factory=list)          # |move| of a team's rating on a day it did not play
    revisions: list = field(default_factory=list)              # (reference day, weeks later, team, rating)


class HindsightReplay:

    def __init__(self, matches: list[te.Match], predictions: list[te.Prediction], constants: te.TeamConstants,
                 lag_days: int, iterations: int = 1):
        self.matches = matches
        self.constants = constants
        self.lag_days = lag_days
        self.iterations = iterations
        self.side_index: dict[tuple[int, int], int] = {}
        self.side_team: list[int] = []
        self.side_opponent: list[int] = []
        self.side_is_home: list[bool] = []
        self.side_match: list[int] = []
        self.sides_of_team: dict[int, list[int]] = {}
        self.forward_prior: list[tuple[float, float]] = []
        self.forward_message: list[tuple[float, float]] = []
        self.seed: dict[int, float] = {}
        self.index_sides(predictions)

    def index_sides(self, predictions: list[te.Prediction]) -> None:
        for match_index, prediction in enumerate(predictions):
            match = prediction.match
            views = (
                (match.home, match.away, True, prediction.home_rating, prediction.home_variance,
                 prediction.home_swing, prediction.home_posterior_variance, prediction.home_seed),
                (match.away, match.home, False, prediction.away_rating, prediction.away_variance,
                 prediction.away_swing, prediction.away_posterior_variance, prediction.away_seed),
            )
            for team, opponent, is_home, prior_mean, prior_variance, swing, posterior_variance, seed in views:
                if seed is not None:
                    self.seed[team] = seed
                side = len(self.side_team)
                self.side_index[(match_index, team)] = side
                self.side_team.append(team)
                self.side_opponent.append(opponent)
                self.side_is_home.append(is_home)
                self.side_match.append(match_index)
                self.sides_of_team.setdefault(team, []).append(side)
                self.forward_prior.append((prior_mean, prior_variance))
                self.forward_message.append(message_of(prior_mean, prior_variance, swing, posterior_variance))

    def run(self, snapshot_days=(), reference_days=(), tracked_teams=frozenset()) -> ReplayResult:
        """One as-of pass per match day and per snapshot day. A pass for day D sees the
        matches played before D: it is the rating published at the start of D."""
        match_days = sorted({match.day for match in self.matches})
        matches_by_day: dict[int, list[int]] = {}
        for index, match in enumerate(self.matches):
            matches_by_day.setdefault(match.day, []).append(index)
        snapshot_set = set(snapshot_days)
        days = sorted(set(match_days) | snapshot_set)
        result = ReplayResult()
        settled: dict[int, tuple[float, float, int]] = {}
        settled_until = days[0]
        tracker = RevisionTracker(sorted(reference_days), tracked_teams, self.lag_days)
        previous_ratings: dict[int, float] = {}
        previous_day = None
        for as_of in days:
            window_start = as_of - self.lag_days
            window = [m for d in match_days if settled_until <= d < as_of for m in matches_by_day[d]]
            cavities = self.cavities(window, settled)
            to_settle = [m for m in window if self.matches[m].day < window_start]
            active = [m for m in window if self.matches[m].day >= window_start]
            settled, _, settle_swings = self.replay(to_settle, settled, cavities)
            result.settled_swings.update(settle_swings)
            settled_until = max(settled_until, window_start)
            tracker.start(as_of, window_start)
            states, _, active_swings = self.replay(active, settled, cavities, tracker)
            tracker.finish(states)
            ratings_now = {team: state[0] for team, state in states.items()}
            if as_of in snapshot_set:
                result.snapshot_states[as_of] = ratings_now
                result.snapshot_window_swings[as_of] = active_swings
            last_active_swings = active_swings
            if as_of not in matches_by_day:
                continue
            for match_index in matches_by_day[as_of]:
                result.as_of_differences[match_index] = self.difference_now(match_index, states)
            if previous_day is not None:
                played = {self.matches[m].home for m in matches_by_day[previous_day]} | {
                    self.matches[m].away for m in matches_by_day[previous_day]}
                for team in tracked_teams:
                    if team in ratings_now and team in previous_ratings and team not in played:
                        result.day_off_moves.append(abs(ratings_now[team] - previous_ratings[team]))
            previous_ratings = {team: ratings_now[team] for team in tracked_teams if team in ratings_now}
            previous_day = as_of
        for key, swing in last_active_swings.items():
            result.settled_swings.setdefault(key, swing)
        result.revisions = tracker.records
        return result

    def cavities(self, window: list[int], settled: dict) -> dict[int, tuple[float, float]]:
        """Each side's opponent-free estimate, after `iterations` rounds."""
        priors, messages = self.forward_prior, self.forward_message
        cavities = self.backward(window, priors, messages)
        for _ in range(self.iterations - 1):
            _, (priors, messages), _ = self.replay(window, settled, cavities, record_messages=True)
            cavities = self.backward(window, priors, messages)
        return cavities

    def backward(self, window: list[int], priors, messages) -> dict[int, tuple[float, float]]:
        in_window = set(window)
        teams = {self.matches[m].home for m in window} | {self.matches[m].away for m in window}
        noise = self.constants.process_noise
        cavities = {}
        for team in teams:
            sides = [s for s in self.sides_of_team[team] if self.side_match[s] in in_window]
            precision, information, later_day = 0.0, 0.0, None
            for side in reversed(sides):
                day = self.matches[self.side_match[side]].day
                if later_day is not None and precision > 0.0:
                    variance = 1.0 / precision + noise * (later_day - day)
                    information = information / precision / variance
                    precision = 1.0 / variance
                prior_mean, prior_variance = priors[side]
                cavity_precision = 1.0 / prior_variance + precision
                cavity_mean = (prior_mean / prior_variance + information) / cavity_precision
                cavities[side] = (cavity_mean, 1.0 / cavity_precision)
                message_mean, message_variance = messages[side]
                if message_variance < INFINITE:
                    precision += 1.0 / message_variance
                    information += message_mean / message_variance
                later_day = day
        return cavities

    def replay(self, match_indices: list[int], base: dict, cavities: dict, tracker=None, record_messages=False):
        """Forward pass from `base` over the given matches, every opponent at its
        cavity. Returns the states after them, optionally each side's prior and
        message, and each side's rating before the match with its swing."""
        states = dict(base)
        priors = list(self.forward_prior) if record_messages else None
        messages = list(self.forward_message) if record_messages else None
        swings = {}
        for day_matches in by_day(match_indices, self.matches):
            day = self.matches[day_matches[0]].day
            if tracker is not None:
                tracker.before_day(day, states)
            updates = []
            for match_index in day_matches:
                match = self.matches[match_index]
                for team in (match.home, match.away):
                    side = self.side_index[(match_index, team)]
                    mean, variance = self.state_before(team, day, states)
                    opponent_side = self.side_index[(match_index, self.side_opponent[side])]
                    opponent_mean, opponent_variance = cavities[opponent_side]
                    swing, posterior = side_update(match, self.side_is_home[side], mean, variance,
                                                   opponent_mean, opponent_variance, self.constants)
                    if record_messages:
                        priors[side] = (mean, variance)
                        messages[side] = message_of(mean, variance, swing, posterior)
                    swings[(match_index, team)] = (mean, swing)
                    updates.append((team, swing, posterior, day))
            apply_day(updates, states, self.seed, self.constants)
        return states, (priors, messages), swings

    def state_before(self, team: int, day: int, states: dict) -> tuple[float, float]:
        if team not in states:
            return self.seed.get(team, te.INITIAL_RATING), self.constants.initial_variance
        mean, variance, last_day = states[team]
        aged = variance + self.constants.process_noise * (day - last_day)
        return mean, min(aged, self.constants.initial_variance)

    def difference_now(self, match_index: int, states: dict) -> float:
        match = self.matches[match_index]
        home = states[match.home][0] if match.home in states else self.seed.get(match.home, te.INITIAL_RATING)
        away = states[match.away][0] if match.away in states else self.seed.get(match.away, te.INITIAL_RATING)
        home_advantage = 0.0 if match.neutral else self.constants.home_advantage
        return home + home_advantage - away


def apply_day(updates: list, states: dict, seed: dict, constants: te.TeamConstants) -> None:
    """A day is one batch, as in the forward filter: swings add up, and a team that
    played twice keeps the variance of its last match."""
    for team, swing, variance, day in updates:
        mean = states[team][0] if team in states else seed.get(team, te.INITIAL_RATING)
        states[team] = (mean + swing, variance, day)


def message_of(prior_mean: float, prior_variance: float, swing: float, posterior_variance: float) -> tuple[float, float]:
    """The Gaussian message a match sent about a team: the observation that turns the
    prior into the posterior. Its precision is the precision gained; its mean is where
    the observation would sit on its own."""
    gained_precision = 1.0 / posterior_variance - 1.0 / prior_variance
    if gained_precision <= 1e-15:
        return 0.0, INFINITE
    message_variance = 1.0 / gained_precision
    message_mean = prior_mean + swing * (1.0 + message_variance / prior_variance)
    return message_mean, message_variance


def side_update(match: te.Match, is_home: bool, mean: float, variance: float,
                opponent_mean: float, opponent_variance: float, constants: te.TeamConstants) -> tuple[float, float]:
    """One team's Kalman step against an opponent known only as a distribution."""
    home_advantage = 0.0 if match.neutral else constants.home_advantage
    if is_home:
        difference = mean + home_advantage - opponent_mean
    else:
        difference = opponent_mean + home_advantage - mean
    direction = 1.0 if is_home else -1.0
    swing = 0.0
    for observed, scale, information in te.observations_of(match, difference, constants):
        expected = te.expected_score(scale * difference)
        surprise = observed - expected
        slope = te.LOGISTIC_SLOPE * scale
        spread = expected * (1.0 - expected)
        denominator = 1.0 + information * slope * slope * spread * (variance + opponent_variance)
        gain = variance * slope * information / denominator
        opponent_gain = opponent_variance * slope * information / denominator
        swing += direction * gain * surprise
        variance -= gain * slope * spread * variance
        opponent_variance -= opponent_gain * slope * spread * opponent_variance
    return swing, variance


def by_day(match_indices: list[int], matches: list[te.Match]) -> list[list[int]]:
    grouped, current, current_day = [], [], None
    for index in sorted(match_indices, key=lambda m: (matches[m].day, m)):
        day = matches[index].day
        if day != current_day and current:
            grouped.append(current)
            current = []
        current_day = day
        current.append(index)
    if current:
        grouped.append(current)
    return grouped


class RevisionTracker:
    """The replayed rating for a reference day, as each later as-of day recomputes
    it: how long a rating for a date keeps moving. One record per team per week."""

    def __init__(self, reference_days: list[int], tracked_teams, lag_days: int):
        self.reference_days = reference_days
        self.tracked_teams = tracked_teams
        self.lag_days = lag_days
        self.records: list[tuple[int, int, int, float]] = []
        self.weeks_recorded: dict[int, int] = {}
        self.pending: list[int] = []
        self.as_of = 0

    def start(self, as_of: int, window_start: int) -> None:
        self.as_of = as_of
        self.pending = [r for r in self.reference_days
                        if window_start <= r <= as_of and self.weeks_recorded.get(r, -1) < (as_of - r) // 7]

    def before_day(self, day: int, states: dict) -> None:
        while self.pending and self.pending[0] <= day:
            self.record(self.pending.pop(0), states)

    def finish(self, states: dict) -> None:
        while self.pending:
            self.record(self.pending.pop(0), states)

    def record(self, reference: int, states: dict) -> None:
        weeks = (self.as_of - reference) // 7
        self.weeks_recorded[reference] = weeks
        for team in self.tracked_teams:
            if team in states:
                self.records.append((reference, weeks, team, states[team][0]))
