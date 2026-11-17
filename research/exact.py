"""Exact integer reference implementation (FINDINGS.md §6).

This is the version the Java port must reproduce bit for bit. The float modules
(teamelo, hindsight, playerelo) are for exploring and fitting; this one fixes
every number.

Units. Every quantity is an integer in a stated unit:

    rating          milli-Elo                     (1 Elo point = 1000)
    variance        thousandths of an Elo point²  (1 Elo² = 1000)
    precision       10⁻¹² per Elo point²          (= 10¹⁵ ÷ variance)
    probability     billionths                    (1 = 10⁹)
    weight          thousandths                   (1 = 1000)
    slope           10⁻⁹ per Elo point            (ln 10 ÷ 400 = 5 756 463)
    share of match  three-hundred-sixtieths       (90 min = 360, so 4 per minute; 120 min: 3 per minute)

Rounding. Every division rounds to the nearest integer, ties towards +∞:
divide_rounded(a, b) = floor((2a + b) ÷ 2b) for b > 0. In Java:
Math.floorDiv(2a + b, 2b) with Math.addExact and Math.multiplyExact. Where parts
must add up to a whole (a team swing shared by minutes, the minutes bonus), the
whole is rounded once and shared by largest remainder, ties to the lower player id.

Overflow. Every product and sum passes through checked(): the reference fails if
any intermediate leaves the signed 64-bit range, so a Java port with Math.*Exact
never throws on the same input.

Order. Matches are processed by date, then game id. Each day is one batch: every
match that day is computed from the ratings at the start of the day. A player's
updates within a day are summed. The result does not depend on input row order.

As of. The rating published for day D uses the matches played before D.
"""

import decimal
from collections import ChainMap
from dataclasses import dataclass, field
from fractions import Fraction
from typing import NamedTuple

import pandas as pd

import store
import teamelo as te

RATING_UNIT = 1000
VARIANCE_UNIT = 1000
PROBABILITY = 10 ** 9
WEIGHT = 1000
PRECISION_NUMERATOR = 10 ** 15
SLOPE = 5_756_463
FULL_MATCH = 360
TABLE_RANGE_ELO = 1600
INITIAL_RATING = 1500 * RATING_UNIT

LIMIT = 2 ** 63


def checked(value: int) -> int:
    if -LIMIT <= value < LIMIT:
        return value
    raise OverflowError(f"intermediate {value} leaves the signed 64-bit range")


def multiply(first: int, second: int, third: int | None = None) -> int:
    """Left to right, every partial product checked, as a chain of Math.multiplyExact."""
    product = first * second
    if not -LIMIT <= product < LIMIT:
        raise OverflowError(f"intermediate {product} leaves the signed 64-bit range")
    if third is None:
        return product
    product *= third
    if not -LIMIT <= product < LIMIT:
        raise OverflowError(f"intermediate {product} leaves the signed 64-bit range")
    return product


def add(first: int, second: int, third: int = 0) -> int:
    """Left to right, every partial sum checked, as a chain of Math.addExact."""
    total = first + second
    if not -LIMIT <= total < LIMIT:
        raise OverflowError(f"intermediate {total} leaves the signed 64-bit range")
    total += third
    if not -LIMIT <= total < LIMIT:
        raise OverflowError(f"intermediate {total} leaves the signed 64-bit range")
    return total


def total_of(values) -> int:
    total = 0
    for value in values:
        total += value
        if not -LIMIT <= total < LIMIT:
            raise OverflowError(f"intermediate {total} leaves the signed 64-bit range")
    return total


def divide_rounded(numerator: int, denominator: int) -> int:
    """Nearest integer, ties towards +∞: floor((2 × numerator + denominator) ÷ (2 × denominator)).
    The denominator is positive."""
    if denominator <= 0:
        raise ZeroDivisionError("denominator must be positive")
    twice = 2 * numerator
    shifted = twice + denominator
    if not (-LIMIT <= twice < LIMIT and -LIMIT <= shifted < LIMIT and 2 * denominator < LIMIT):
        raise OverflowError("intermediate leaves the signed 64-bit range")
    return shifted // (2 * denominator)


def apportion(whole: int, numerators: dict[int, int], denominator: int) -> dict[int, int]:
    """Shares numerators[k] ÷ denominator of `whole`... rounded so they sum to `whole`:
    every part is floored, then the remaining units go to the largest remainders,
    ties to the lower key."""
    floors = {key: n // denominator for key, n in numerators.items()}
    remainders = {key: n % denominator for key, n in numerators.items()}
    missing = whole - sum(floors.values())
    order = sorted(numerators, key=lambda key: (-remainders[key], key))
    if missing >= 0:
        for key in order[:missing]:
            floors[key] += 1
    else:
        for key in sorted(numerators, key=lambda key: (remainders[key], key))[:-missing]:
            floors[key] -= 1
    return floors


# ---------------------------------------------------------------------------
# Expected score


def expected_score_table() -> list[int]:
    """E(k) = 1 ÷ (1 + 10^(−k/400)) for whole Elo differences k in [−1600, 1600], in
    billionths, rounded half to even from a 60-digit computation (decimal's exp and
    ln are correctly rounded). Published with the constants; the Java port loads it."""
    context = decimal.Context(prec=60, rounding=decimal.ROUND_HALF_EVEN)
    ln10 = context.ln(decimal.Decimal(10))
    table = []
    for difference in range(-TABLE_RANGE_ELO, TABLE_RANGE_ELO + 1):
        exponent = context.multiply(ln10, context.divide(decimal.Decimal(-difference), decimal.Decimal(400)))
        value = context.divide(decimal.Decimal(PROBABILITY), context.add(decimal.Decimal(1), context.exp(exponent)))
        table.append(int(value.quantize(decimal.Decimal(1), rounding=decimal.ROUND_HALF_EVEN)))
    return table


EXPECTED = expected_score_table()


def expected_score(difference: int) -> int:
    """Linear interpolation between whole Elo points; saturates outside ±1600."""
    bound = TABLE_RANGE_ELO * RATING_UNIT
    clamped = max(-bound, min(bound, difference))
    whole_points = clamped // RATING_UNIT
    fraction = clamped - whole_points * RATING_UNIT
    position = whole_points + TABLE_RANGE_ELO
    if fraction == 0:
        return EXPECTED[position]
    step = EXPECTED[position + 1] - EXPECTED[position]
    return EXPECTED[position] + divide_rounded(multiply(step, fraction), RATING_UNIT)


# ---------------------------------------------------------------------------
# Constants in integer form


@dataclass(frozen=True)
class ExactTeamConstants:
    process_noise: int          # variance per day
    initial_variance: int
    home_advantage: int         # milli-Elo
    league_seed_offset: int
    unknown_seed_offset: int
    corner_scale: int           # thousandths
    corner_weight: int          # thousandths
    lag_days: int
    iterations: int

    @staticmethod
    def from_float(constants: te.TeamConstants, lag_days: int, iterations: int) -> "ExactTeamConstants":
        """Only the adopted features have an integer form (FINDINGS.md §4.7)."""
        if any(weight != 1.0 for weight in constants.stage_weights.values()):
            raise NotImplementedError("match importance weights were not adopted; no integer form")
        if constants.state_floor < 1.0 or constants.card_weight > 0 or not constants.goal_difference:
            raise NotImplementedError("competition state and cards were not adopted; no integer form")
        return ExactTeamConstants(
            process_noise=round(constants.process_noise * VARIANCE_UNIT),
            initial_variance=round(constants.initial_variance * VARIANCE_UNIT),
            home_advantage=round(constants.home_advantage * RATING_UNIT),
            league_seed_offset=round(constants.league_seed_offset * RATING_UNIT),
            unknown_seed_offset=round(constants.unknown_seed_offset * RATING_UNIT),
            corner_scale=round(constants.corner_scale * WEIGHT),
            corner_weight=round(constants.corner_weight * WEIGHT),
            lag_days=lag_days, iterations=iterations,
        )


@dataclass(frozen=True)
class ExactPlayerConstants:
    anchor_rate: int            # thousandths per full match
    debutant_offset: int        # milli-Elo
    bonus_scale: int            # milli-Elo per unit of minutes share
    bonus_window_days: int
    national_gain: int          # milli-Elo per unit of surprise
    inactive_grace_days: int
    inactive_decay_days: int
    replacement_level: int      # milli-Elo

    @staticmethod
    def from_float(constants) -> "ExactPlayerConstants":
        return ExactPlayerConstants(
            anchor_rate=round(constants.anchor_rate * WEIGHT),
            debutant_offset=round(constants.debutant_offset * RATING_UNIT),
            bonus_scale=round(constants.bonus_scale * RATING_UNIT),
            bonus_window_days=constants.bonus_window_days,
            national_gain=round(constants.national_gain * RATING_UNIT),
            inactive_grace_days=constants.inactive_grace_days,
            inactive_decay_days=constants.inactive_decay_days,
            replacement_level=round((te.INITIAL_RATING - constants.replacement_offset) * RATING_UNIT),
        )


def margin_weight(goal_difference: int) -> int:
    """World Football Elo's margin multiplier in thousandths: 1, 1.5, then (11 + N) ÷ 8."""
    margin = abs(goal_difference)
    if margin <= 1:
        return WEIGHT
    if margin == 2:
        return 1500
    return multiply(11 + margin, 125)


def season_of(day: int) -> int:
    """Seasons run from 1 July: the ledger is kept per season by date."""
    date = store.EPOCH + pd.Timedelta(days=day)
    return date.year if date.month >= 7 else date.year - 1


def score_of(goal_difference: int) -> int:
    if goal_difference > 0:
        return PROBABILITY
    if goal_difference < 0:
        return 0
    return PROBABILITY // 2


# ---------------------------------------------------------------------------
# Inputs


class ExactMatch(NamedTuple):
    game_id: int
    day: int
    season: int
    competition_id: str
    stage: str
    home: int
    away: int
    goal_difference: int
    neutral: bool
    home_corners: int | None
    away_corners: int | None


def load_matches(until_day: int | None = None, shuffle_seed: int | None = None) -> list[ExactMatch]:
    games = store.club_games()
    games = games[games.data_issue.fillna("") != "team_plays_twice_same_day"]
    if until_day is not None:
        games = games[games.day < until_day]
    if shuffle_seed is not None:
        games = games.sample(frac=1.0, random_state=shuffle_seed)
    matches = []
    for row in games.itertuples():
        corners = not (pd.isna(row.home_corners) or pd.isna(row.away_corners))
        matches.append(ExactMatch(
            int(row.game_id), int(row.day), int(row.season), row.competition_id, row.stage,
            int(row.home_team_id), int(row.away_team_id), int(row.goal_difference), bool(row.neutral),
            int(row.home_corners) if corners else None, int(row.away_corners) if corners else None,
        ))
    return sorted(matches, key=lambda m: (m.day, m.game_id))


def observations_of(match: ExactMatch, constants: ExactTeamConstants) -> list[tuple[int, int, int]]:
    """(observed share in billionths, scale in thousandths, weight in thousandths)."""
    observations = [(score_of(match.goal_difference), WEIGHT, margin_weight(match.goal_difference))]
    corners_known = match.home_corners is not None and match.home_corners + match.away_corners > 0
    if constants.corner_weight > 0 and corners_known:
        total = match.home_corners + match.away_corners
        share = divide_rounded(multiply(match.home_corners, PROBABILITY), total)
        observations.append((share, constants.corner_scale, constants.corner_weight))
    return observations


# ---------------------------------------------------------------------------
# The Kalman step for one observation


class Step(NamedTuple):
    own_swing: int
    own_variance: int
    opponent_variance: int


def observation_step(observed: int, scale: int, weight: int, difference: int, own_variance: int,
                     opponent_variance: int, own_is_home: bool) -> Step:
    """One observation's update for one side (FINDINGS.md §6.3 writes it as formulas).

    Naturally: gain = variance × slope × weight ÷ (1 + weight × slope² × spread ×
    (variance + opponentVariance)), swing = gain × surprise, and each variance is
    multiplied by (1 + the other side's load) ÷ the same denominator."""
    scaled_difference = divide_rounded(multiply(difference, scale), WEIGHT)
    expected = expected_score(scaled_difference)
    surprise = observed - expected
    slope = divide_rounded(multiply(SLOPE, scale), WEIGHT)
    spread = divide_rounded(multiply(expected, PROBABILITY - expected), PROBABILITY)
    curvature = divide_rounded(multiply(slope, slope, weight), 10 ** 9)
    information = divide_rounded(multiply(curvature, spread), PROBABILITY)
    own_load = divide_rounded(multiply(information, own_variance), 10 ** 6)
    opponent_load = divide_rounded(multiply(information, opponent_variance), 10 ** 6)
    denominator = add(PROBABILITY, own_load, opponent_load)
    pull = divide_rounded(multiply(slope, weight), WEIGHT)
    gain = divide_rounded(multiply(own_variance, pull), denominator)
    direction = 1 if own_is_home else -1
    swing = divide_rounded(multiply(direction, gain, surprise), PROBABILITY)
    own_after = divide_rounded(multiply(own_variance, add(PROBABILITY, opponent_load)), denominator)
    opponent_after = divide_rounded(multiply(opponent_variance, add(PROBABILITY, own_load)), denominator)
    return Step(swing, own_after, opponent_after)


def side_update(match: ExactMatch, own_is_home: bool, mean: int, variance: int, opponent_mean: int,
                opponent_variance: int, constants: ExactTeamConstants) -> tuple[int, int]:
    """A team's whole update in a match: the result, then any tier-2 signal, each
    observation on the variances the previous one left."""
    home_advantage = 0 if match.neutral else constants.home_advantage
    if own_is_home:
        difference = add(mean, home_advantage, -opponent_mean)
    else:
        difference = add(opponent_mean, home_advantage, -mean)
    swing = 0
    for observed, scale, weight in observations_of(match, constants):
        step = observation_step(observed, scale, weight, difference, variance, opponent_variance, own_is_home)
        swing = add(swing, step.own_swing)
        variance, opponent_variance = step.own_variance, step.opponent_variance
    return swing, variance


def precision_of(variance: int) -> int:
    return divide_rounded(PRECISION_NUMERATOR, variance)


# ---------------------------------------------------------------------------
# Forward filter


@dataclass
class TeamState:
    rating: int
    variance: int
    last_day: int


@dataclass
class ForwardSide:
    prior_mean: int
    prior_variance: int
    swing: int
    posterior_variance: int


class Seeder:
    """A new team starts at the mean of the league it enters less an offset, or at the
    pool's mean less a larger one when it first appears outside a covered league.
    Teams first seen in the first season start at 1500."""

    def __init__(self, constants: ExactTeamConstants):
        self.constants = constants
        self.league_members: dict[str, dict[int, int]] = {}

    def note(self, match: ExactMatch) -> None:
        if match.stage == "league":
            members = self.league_members.setdefault(match.competition_id, {})
            members[match.home] = match.day
            members[match.away] = match.day

    def seed(self, match: ExactMatch, states: dict[int, TeamState]) -> int:
        if match.season < 2013:
            return INITIAL_RATING
        if match.stage == "league":
            members = self.league_members.get(match.competition_id, {})
            ratings = [states[t].rating for t, day in members.items() if t in states and match.day - day <= 365]
            if ratings:
                return add(divide_rounded(total_of(ratings), len(ratings)), -self.constants.league_seed_offset)
        active = [s.rating for s in states.values() if match.day - s.last_day <= 365]
        if not active:
            return INITIAL_RATING
        return add(divide_rounded(total_of(active), len(active)), -self.constants.unknown_seed_offset)


def aged(state: TeamState, day: int, constants: ExactTeamConstants) -> int:
    grown = add(state.variance, multiply(constants.process_noise, day - state.last_day))
    return min(grown, constants.initial_variance)


def forward(matches: list[ExactMatch], constants: ExactTeamConstants):
    """Returns, per match, both sides' forward view, and each team's seed."""
    states: dict[int, TeamState] = {}
    seeder = Seeder(constants)
    sides: list[dict[int, ForwardSide]] = []
    seeds: dict[int, int] = {}
    for day in days_of(matches):
        pending = []
        for match in day:
            for team in (match.home, match.away):
                if team not in states:
                    seeds[team] = seeder.seed(match, states)
                    states[team] = TeamState(seeds[team], constants.initial_variance, match.day)
            home, away = states[match.home], states[match.away]
            home_variance, away_variance = aged(home, match.day, constants), aged(away, match.day, constants)
            home_swing, home_after = joint_update(match, home.rating, home_variance, away.rating, away_variance, constants, True)
            away_swing, away_after = joint_update(match, home.rating, home_variance, away.rating, away_variance, constants, False)
            sides.append({
                match.home: ForwardSide(home.rating, home_variance, home_swing, home_after),
                match.away: ForwardSide(away.rating, away_variance, away_swing, away_after),
            })
            pending.append((match, home_swing, home_after, away_swing, away_after))
        for match, home_swing, home_after, away_swing, away_after in pending:
            for team, swing, variance in ((match.home, home_swing, home_after), (match.away, away_swing, away_after)):
                state = states[team]
                state.rating = add(state.rating, swing)
                state.variance = variance
                state.last_day = match.day
            seeder.note(match)
    return sides, seeds


def joint_update(match, home_rating, home_variance, away_rating, away_variance, constants, for_home: bool):
    """The forward filter's update for one side: the same step as the replay, with the
    opponent at its own forward estimate."""
    if for_home:
        return side_update(match, True, home_rating, home_variance, away_rating, away_variance, constants)
    return side_update(match, False, away_rating, away_variance, home_rating, home_variance, constants)


def days_of(matches: list[ExactMatch]) -> list[list[ExactMatch]]:
    grouped, current, current_day = [], [], None
    for match in matches:
        if match.day != current_day and current:
            grouped.append(current)
            current = []
        current_day = match.day
        current.append(match)
    if current:
        grouped.append(current)
    return grouped


# ---------------------------------------------------------------------------
# Hindsight replay


class Message(NamedTuple):
    precision: int
    mean: int


NO_MESSAGE = Message(0, 0)


def message_of(prior_mean: int, prior_variance: int, swing: int, posterior_variance: int) -> Message:
    """The observation that turns the prior into the posterior: its precision is the
    precision gained, its mean sits at prior + swing × (1 + prior precision ÷ gained)."""
    prior_precision = precision_of(prior_variance)
    gained = precision_of(posterior_variance) - prior_precision
    if gained <= 0:
        return NO_MESSAGE
    beyond = divide_rounded(multiply(swing, prior_precision), gained)
    return Message(gained, add(prior_mean, swing, beyond))


@dataclass
class ExactReplayResult:
    as_of_differences: dict = field(default_factory=dict)
    settled_sides: dict = field(default_factory=dict)          # (match index, team) -> (rating before, swing)
    snapshot_states: dict = field(default_factory=dict)        # day -> {team: rating}
    snapshot_window_sides: dict = field(default_factory=dict)  # day -> {(match index, team): (rating before, swing)}


class Replay:
    """Integer mirror of hindsight.HindsightReplay."""

    def __init__(self, matches: list[ExactMatch], forward_sides: list[dict], seeds: dict, constants: ExactTeamConstants):
        self.matches = matches
        self.constants = constants
        self.seeds = seeds
        self.sides_of_team: dict[int, list[int]] = {}
        for index, match in enumerate(matches):
            for team in (match.home, match.away):
                self.sides_of_team.setdefault(team, []).append(index)
        self.forward_prior = {}
        self.forward_message = {}
        for index, sides in enumerate(forward_sides):
            for team, side in sides.items():
                self.forward_prior[(index, team)] = (side.prior_mean, side.prior_variance)
                self.forward_message[(index, team)] = message_of(side.prior_mean, side.prior_variance,
                                                                 side.swing, side.posterior_variance)

    def run(self, snapshot_days=()) -> ExactReplayResult:
        match_days = sorted({m.day for m in self.matches})
        by_day: dict[int, list[int]] = {}
        for index, match in enumerate(self.matches):
            by_day.setdefault(match.day, []).append(index)
        snapshots = set(snapshot_days)
        result = ExactReplayResult()
        settled: dict[int, tuple[int, int, int]] = {}
        settled_until = min(match_days[0], min(snapshots) if snapshots else match_days[0])
        lag = self.constants.lag_days
        last_active = {}
        for as_of in sorted(set(match_days) | snapshots):
            window_start = as_of - lag
            window = [m for d in match_days if settled_until <= d < as_of for m in by_day[d]]
            cavities = self.cavities(window, settled)
            to_settle = [m for m in window if self.matches[m].day < window_start]
            active = [m for m in window if self.matches[m].day >= window_start]
            settled, _, settle_sides = self.replay(to_settle, settled, cavities)
            result.settled_sides.update(settle_sides)
            settled_until = max(settled_until, window_start)
            states, _, active_sides = self.replay(active, settled, cavities)
            last_active = active_sides
            if as_of in snapshots:
                result.snapshot_states[as_of] = {team: state[0] for team, state in states.items()}
                result.snapshot_window_sides[as_of] = active_sides
            for index in by_day.get(as_of, ()):
                match = self.matches[index]
                home = self.rating_of(match.home, states)
                away = self.rating_of(match.away, states)
                home_advantage = 0 if match.neutral else self.constants.home_advantage
                result.as_of_differences[index] = add(home, home_advantage, -away)
        for key, side in last_active.items():
            result.settled_sides.setdefault(key, side)
        return result

    def rating_of(self, team: int, states: dict) -> int:
        if team in states:
            return states[team][0]
        return self.seeds.get(team, INITIAL_RATING)

    def cavities(self, window: list[int], settled: dict) -> dict:
        priors, messages = self.forward_prior, self.forward_message
        cavities = self.backward(window, priors, messages)
        for _ in range(self.constants.iterations - 1):
            _, (priors, messages), _ = self.replay(window, settled, cavities, record_messages=True)
            cavities = self.backward(window, priors, messages)
        return cavities

    def backward(self, window: list[int], priors: dict, messages: dict) -> dict:
        """Each team's later matches folded back to every earlier one (information
        form), combined with the forward estimate before it: the cavity."""
        in_window = set(window)
        teams = {self.matches[m].home for m in window} | {self.matches[m].away for m in window}
        cavities = {}
        for team in sorted(teams):
            indices = [m for m in self.sides_of_team[team] if m in in_window]
            precision, information, later_day = 0, 0, None
            for index in reversed(indices):
                day = self.matches[index].day
                if later_day is not None and precision > 0:
                    mean = divide_rounded(information, precision)
                    spread_out = multiply(self.constants.process_noise, later_day - day)
                    variance = add(divide_rounded(PRECISION_NUMERATOR, precision), spread_out)
                    precision = precision_of(variance)
                    information = multiply(mean, precision)
                prior_mean, prior_variance = priors[(index, team)]
                prior_precision = precision_of(prior_variance)
                cavity_precision = add(prior_precision, precision)
                cavity_information = add(multiply(prior_mean, prior_precision), information)
                cavity_mean = divide_rounded(cavity_information, cavity_precision)
                cavities[(index, team)] = (cavity_mean, divide_rounded(PRECISION_NUMERATOR, cavity_precision))
                message = messages[(index, team)]
                if message.precision > 0:
                    precision = add(precision, message.precision)
                    information = add(information, multiply(message.mean, message.precision))
                later_day = day
        return cavities

    def replay(self, indices: list[int], base: dict, cavities: dict, record_messages: bool = False):
        states = dict(base)
        priors = ChainMap({}, self.forward_prior) if record_messages else None
        messages = ChainMap({}, self.forward_message) if record_messages else None
        sides = {}
        for day in group_by_day(indices, self.matches):
            updates = []
            for index in day:
                match = self.matches[index]
                for team, opponent, is_home in ((match.home, match.away, True), (match.away, match.home, False)):
                    mean, variance = self.state_before(team, match.day, states)
                    opponent_mean, opponent_variance = cavities[(index, opponent)]
                    swing, posterior = side_update(match, is_home, mean, variance, opponent_mean,
                                                   opponent_variance, self.constants)
                    if record_messages:
                        priors[(index, team)] = (mean, variance)
                        messages[(index, team)] = message_of(mean, variance, swing, posterior)
                    sides[(index, team)] = (mean, swing)
                    updates.append((team, swing, posterior, match.day))
            for team, swing, variance, update_day in updates:
                mean = states[team][0] if team in states else self.seeds.get(team, INITIAL_RATING)
                states[team] = (add(mean, swing), variance, update_day)
        return states, (priors, messages), sides

    def state_before(self, team: int, day: int, states: dict) -> tuple[int, int]:
        if team not in states:
            return self.seeds.get(team, INITIAL_RATING), self.constants.initial_variance
        mean, variance, last_day = states[team]
        grown = add(variance, multiply(self.constants.process_noise, day - last_day))
        return mean, min(grown, self.constants.initial_variance)


def group_by_day(indices: list[int], matches: list[ExactMatch]) -> list[list[int]]:
    grouped, current, current_day = [], [], None
    for index in sorted(indices, key=lambda m: (matches[m].day, matches[m].game_id)):
        day = matches[index].day
        if day != current_day and current:
            grouped.append(current)
            current = []
        current_day = day
        current.append(index)
    if current:
        grouped.append(current)
    return grouped


# ---------------------------------------------------------------------------
# Players


@dataclass
class PlayerState:
    rating: int
    last_day: int
    team: int


class MinutesWindow:
    """Each player's share of his team's matches over the trailing window, in
    three-hundred-sixtieths of a full match."""

    def __init__(self, window_days: int):
        self.window_days = window_days
        self.matches: dict[int, list[tuple[int, dict[int, int]]]] = {}
        self.share_sum: dict[tuple[int, int], int] = {}
        self.squad: dict[int, set] = {}

    def copy(self) -> "MinutesWindow":
        window = MinutesWindow(self.window_days)
        window.matches = {team: list(entries) for team, entries in self.matches.items()}
        window.share_sum = dict(self.share_sum)
        window.squad = {team: set(members) for team, members in self.squad.items()}
        return window

    def add(self, team: int, day: int, shares: dict[int, int]) -> None:
        self.expire(team, day)
        self.matches.setdefault(team, []).append((day, shares))
        squad = self.squad.setdefault(team, set())
        for player, share in shares.items():
            key = (team, player)
            self.share_sum[key] = self.share_sum.get(key, 0) + share
            squad.add(player)

    def expire(self, team: int, day: int) -> None:
        entries = self.matches.get(team)
        while entries and day - entries[0][0] > self.window_days:
            _, shares = entries.pop(0)
            for player, share in shares.items():
                key = (team, player)
                remaining = self.share_sum[key] - share
                if remaining == 0:
                    del self.share_sum[key]
                    self.squad[team].discard(player)
                else:
                    self.share_sum[key] = remaining

    def bonuses(self, team: int, day: int, states: dict, scale: int) -> dict[int, int]:
        """scale × (share − squad mean share) for every current squad member, shared by
        largest remainder so the squad's bonuses sum to exactly zero."""
        self.expire(team, day)
        count = len(self.matches.get(team, ()))
        members = sorted(p for p in self.squad.get(team, ()) if p in states and states[p].team == team)
        if count == 0 or not members or scale == 0:
            return {}
        total = sum(self.share_sum[(team, p)] for p in members)
        size = len(members)
        denominator = multiply(FULL_MATCH, count, size)
        numerators = {p: multiply(scale, add(multiply(size, self.share_sum[(team, p)]), -total)) for p in members}
        return apportion(0, numerators, denominator)


class Ledger:
    def __init__(self):
        self.rows: dict[tuple[int, str], int] = {}
        self.rounding: dict[int, Fraction] = {}

    def copy(self) -> "Ledger":
        ledger = Ledger()
        ledger.rows = dict(self.rows)
        ledger.rounding = dict(self.rounding)
        return ledger

    def add(self, season: int, source: str, amount: int) -> None:
        key = (season, source)
        self.rows[key] = self.rows.get(key, 0) + amount


class PlayerModel:

    def __init__(self, constants: ExactPlayerConstants, team_constants: ExactTeamConstants):
        self.constants = constants
        self.team_constants = team_constants
        self.states: dict[int, PlayerState] = {}
        self.minutes = MinutesWindow(constants.bonus_window_days)
        self.ledger = Ledger()

    def copy(self) -> "PlayerModel":
        model = PlayerModel(self.constants, self.team_constants)
        model.states = {p: PlayerState(s.rating, s.last_day, s.team) for p, s in self.states.items()}
        model.minutes = self.minutes.copy()
        model.ledger = self.ledger.copy()
        return model

    def decayed(self, state: PlayerState, day: int) -> int:
        idle = day - state.last_day - self.constants.inactive_grace_days
        if idle <= 0:
            return state.rating
        remaining = max(0, self.constants.inactive_decay_days - idle)
        gap = add(state.rating, -self.constants.replacement_level)
        kept = divide_rounded(multiply(gap, remaining), self.constants.inactive_decay_days)
        return add(self.constants.replacement_level, kept)

    def published(self, player: int, day: int, bonus_cache: dict | None = None) -> int | None:
        state = self.states.get(player)
        if state is None:
            return None
        rating = self.decayed(state, day)
        if self.constants.bonus_scale == 0:
            return rating
        cache = bonus_cache if bonus_cache is not None else {}
        if state.team not in cache:
            cache[state.team] = self.minutes.bonuses(state.team, day, self.states, self.constants.bonus_scale)
        return add(rating, cache[state.team].get(player, 0))

    def club_match(self, match: ExactMatch, sides: dict, players: dict, length: int, forward_swings: dict) -> None:
        for team in (match.home, match.away):
            rating_before, swing = sides[team]
            lineup = sorted(players.get(team, ()))
            shares = {p: multiply(min(minutes, length), FULL_MATCH // length) for p, minutes in lineup}
            self.attribute(match, team, rating_before, swing, shares, forward_swings[team])
            self.minutes.add(team, match.day, shares)

    def attribute(self, match: ExactMatch, team: int, rating_before: int, swing: int, shares: dict[int, int],
                  forward_swing: int) -> None:
        """The team swing shared by minutes (rounded once, shared by largest remainder),
        then each player's pull towards the team's rating."""
        if not shares:
            return
        for player in shares:
            self.seed_or_settle(player, team, match, rating_before)
        share_total = total_of(shares.values())
        exact_total = Fraction(multiply(share_total, swing), FULL_MATCH)
        whole = divide_rounded(multiply(share_total, swing), FULL_MATCH)
        parts = apportion(whole, {p: multiply(s, swing) for p, s in shares.items()}, FULL_MATCH)
        forward_whole = divide_rounded(multiply(share_total, forward_swing), FULL_MATCH)
        season = season_of(match.day)
        self.ledger.add(season, "team swings, forward filter", forward_whole)
        self.ledger.add(season, "hindsight replay", whole - forward_whole)
        self.ledger.rounding[season] = self.ledger.rounding.get(season, Fraction(0)) + exact_total - whole
        for player, share in shares.items():
            state = self.states[player]
            gap = add(rating_before, -state.rating)
            anchored = divide_rounded(multiply(share, self.constants.anchor_rate, gap), multiply(FULL_MATCH, WEIGHT))
            state.rating = add(state.rating, parts[player], anchored)
            state.last_day = match.day
            state.team = team
            self.ledger.add(season, "anchoring to team level", anchored)

    def seed_or_settle(self, player: int, team: int, match: ExactMatch, rating_before: int) -> None:
        state = self.states.get(player)
        if state is None:
            seed = add(rating_before, -self.constants.debutant_offset)
            self.states[player] = PlayerState(seed, match.day, team)
            self.ledger.add(season_of(match.day), "debutant seeding", seed)
            return
        decayed = self.decayed(state, match.day)
        if decayed != state.rating:
            self.ledger.add(season_of(match.day), "inactivity decay", decayed - state.rating)
            state.rating = decayed

    def national_match(self, game, lineups: dict, length: int) -> None:
        strengths = {}
        for team in (game.home_team_id, game.away_team_id):
            rated = [(self.published(p, game.day), m) for p, m in lineups.get(team, ())]
            total = sum(m for _, m in rated)
            known = [(r, m) for r, m in rated if r is not None]
            known_minutes = sum(m for _, m in known)
            if total == 0 or multiply(10, known_minutes) < multiply(6, total):
                return
            strengths[team] = divide_rounded(total_of(multiply(r, m) for r, m in known), known_minutes)
        home_advantage = 0 if game.neutral else self.team_constants.home_advantage
        difference = add(strengths[game.home_team_id], home_advantage, -strengths[game.away_team_id])
        surprise = score_of(int(game.goal_difference)) - expected_score(difference)
        step = divide_rounded(multiply(self.constants.national_gain, margin_weight(int(game.goal_difference)), surprise),
                              multiply(WEIGHT, PROBABILITY))
        for team, direction in ((game.home_team_id, 1), (game.away_team_id, -1)):
            for player, minutes in sorted(lineups.get(team, ())):
                state = self.states.get(player)
                if state is None:
                    continue
                share = multiply(min(minutes, length), FULL_MATCH // length)
                change = divide_rounded(multiply(direction, step, share), FULL_MATCH)
                state.rating = add(state.rating, change)
                self.ledger.add(season_of(int(game.day)), "national-team calibration", change)


class PlayerRunner:

    def __init__(self, matches, inputs, model: PlayerModel, forward_sides: list[dict]):
        self.matches = matches
        self.inputs = inputs
        self.model = model
        self.forward_sides = forward_sides
        self.national = sorted(inputs.national_games.itertuples(), key=lambda g: (g.day, g.game_id))
        self.match_position = 0
        self.national_position = 0

    def fork(self) -> "PlayerRunner":
        copy = PlayerRunner.__new__(PlayerRunner)
        copy.__dict__.update(self.__dict__)
        copy.model = self.model.copy()
        return copy

    def advance_to(self, day: int, sides_of) -> None:
        while self.match_position < len(self.matches) and self.matches[self.match_position].day < day:
            index = self.match_position
            match = self.matches[index]
            self.national_until(match.day)
            players = self.inputs.appearances.get(match.game_id)
            if players:
                forward_swings = {team: side.swing for team, side in self.forward_sides[index].items()}
                self.model.club_match(match, sides_of(index), players, self.inputs.lengths.get(match.game_id, 90),
                                      forward_swings)
            self.match_position += 1
        self.national_until(day)

    def national_until(self, day: int) -> None:
        while self.national_position < len(self.national) and self.national[self.national_position].day < day:
            game = self.national[self.national_position]
            self.national_position += 1
            if game.game_id in self.inputs.appearances:
                self.model.national_match(game, self.inputs.appearances[game.game_id],
                                          self.inputs.lengths.get(game.game_id, 90))


# ---------------------------------------------------------------------------
# The whole computation


@dataclass
class ExactRun:
    team_constants: ExactTeamConstants
    player_constants: ExactPlayerConstants
    as_of_differences: dict
    team_snapshots: dict
    player_snapshots: pd.DataFrame
    pool: pd.DataFrame
    ledger: dict
    rounding: dict
    stored_pool_by_season_end: dict
    published_pool_by_season_end: dict
    match_game_ids: list


def run(team_constants: ExactTeamConstants, player_constants: ExactPlayerConstants, inputs, snapshot_days: list[int],
        tracked: set[int], until_day: int | None = None, shuffle_seed: int | None = None, log=print) -> ExactRun:
    matches = load_matches(until_day, shuffle_seed)
    if shuffle_seed is not None:
        inputs = shuffled_inputs(inputs, shuffle_seed)
    forward_sides, seeds = forward(matches, team_constants)
    log("forward filter done")
    replay = Replay(matches, forward_sides, seeds, team_constants).run(snapshot_days)
    log("replay done")
    season_ends = sorted({int((pd.Timestamp(f"{s + 1}-07-01") - store.EPOCH).days) for s in range(2012, 2026)})
    all_days = sorted(set(snapshot_days) | set(season_ends))
    settled = PlayerRunner(matches, inputs, PlayerModel(player_constants, team_constants), forward_sides)
    lag = team_constants.lag_days

    def settled_sides(index):
        match = matches[index]
        return {team: replay.settled_sides[(index, team)] for team in (match.home, match.away)}

    rows, pool, stored_pool, published_pool = [], [], {}, {}
    for day in all_days:
        if day in season_ends:
            final = settled.fork()
            final.advance_to(day, settled_sides)
            stored_pool[day] = sum(s.rating for s in final.model.states.values())
            cache: dict = {}
            published_pool[day] = sum(final.model.published(p, day, cache) for p in final.model.states)
        if day not in snapshot_days:
            continue
        settled.advance_to(day - lag, settled_sides)
        current = settled.fork()
        window = replay.snapshot_window_sides.get(day, {})

        def window_sides(index, window=window):
            match = matches[index]
            return {team: window.get((index, team)) or replay.settled_sides[(index, team)]
                    for team in (match.home, match.away)}

        current.advance_to(day, window_sides)
        cache = {}
        for player in tracked:
            rating = current.model.published(player, day, cache)
            if rating is not None:
                rows.append((day, player, rating))
        if (store.EPOCH + pd.Timedelta(days=day)).strftime("%m-%d") == "06-01":
            for player, state in current.model.states.items():
                if day - state.last_day <= 365:
                    pool.append((day, player, current.model.published(player, day, cache), state.team))
    settled.advance_to(max(all_days) + 1, settled_sides)
    log("players done")
    return ExactRun(
        team_constants, player_constants, replay.as_of_differences, replay.snapshot_states,
        pd.DataFrame(rows, columns=["day", "player_id", "rating"]),
        pd.DataFrame(pool, columns=["day", "player_id", "rating", "team_id"]),
        settled.model.ledger.rows, settled.model.ledger.rounding, stored_pool, published_pool,
        [m.game_id for m in matches],
    )


def shuffled_inputs(inputs, seed: int):
    """The same player inputs with every list in a random order."""
    import random
    rng = random.Random(seed)
    appearances = {}
    for game_id in rng.sample(list(inputs.appearances), len(inputs.appearances)):
        teams = {}
        for team in rng.sample(list(inputs.appearances[game_id]), len(inputs.appearances[game_id])):
            entries = list(inputs.appearances[game_id][team])
            rng.shuffle(entries)
            teams[team] = entries
        appearances[game_id] = teams
    national = inputs.national_games.sample(frac=1.0, random_state=seed)
    return type(inputs)(appearances, inputs.starters, inputs.lengths, national)
