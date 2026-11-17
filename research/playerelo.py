"""Player ratings derived from team swings, float reference (FINDINGS.md §5).

Per club match, every player who appeared for a team moves by

    attributed = minutesShare × teamSwing
    anchored   = minutesShare × anchorRate × (teamRatingBefore − playerRating)

where minutesShare = minutes ÷ match length (90, or 120 after extra time).

- The first term is the Spec's attribution: the team's Elo swing, split by
  fractional minutes. Nothing comes from opposition players.
- The second term pulls a player towards the rating of the team he is selected
  for, at a rate set by the minutes he plays there. One mechanism gives three
  required behaviours: a transferred player converges to his new team's level;
  the gap opened by matches he missed (the team-without-him information) fades
  as he keeps playing; and a player who never misses a game ends up tracking his
  team's rating.

Published rating = playerRating + minutesBonus, where the bonus moves rating
from the bench to the starters inside one squad and sums to zero there.

National-team matches feed back as a calibration signal: the line-up's club-derived
ratings predict the result, and the surprise is attributed by minutes, plus to one
side and minus to the other.

Inactivity: a player with no covered appearance for longer than a grace period
decays towards the replacement level (§5.6 explains why this one needs a rule).
"""

import math
from collections import deque
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

import store
import teamelo as te


@dataclass(frozen=True)
class PlayerConstants:
    anchor_rate: float = 0.05
    debutant_offset: float = 50.0
    bonus_scale: float = 0.0
    bonus_window_days: int = 365
    national_gain: float = 20.0
    inactive_grace_days: int = 120
    inactive_decay_days: int = 365
    replacement_offset: float = 250.0
    lineup_weight: float = 1.0

    def with_(self, **changes) -> "PlayerConstants":
        return replace(self, **changes)


@dataclass
class PlayerState:
    rating: float
    last_day: int
    team: int


@dataclass
class TeamSide:
    """What the player model needs from the team model for one team in one match."""
    rating_before: float
    swing: float


class MinutesWindow:
    """Each player's share of his team's minutes over the trailing window, kept as
    running sums so that the bonus is cheap to read before any match."""

    def __init__(self, window_days: int):
        self.window_days = window_days
        self.matches: dict[int, deque] = {}
        self.share_sum: dict[tuple[int, int], float] = {}
        self.squad: dict[int, set] = {}

    def add(self, team: int, day: int, shares: dict[int, float]) -> None:
        self.expire(team, day)
        self.matches.setdefault(team, deque()).append((day, shares))
        squad = self.squad.setdefault(team, set())
        for player, share in shares.items():
            key = (team, player)
            self.share_sum[key] = self.share_sum.get(key, 0.0) + share
            squad.add(player)

    def expire(self, team: int, day: int) -> None:
        window = self.matches.get(team)
        while window and day - window[0][0] > self.window_days:
            _, shares = window.popleft()
            for player, share in shares.items():
                key = (team, player)
                remaining = self.share_sum[key] - share
                if remaining <= 1e-9:
                    del self.share_sum[key]
                    self.squad[team].discard(player)
                else:
                    self.share_sum[key] = remaining

    def bonus_shares(self, team: int, day: int, states: dict) -> dict[int, float]:
        """Minutes share minus the squad's mean share, for every current squad member."""
        self.expire(team, day)
        count = len(self.matches.get(team, ()))
        if count == 0:
            return {}
        members = [p for p in self.squad.get(team, ()) if p in states and states[p].team == team]
        if not members:
            return {}
        shares = {p: self.share_sum[(team, p)] / count for p in members}
        mean = sum(shares.values()) / len(shares)
        return {p: share - mean for p, share in shares.items()}


@dataclass
class Ledger:
    """Where the player pool's total came from, per season (§5.7)."""
    rows: dict

    def add(self, season: int, source: str, amount: float) -> None:
        key = (season, source)
        self.rows[key] = self.rows.get(key, 0.0) + amount


class PlayerModel:

    def __init__(self, constants: PlayerConstants, team_constants: te.TeamConstants):
        self.constants = constants
        self.team_constants = team_constants
        self.states: dict[int, PlayerState] = {}
        self.minutes = MinutesWindow(constants.bonus_window_days)
        self.ledger = Ledger({})
        self.replacement_level = te.INITIAL_RATING - constants.replacement_offset

    def published(self, player: int, day: int, bonus_cache: dict | None = None) -> float | None:
        state = self.states.get(player)
        if state is None:
            return None
        rating = self.decayed(state, day)
        bonus = 0.0
        if self.constants.bonus_scale:
            shares = bonus_cache.get(state.team) if bonus_cache is not None else None
            if shares is None:
                shares = self.minutes.bonus_shares(state.team, day, self.states)
                if bonus_cache is not None:
                    bonus_cache[state.team] = shares
            bonus = self.constants.bonus_scale * shares.get(player, 0.0)
        return rating + bonus

    def decayed(self, state: PlayerState, day: int) -> float:
        """After the grace period the gap to the replacement level closes in a straight
        line over inactive_decay_days (a line, not an exponential, so that the integer
        form is exact)."""
        idle = day - state.last_day - self.constants.inactive_grace_days
        if idle <= 0:
            return state.rating
        remaining = max(0, self.constants.inactive_decay_days - idle) / self.constants.inactive_decay_days
        return self.replacement_level + (state.rating - self.replacement_level) * remaining

    def settle_decay(self, state: PlayerState, day: int, season: int) -> None:
        rating = self.decayed(state, day)
        if rating != state.rating:
            self.ledger.add(season, "inactivity decay", rating - state.rating)
            state.rating = rating

    def club_match(self, match: te.Match, sides: dict[int, TeamSide], players: dict[int, list[tuple[int, int]]],
                   length: int) -> None:
        for team in (match.home, match.away):
            side = sides[team]
            shares = {}
            for player, minutes in players.get(team, ()):
                share = min(minutes, length) / length
                shares[player] = share
                self.play(player, team, match, side, share)
            self.minutes.add(team, match.day, shares)

    def play(self, player: int, team: int, match: te.Match, side: TeamSide, share: float) -> None:
        state = self.states.get(player)
        if state is None:
            seed = side.rating_before - self.constants.debutant_offset
            state = PlayerState(seed, match.day, team)
            self.states[player] = state
            self.ledger.add(match.season, "debutant seeding", seed)
        else:
            self.settle_decay(state, match.day, match.season)
        attributed = share * side.swing
        anchored = share * self.constants.anchor_rate * (side.rating_before - state.rating)
        state.rating += attributed + anchored
        state.last_day = match.day
        state.team = team
        self.ledger.add(match.season, "team swings", attributed)
        self.ledger.add(match.season, "anchoring to team level", anchored)

    def national_match(self, game, lineups: dict[int, list[tuple[int, int]]], length: int, season: int) -> bool:
        """Returns whether the match was rated (enough of both line-ups have ratings)."""
        strengths = {}
        for team in (game.home_team_id, game.away_team_id):
            rated = [(self.published(p, game.day), m) for p, m in lineups.get(team, ())]
            total = sum(m for _, m in rated)
            known = [(r, m) for r, m in rated if r is not None]
            if total == 0 or sum(m for _, m in known) < 0.6 * total:
                return False
            strengths[team] = sum(r * m for r, m in known) / sum(m for _, m in known)
        home_advantage = 0.0 if game.neutral else self.team_constants.home_advantage
        difference = strengths[game.home_team_id] + home_advantage - strengths[game.away_team_id]
        margin = te.goal_difference_multiplier(game.goal_difference) if self.team_constants.goal_difference else 1.0
        surprise = margin * (te.score_of(game.goal_difference) - te.expected_score(difference))
        for team, direction in ((game.home_team_id, 1.0), (game.away_team_id, -1.0)):
            for player, minutes in lineups.get(team, ()):
                state = self.states.get(player)
                if state is None:
                    continue
                share = min(minutes, length) / length
                change = direction * self.constants.national_gain * share * surprise
                state.rating += change
                self.ledger.add(season, "national-team calibration", change)
        return True


def match_lengths(appearances: pd.DataFrame) -> dict[int, int]:
    """90, or 120 when anyone played beyond 90 minutes (extra time)."""
    longest = appearances.groupby("game_id").minutes.max()
    return {int(g): (120 if m > 100 else 90) for g, m in longest.items()}


def appearances_by_match(appearances: pd.DataFrame) -> dict[int, dict[int, list[tuple[int, int]]]]:
    played = appearances[appearances.minutes > 0]
    grouped: dict[int, dict[int, list[tuple[int, int]]]] = {}
    for game_id, team_id, player_id, minutes in zip(played.game_id, played.team_id, played.player_id, played.minutes):
        grouped.setdefault(int(game_id), {}).setdefault(int(team_id), []).append((int(player_id), int(minutes)))
    return grouped


def starters_by_match(lineups: pd.DataFrame) -> dict[int, dict[int, list[int]]]:
    starters = lineups[lineups.starter == 1]
    grouped: dict[int, dict[int, list[int]]] = {}
    for game_id, team_id, player_id in zip(starters.game_id, starters.team_id, starters.player_id):
        grouped.setdefault(int(game_id), {}).setdefault(int(team_id), []).append(int(player_id))
    return grouped


@dataclass
class PlayerInputs:
    appearances: dict
    starters: dict
    lengths: dict
    national_games: pd.DataFrame

    @staticmethod
    def load() -> "PlayerInputs":
        appearances = store.appearances()
        return PlayerInputs(appearances_by_match(appearances), starters_by_match(store.lineups()),
                            match_lengths(appearances), store.national_games())


@dataclass
class LineupPrediction:
    game_id: int
    season: int
    team_difference: float
    lineup_difference: float
    outcome: int
    warm: bool


class PlayerRunner:
    """Walks club and national-team matches in date order. It can be copied at any
    point, so a snapshot can continue from settled history with that day's swings."""

    def __init__(self, matches: list[te.Match], team_predictions: list[te.Prediction], inputs: PlayerInputs,
                 constants: PlayerConstants, team_constants: te.TeamConstants, recorder=None):
        self.matches = matches
        self.team_predictions = team_predictions
        self.inputs = inputs
        self.model = PlayerModel(constants, team_constants)
        self.national = list(inputs.national_games.itertuples())
        self.match_position = 0
        self.national_position = 0
        self.recorder = recorder
        self.lineup_predictions: list[LineupPrediction] = []

    def advance_to(self, day: int, sides_of, score_lineups: bool = False) -> None:
        """Processes every match before `day`."""
        while self.match_position < len(self.matches) and self.matches[self.match_position].day < day:
            match_index = self.match_position
            match = self.matches[match_index]
            self.national_until(match.day)
            sides = sides_of(match_index)
            if score_lineups:
                self.lineup_predictions.append(
                    lineup_prediction(match, self.team_predictions[match_index], sides, self.inputs, self.model))
            players = self.inputs.appearances.get(match.game_id)
            if players:
                before = self.recorder.before(players, self.model) if self.recorder else None
                self.model.club_match(match, sides, players, self.inputs.lengths.get(match.game_id, 90))
                if self.recorder:
                    self.recorder.after(match, players, before, self.model)
            self.match_position += 1
        self.national_until(day)

    def national_until(self, day: int) -> None:
        while self.national_position < len(self.national) and self.national[self.national_position].day < day:
            game = self.national[self.national_position]
            self.national_position += 1
            if game.game_id in self.inputs.appearances:
                self.model.national_match(game, self.inputs.appearances[game.game_id],
                                          self.inputs.lengths.get(game.game_id, 90), int(game.season))


def run(matches: list[te.Match], team_predictions: list[te.Prediction], inputs: PlayerInputs,
        constants: PlayerConstants, team_constants: te.TeamConstants, sides_of=None, score_lineups: bool = False,
        recorder=None):
    """One forward pass with the forward filter's swings (or `sides_of`)."""
    runner = PlayerRunner(matches, team_predictions, inputs, constants, team_constants, recorder)
    runner.advance_to(matches[-1].day + 1, sides_of or forward_sides(team_predictions), score_lineups)
    return runner.model, runner.lineup_predictions


def forward_sides(team_predictions: list[te.Prediction]):
    def sides_of(match_index: int) -> dict[int, TeamSide]:
        prediction = team_predictions[match_index]
        return {
            prediction.match.home: TeamSide(prediction.home_rating, prediction.home_swing),
            prediction.match.away: TeamSide(prediction.away_rating, prediction.away_swing),
        }
    return sides_of


def lineup_prediction(match: te.Match, prediction: te.Prediction, sides: dict[int, TeamSide],
                      inputs: PlayerInputs, model: PlayerModel) -> LineupPrediction:
    """Team strength adjusted by the announced starting eleven. The team rating already
    reflects the players who usually play, so only the eleven's deviation from them
    counts: the eleven's mean gap to the team rating, less the minutes-weighted mean
    gap of the usual squad."""
    starters = inputs.starters.get(match.game_id, {})
    bonus_cache: dict = {}
    adjusted = {}
    for team in (match.home, match.away):
        team_rating = sides[team].rating_before
        eleven_gap = mean_gap(starters.get(team, ()), team_rating, match.day, model, bonus_cache)
        usual_gap = usual_squad_gap(team, team_rating, match.day, model, bonus_cache)
        adjusted[team] = team_rating + model.constants.lineup_weight * (eleven_gap - usual_gap)
    home_advantage = 0.0 if match.neutral else model.team_constants.home_advantage
    warm = (min(prediction.home_prior_matches, prediction.away_prior_matches) >= te.MIN_PRIOR_MATCHES
            and len(starters.get(match.home, ())) >= 10 and len(starters.get(match.away, ())) >= 10)
    return LineupPrediction(
        game_id=match.game_id, season=match.season,
        team_difference=prediction.rating_difference,
        lineup_difference=adjusted[match.home] + home_advantage - adjusted[match.away],
        outcome=te.outcome_of(match.goal_difference), warm=warm,
    )


def mean_gap(players, team_rating: float, day: int, model: PlayerModel, bonus_cache: dict) -> float:
    gaps = []
    for player in players:
        rating = model.published(player, day, bonus_cache)
        if rating is None:
            rating = team_rating - model.constants.debutant_offset
        gaps.append(rating - team_rating)
    return sum(gaps) / len(gaps) if gaps else 0.0


def usual_squad_gap(team: int, team_rating: float, day: int, model: PlayerModel, bonus_cache: dict) -> float:
    window = model.minutes
    window.expire(team, day)
    count = len(window.matches.get(team, ()))
    if count == 0:
        return 0.0
    weighted, weights = 0.0, 0.0
    for player in window.squad.get(team, ()):
        state = model.states.get(player)
        if state is None or state.team != team:
            continue
        share = window.share_sum[(team, player)] / count
        weighted += share * (model.published(player, day, bonus_cache) - team_rating)
        weights += share
    return weighted / weights if weights else 0.0


def lineup_scores(lineup_predictions: list[LineupPrediction]) -> tuple[te.Score, te.Score]:
    frame = pd.DataFrame([p.__dict__ for p in lineup_predictions])
    frame = frame[frame.warm]
    team_only = te.score(frame.rename(columns={"team_difference": "difference"}))
    with_lineup = te.score(frame.rename(columns={"lineup_difference": "difference"}))
    return team_only, with_lineup
