"""Team Elo, float reference used for exploring and fitting (FINDINGS.md §4).

Two variants share one code path:

- **Fixed-K Elo** (the plain baseline): every match moves both teams by
  K × weight × (score − expectedScore).
- **Elo with uncertainty**: each team carries a variance, the Elo update becomes
  an extended Kalman filter step (Glicko's idea, in the form of Szczecinski and
  Tihon's simplified Kalman filter), and the variance grows with the days a team
  does not play. New and long-idle teams move fast; established teams settle to
  an Elo-like step.

Ratings are in Elo points (400 points = a factor of 10 in odds); variances in
Elo points squared.
"""

import math
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import store

LOGISTIC_SLOPE = math.log(10) / 400

INITIAL_RATING = 1500.0

STAGES = [
    "league", "cup_early", "cup_late", "super_cup", "continental_qualifying",
    "continental_group", "continental_knockout", "continental_final", "club_world_cup",
]

FIT_SEASONS = range(2014, 2019)
TEST_SEASONS = range(2019, 2026)
MIN_PRIOR_MATCHES = 20


@dataclass(frozen=True)
class TeamConstants:
    uncertainty: bool = True
    k_factor: float = 20.0
    process_noise: float = 2.0
    initial_variance: float = 200.0 ** 2
    home_advantage: float = 65.0
    goal_difference: bool = True
    stage_weights: dict = field(default_factory=lambda: {stage: 1.0 for stage in STAGES})
    state_floor: float = 1.0
    goal_value: float = 300.0
    league_seed_offset: float = 100.0
    unknown_seed_offset: float = 250.0
    corner_weight: float = 0.0
    corner_scale: float = 0.5
    card_weight: float = 0.0
    card_scale: float = -0.2

    def with_(self, **changes) -> "TeamConstants":
        return replace(self, **changes)


def expected_score(rating_difference: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-rating_difference / 400.0))


def goal_difference_multiplier(goal_difference: int) -> float:
    """World Football Elo's margin multiplier: 1, 1.5, then (11 + margin) / 8."""
    margin = abs(goal_difference)
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def score_of(goal_difference: int) -> float:
    if goal_difference > 0:
        return 1.0
    if goal_difference < 0:
        return 0.0
    return 0.5


@dataclass
class Match:
    """One club match as the model consumes it."""
    game_id: int
    day: int
    season: int
    competition_id: str
    stage: str
    home: int
    away: int
    goal_difference: int
    neutral: bool
    first_leg_difference: int | None
    corner_share: float | None
    card_share: float | None


def load_matches() -> list[Match]:
    """A team cannot play twice on one day; the four games where the data says so are
    data errors and are left out (FINDINGS.md §3)."""
    games = store.club_games()
    by_id = dict(zip(games.game_id, games.goal_difference))
    games = games[games.data_issue.fillna("") != "team_plays_twice_same_day"]
    matches = []
    for row in games.itertuples():
        first_leg = None
        if row.leg == 2 and not pd.isna(row.first_leg_game_id):
            first_leg = int(by_id[int(row.first_leg_game_id)])
        matches.append(Match(
            game_id=int(row.game_id), day=int(row.day), season=int(row.season),
            competition_id=row.competition_id, stage=row.stage,
            home=int(row.home_team_id), away=int(row.away_team_id),
            goal_difference=int(row.goal_difference), neutral=bool(row.neutral),
            first_leg_difference=first_leg,
            corner_share=share(row.home_corners, row.away_corners),
            card_share=share(cards(row.away_yellow, row.away_red), cards(row.home_yellow, row.home_red)),
        ))
    return matches


def cards(yellow, red):
    if pd.isna(yellow) or pd.isna(red):
        return None
    return yellow + 2 * red


def share(mine, theirs):
    if mine is None or theirs is None or pd.isna(mine) or pd.isna(theirs) or mine + theirs == 0:
        return None
    return float(mine) / float(mine + theirs)


def days_of(matches: list[Match]) -> list[list[Match]]:
    """Matches grouped by day. A day is one batch: every match in it is computed
    from the ratings at the start of the day."""
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


@dataclass
class TeamState:
    rating: float
    variance: float
    last_day: int
    matches: int


@dataclass
class Prediction:
    """What a match looked like before kick-off, and how the ratings moved."""
    match: Match
    rating_difference: float
    home_rating: float
    away_rating: float
    home_variance: float
    away_variance: float
    home_prior_matches: int
    away_prior_matches: int
    home_swing: float = 0.0
    away_swing: float = 0.0
    home_posterior_variance: float = 0.0
    away_posterior_variance: float = 0.0
    home_seed: float | None = None
    away_seed: float | None = None


class Seeder:
    """A team seen for the first time starts below the current mean of the league it
    enters (promoted teams are weaker than the league they join), or further below
    the whole pool's mean when it first appears outside a covered league."""

    def __init__(self, constants: TeamConstants):
        self.constants = constants
        self.league_members: dict[str, dict[int, int]] = {}

    def note(self, match: Match) -> None:
        if match.stage == "league":
            members = self.league_members.setdefault(match.competition_id, {})
            members[match.home] = match.day
            members[match.away] = match.day

    def seed(self, match: Match, states: dict[int, TeamState]) -> float:
        if match.stage == "league":
            members = self.league_members.get(match.competition_id, {})
            ratings = [states[t].rating for t, day in members.items() if t in states and match.day - day <= 365]
            if ratings:
                return sum(ratings) / len(ratings) - self.constants.league_seed_offset
        everyone = [state.rating for state in states.values() if match.day - state.last_day <= 365]
        if not everyone:
            return INITIAL_RATING
        return sum(everyone) / len(everyone) - self.constants.unknown_seed_offset


def run(matches: list[Match], constants: TeamConstants, burn_in_seed: bool = True) -> tuple[list[Prediction], dict[int, TeamState]]:
    """Forward filter over every match, in processing order."""
    states: dict[int, TeamState] = {}
    seeder = Seeder(constants)
    predictions = []
    for day in days_of(matches):
        pending = []
        for match in day:
            seeds = {}
            for team in (match.home, match.away):
                if team not in states:
                    rating = INITIAL_RATING if match.season < 2013 and burn_in_seed else seeder.seed(match, states)
                    states[team] = TeamState(rating, constants.initial_variance, match.day, 0)
                    seeds[team] = rating
            prediction = predict(match, states, constants)
            home_swing, away_swing, home_variance, away_variance = update(prediction, constants)
            prediction.home_swing, prediction.away_swing = home_swing, away_swing
            prediction.home_posterior_variance, prediction.away_posterior_variance = home_variance, away_variance
            prediction.home_seed, prediction.away_seed = seeds.get(match.home), seeds.get(match.away)
            pending.append((prediction, home_variance, away_variance))
            predictions.append(prediction)
        for prediction, home_variance, away_variance in pending:
            apply(prediction, home_variance, away_variance, states)
            seeder.note(prediction.match)
    return predictions, states


def predict(match: Match, states: dict[int, TeamState], constants: TeamConstants) -> Prediction:
    home, away = states[match.home], states[match.away]
    home_variance = aged_variance(home, match.day, constants)
    away_variance = aged_variance(away, match.day, constants)
    home_advantage = 0.0 if match.neutral else constants.home_advantage
    rating_difference = home.rating + home_advantage - away.rating
    return Prediction(match, rating_difference, home.rating, away.rating, home_variance, away_variance,
                      home.matches, away.matches)


def aged_variance(state: TeamState, day: int, constants: TeamConstants) -> float:
    idle_days = day - state.last_day
    grown = state.variance + constants.process_noise * idle_days
    return min(grown, constants.initial_variance)


def match_weight(match: Match, rating_difference: float, constants: TeamConstants) -> float:
    importance = constants.stage_weights[match.stage]
    state = competition_state(match, rating_difference, constants)
    margin = goal_difference_multiplier(match.goal_difference) if constants.goal_difference else 1.0
    return importance * state * margin


def competition_state(match: Match, rating_difference: float, constants: TeamConstants) -> float:
    """How much a second leg still matters. The first-leg margin is a head start worth
    goal_value Elo points per goal; the chance that the home side goes through is the
    expected score with that head start, and 4 × chance × (1 − chance) is 1 for an
    open tie and near 0 for a decided one."""
    if match.first_leg_difference is None or constants.state_floor >= 1.0:
        return 1.0
    head_start = -match.first_leg_difference * constants.goal_value
    progress_chance = expected_score(rating_difference + head_start)
    stakes = 4.0 * progress_chance * (1.0 - progress_chance)
    return constants.state_floor + (1.0 - constants.state_floor) * stakes


def observations_of(match: Match, rating_difference: float, constants: TeamConstants) -> list[tuple]:
    """(observed share, scale, information weight). The result is a share of 1, 0.5
    or 0. A tier-2 signal is another share (corners won, or the opponent's share of
    the cards) whose expected value is the expected score at a scaled difference."""
    weight = match_weight(match, rating_difference, constants)
    observations = [(score_of(match.goal_difference), 1.0, weight)]
    if constants.corner_weight > 0 and match.corner_share is not None:
        observations.append((match.corner_share, constants.corner_scale, constants.corner_weight))
    if constants.card_weight > 0 and match.card_share is not None:
        observations.append((match.card_share, constants.card_scale, constants.card_weight))
    return observations


def update(prediction: Prediction, constants: TeamConstants) -> tuple[float, float, float, float]:
    difference = prediction.rating_difference
    home_swing = away_swing = 0.0
    home_variance, away_variance = prediction.home_variance, prediction.away_variance
    for observed, scale, information in observations_of(prediction.match, difference, constants):
        expected = expected_score(scale * difference)
        surprise = observed - expected
        if not constants.uncertainty:
            step = constants.k_factor * information * surprise * math.copysign(1.0, scale)
            home_swing += step
            away_swing -= step
            continue
        slope = LOGISTIC_SLOPE * scale
        spread = expected * (1.0 - expected)
        total_variance = home_variance + away_variance
        denominator = 1.0 + information * slope * slope * spread * total_variance
        home_gain = home_variance * slope * information / denominator
        away_gain = away_variance * slope * information / denominator
        home_swing += home_gain * surprise
        away_swing -= away_gain * surprise
        home_variance -= home_gain * slope * spread * home_variance
        away_variance -= away_gain * slope * spread * away_variance
    return home_swing, away_swing, home_variance, away_variance


def apply(prediction: Prediction, home_variance: float, away_variance: float, states: dict[int, TeamState]) -> None:
    match = prediction.match
    for team, swing, variance in ((match.home, prediction.home_swing, home_variance),
                                  (match.away, prediction.away_swing, away_variance)):
        state = states[team]
        state.rating += swing
        state.variance = variance
        state.last_day = match.day
        state.matches += 1


# ---------------------------------------------------------------------------
# Scoring


def outcome_of(goal_difference: int) -> int:
    """0 away win, 1 draw, 2 home win."""
    return 2 if goal_difference > 0 else (0 if goal_difference < 0 else 1)


def scored_frame(predictions: list[Prediction]) -> pd.DataFrame:
    frame = pd.DataFrame({
        "game_id": [p.match.game_id for p in predictions],
        "season": [p.match.season for p in predictions],
        "difference": [p.rating_difference for p in predictions],
        "outcome": [outcome_of(p.match.goal_difference) for p in predictions],
        "warm": [min(p.home_prior_matches, p.away_prior_matches) >= MIN_PRIOR_MATCHES for p in predictions],
    })
    return frame[frame.warm]


@dataclass(frozen=True)
class OrderedLogit:
    """P(outcome ≤ k) = σ(cutpoint_k − slope × difference)."""
    away_cut: float
    draw_cut: float
    slope: float

    def probabilities(self, difference: np.ndarray) -> np.ndarray:
        not_home_win = sigmoid(self.draw_cut - self.slope * difference)
        away_win = sigmoid(self.away_cut - self.slope * difference)
        return np.column_stack([away_win, not_home_win - away_win, 1.0 - not_home_win])


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def fit_ordered_logit(difference: np.ndarray, outcome: np.ndarray) -> OrderedLogit:
    """Maximum likelihood by Newton's method; the problem is convex."""
    params = np.array([-0.5, 0.5, 0.005])
    for _ in range(50):
        gradient, hessian = numeric_derivatives(params, difference, outcome)
        step = np.linalg.solve(hessian, gradient)
        params = params - step
        if np.max(np.abs(step)) < 1e-10:
            break
    return OrderedLogit(*params)


def mean_log_loss(params, difference, outcome) -> float:
    model = OrderedLogit(*params)
    probabilities = model.probabilities(difference)
    chosen = probabilities[np.arange(len(outcome)), outcome]
    return -np.mean(np.log(np.clip(chosen, 1e-12, 1.0)))


def numeric_derivatives(params, difference, outcome):
    epsilon = np.array([1e-4, 1e-4, 1e-7])
    size = len(params)
    gradient = np.zeros(size)
    hessian = np.zeros((size, size))
    base = mean_log_loss(params, difference, outcome)
    for i in range(size):
        step_i = np.eye(size)[i] * epsilon[i]
        plus = mean_log_loss(params + step_i, difference, outcome)
        minus = mean_log_loss(params - step_i, difference, outcome)
        gradient[i] = (plus - minus) / (2 * epsilon[i])
        hessian[i, i] = (plus - 2 * base + minus) / (epsilon[i] ** 2)
        for j in range(i + 1, size):
            step_j = np.eye(size)[j] * epsilon[j]
            pp = mean_log_loss(params + step_i + step_j, difference, outcome)
            pm = mean_log_loss(params + step_i - step_j, difference, outcome)
            mp = mean_log_loss(params - step_i + step_j, difference, outcome)
            mm = mean_log_loss(params - step_i - step_j, difference, outcome)
            hessian[i, j] = hessian[j, i] = (pp - pm - mp + mm) / (4 * epsilon[i] * epsilon[j])
    return gradient, hessian


def match_losses(probabilities: np.ndarray, outcome: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    chosen = probabilities[np.arange(len(outcome)), outcome]
    log_loss = -np.log(np.clip(chosen, 1e-12, 1.0))
    actual = np.zeros_like(probabilities)
    actual[np.arange(len(outcome)), outcome] = 1.0
    brier = np.sum((probabilities - actual) ** 2, axis=1)
    return log_loss, brier


@dataclass
class Score:
    fit_log_loss: float
    test_log_loss: float
    test_brier: float
    logit: OrderedLogit
    test_losses: pd.Series

    def row(self, name: str) -> dict:
        return {"model": name, "fit log loss": round(self.fit_log_loss, 4),
                "test log loss": round(self.test_log_loss, 4), "test Brier": round(self.test_brier, 4)}


def score(frame: pd.DataFrame, only_game_ids=None) -> Score:
    if only_game_ids is not None:
        frame = frame[frame.game_id.isin(only_game_ids)]
    fit = frame[frame.season.isin(FIT_SEASONS)]
    test = frame[frame.season.isin(TEST_SEASONS)]
    logit = fit_ordered_logit(fit.difference.to_numpy(), fit.outcome.to_numpy())
    fit_loss, _ = match_losses(logit.probabilities(fit.difference.to_numpy()), fit.outcome.to_numpy())
    test_loss, test_brier = match_losses(logit.probabilities(test.difference.to_numpy()), test.outcome.to_numpy())
    return Score(float(fit_loss.mean()), float(test_loss.mean()), float(test_brier.mean()), logit,
                 pd.Series(test_loss, index=test.game_id.to_numpy()))


def fit_log_loss(matches: list[Match], constants: TeamConstants) -> float:
    predictions, _ = run(matches, constants)
    frame = scored_frame(predictions)
    fit = frame[frame.season.isin(FIT_SEASONS)]
    logit = fit_ordered_logit(fit.difference.to_numpy(), fit.outcome.to_numpy())
    return mean_log_loss([logit.away_cut, logit.draw_cut, logit.slope], fit.difference.to_numpy(), fit.outcome.to_numpy())


def paired_difference(a: pd.Series, b: pd.Series, resamples: int = 1000, seed: int = 7) -> tuple[float, float, float]:
    """Mean of a − b over common matches, with a 95% bootstrap interval."""
    common = a.index.intersection(b.index)
    diff = (a.loc[common] - b.loc[common]).to_numpy()
    rng = np.random.default_rng(seed)
    means = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(resamples)]
    low, high = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), float(low), float(high)


def coordinate_search(matches: list[Match], constants: TeamConstants, grids: dict, rounds: int = 2,
                      log=print) -> tuple[TeamConstants, float]:
    """Minimises the fit-season log loss one constant at a time over a grid."""
    best = fit_log_loss(matches, constants)
    for _ in range(rounds):
        improved = False
        for name, values in grids.items():
            for value in values:
                candidate = with_value(constants, name, value)
                if candidate == constants:
                    continue
                loss = fit_log_loss(matches, candidate)
                if loss < best - 1e-6:
                    best, constants, improved = loss, candidate, True
                    log(f"  {name} = {value}: fit log loss {loss:.5f}")
        if not improved:
            break
    return constants, best


def with_value(constants: TeamConstants, name: str, value) -> TeamConstants:
    if name.startswith("stage:"):
        weights = dict(constants.stage_weights)
        weights[name.split(":", 1)[1]] = value
        return constants.with_(stage_weights=weights)
    return constants.with_(**{name: value})
