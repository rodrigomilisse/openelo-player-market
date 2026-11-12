"""Player model, second design (owner review of 2026-11-12), with each idea a switch.

    published = level + resultsOffset + selectionStanding − absenceDiscount

Ideas, tested one at a time and in combinations (`Variant`):

- split:     the rating is a level (tracks the team; converges after a transfer)
             plus a results offset that only separating evidence moves and that
             never reverts on its own.
- weighted:  the results offset carries an uncertainty; each separating event is
             weighted by it (a Kalman step on the team's surprise), and a transfer
             inflates it so the new club's evidence counts more. Needs `split`.
- absence:   no-show while still at the club is a bounded, recoverable discount
             (injury, suspension); unused on the bench is no absence; only a player
             listed by no covered club for 300 days decays to the replacement level.
- direct:    no personal level at all: the rating is the team's rating after its
             last match plus the minutes bonus (and national points).
- selection: the minutes bonus measured over the player's own last 38 team
             matches (any club), so a new club's evidence replaces the old one
             gradually and nothing before he arrived counts against him.

The baseline is the current candidate: one state per player pulled to the team
level by minutes, a 365-day team-window bonus, and the 120-day decay rule.
Every variant uses minutes filled from line-ups where the dataset lacks them.
Constants here are set by hand for the comparison, not fitted.
"""

import math
from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd

import store
import teamelo as te

LEVEL_RATE = 0.05
DEBUTANT_OFFSET = 50.0
BONUS_SCALE = 200.0
REPLACEMENT = 1250.0
GRACE_DAYS = 120
DECAY_DAYS = 365
RETIRED_AFTER_DAYS = 300
DISCOUNT_CAP = 120.0
DISCOUNT_DAYS = 120.0
WINDOW_MATCHES = 38
OFFSET_PRIOR_VARIANCE = 100.0 ** 2
OFFSET_NOISE_PER_DAY = 1.0
TRANSFER_INFLATION = 50.0 ** 2
PLAYERS_ON_PITCH = 11.0


@dataclass(frozen=True)
class Variant:
    split: bool = False
    weighted: bool = False
    absence: bool = False
    selection: bool = False
    fill: bool = True
    window: int = WINDOW_MATCHES
    squad_window: bool = False
    squad_top: int = 0
    direct: bool = False
    national: str = "none"
    national_scale: float = 50.0
    nt_matches: int = 0
    nt_credit: float = 0.0
    nt_days: int = 0
    bonus_scale: float = BONUS_SCALE

    def name(self) -> str:
        parts = [p for p in ("split", "weighted", "absence", "selection") if getattr(self, p)]
        if self.selection:
            parts.append(f"window {self.window} {'squad' if self.squad_window else 'team'} matches")
        if self.squad_top:
            parts.append(f"mean of top {self.squad_top}")
        if self.direct:
            parts.append("team rating direct")
        if self.national != "none":
            parts.append(f"national {self.national}")
        return " + ".join(parts) or ("baseline" if self.fill else "baseline, no fill")


class Context:
    """Everything a player's computation reads: team matches with the team's rating,
    swing and surprise, each player's listings (start, bench, minutes), and each
    team's squad mean share over the trailing 365 days."""

    def __init__(self, team_constants: te.TeamConstants):
        matches = te.load_matches()
        predictions, _ = te.run(matches, team_constants)
        appearances = store.appearances()
        lengths = {g: (120 if m > 100 else 90) for g, m in appearances.groupby("game_id").minutes.max().items()}
        rows = []
        for p in predictions:
            m = p.match
            expected = te.expected_score(p.rating_difference)
            surprise = te.score_of(m.goal_difference) - expected
            spread = expected * (1 - expected)
            for team, rating, swing, sign in ((m.home, p.home_rating, p.home_swing, 1), (m.away, p.away_rating, p.away_swing, -1)):
                rows.append((m.game_id, team, m.day, rating, swing, sign * surprise, spread, lengths.get(m.game_id, 90)))
        self.team_matches = pd.DataFrame(rows, columns=["game_id", "team_id", "day", "rating", "swing", "surprise",
                                                        "spread", "length"]).sort_values(["day", "game_id"])
        self.by_team = {t: g.reset_index(drop=True) for t, g in self.team_matches.groupby("team_id")}
        self.length = dict(zip(self.team_matches.game_id, self.team_matches.length))
        self.day = dict(zip(self.team_matches.game_id, self.team_matches.day))
        lineups = store.lineups()
        self.appearances = appearances
        self.lineups = lineups
        played = appearances[appearances.minutes > 0].copy()
        played["day"] = played.game_id.map(self.day)
        played = played.dropna(subset=["day"])
        played["share"] = np.minimum(played.minutes, played.game_id.map(self.length)) / played.game_id.map(self.length)
        self.played_by_team = {t: g[["day", "player_id", "share"]].sort_values("day") for t, g in played.groupby("team_id")}
        self.squad_mean = {}
        self.nation_days = {}
        self.national_call_ups = self.call_ups(appearances, lineups)

    def squad_means(self, team: int, top: int = 0):
        """(days, mean share of the squad over the 365 days before each match day):
        the minutes shares summed over the window, ÷ (matches × players). With
        `top`, only the `top` players with the most minutes in the window count
        (16 = a starting eleven and five substitutes), so the mean no longer
        depends on how many fringe players the dataset lists."""
        group = self.played_by_team.get(team)
        if group is None:
            return np.array([]), np.array([])
        days = np.sort(group.day.unique())
        per_day = {d: list(zip(g.player_id, g.share)) for d, g in group.groupby("day")}
        sums, counts, start, result = {}, {}, 0, []
        for i, d in enumerate(days):
            while days[start] < d - 365:
                for p, share in per_day[days[start]]:
                    sums[p] -= share
                    counts[p] -= 1
                    if counts[p] == 0:
                        del sums[p], counts[p]
                start += 1
            matches = i - start
            if matches and sums:
                values = sorted(sums.values(), reverse=True)
                if top:
                    values = values[:top]
                result.append(sum(values) / (matches * len(values)))
            else:
                result.append(np.nan)
            for p, share in per_day[d]:
                sums[p] = sums.get(p, 0.0) + share
                counts[p] = counts.get(p, 0) + 1
        return days, np.array(result)

    def call_ups(self, appearances: pd.DataFrame, lineups: pd.DataFrame) -> dict:
        """Per player: (day, minutes share, mean club rating of the line-up, the
        national team's Elo) for every national-team match he was listed for."""
        games = store.national_games()
        extra_games, extra_lineups, extra_minutes = store.national_extra()
        games = pd.concat([games, extra_games[extra_games.in_store == 0]], ignore_index=True)
        elo = national_elo(games)
        club_rows = appearances[appearances.game_id.isin(self.day.keys()) & (appearances.minutes > 0)].copy()
        club_rows["day"] = club_rows.game_id.map(self.day)
        club_rows = club_rows.sort_values("day")
        club_of = {p: (g.day.to_numpy(), g.team_id.to_numpy()) for p, g in club_rows.groupby("player_id")}
        listed = pd.concat([lineups[lineups.game_id.isin(games.game_id)], extra_lineups]) \
            .drop_duplicates(["game_id", "player_id"])
        played = pd.concat([appearances[appearances.game_id.isin(games.game_id)], extra_minutes]) \
            .drop_duplicates(["game_id", "player_id"])
        minutes = played.set_index(["game_id", "player_id"]).minutes
        lengths = played.groupby("game_id").minutes.max()
        known_lengths = dict(zip(extra_games.game_id, extra_games.length))
        listed_by_game = {g: s for g, s in listed.groupby("game_id")}
        result = {}
        for game in games.itertuples():
            squad = listed_by_game.get(game.game_id)
            if squad is None:
                continue
            length = known_lengths.get(game.game_id) or (120 if lengths.get(game.game_id, 90) > 100 else 90)
            for team, members in squad.groupby("team_id"):
                own = [self.club_rating(club_of, p, game.day) for p in members.player_id]
                known = [c for c in own if c is not None]
                stacked = float(np.mean(known)) if known else 1500.0
                total, count = sum(known), len(known)
                self.nation_days.setdefault(int(team), []).append(int(game.day))
                for player, started, level in zip(members.player_id, members.starter, own):
                    # as for clubs: a starter the dataset lists without minutes played the match
                    played = float(minutes.get((game.game_id, player), length if started == 1 else 0.0))
                    share = min(played, length) / length
                    # the squad's average without him: sum once per match, take his own level out
                    rest = (total - level) / (count - 1) if level is not None and count > 1 else \
                        (total / count if count and level is None else 1500.0)
                    result.setdefault(int(player), []).append(
                        (int(game.day), share, stacked, elo[(game.game_id, team)], rest, int(team)))
        self.nation_days = {t: np.array(sorted(set(d))) for t, d in self.nation_days.items()}
        # national Elo restated on the spread of the club-rating average, so either can drive strength
        rows = [c for calls in result.values() for c in calls]
        club_mean, club_sd = np.mean([c[4] for c in rows]), np.std([c[4] for c in rows])
        elo_mean, elo_sd = np.mean([c[3] for c in rows]), np.std([c[3] for c in rows])
        for player, calls in result.items():
            result[player] = [c + (club_mean + (c[3] - elo_mean) / elo_sd * club_sd,) for c in calls]
        return result

    def club_rating(self, club_of: dict, player: int, day: int):
        timeline = club_of.get(player)
        if timeline is None:
            return None
        days, teams = timeline
        i = np.searchsorted(days, day) - 1
        if i < 0 or day - days[i] > 365:
            return None
        schedule = self.by_team.get(int(teams[i]))
        before = schedule[schedule.day < day]
        return float(before.rating.iloc[-1] + before.swing.iloc[-1]) if len(before) else None

    def squad_mean_at(self, team: int, day: int, top: int = 0) -> float:
        if (team, top) not in self.squad_mean:
            self.squad_mean[(team, top)] = self.squad_means(team, top)
        days, values = self.squad_mean[(team, top)]
        i = np.searchsorted(days, day, side="right") - 1
        return float(values[i]) if i >= 0 and not np.isnan(values[i]) else 0.4

    def listings(self, player: int, fill: bool) -> pd.DataFrame:
        """Every club match the player was listed for: minutes (filled for starters
        without minutes when `fill`), and whether he started or sat on the bench."""
        apps = self.appearances[self.appearances.player_id == player][["game_id", "team_id", "minutes"]]
        lins = self.lineups[self.lineups.player_id == player][["game_id", "team_id", "starter"]]
        rows = apps.merge(lins, on=["game_id", "team_id"], how="outer")
        rows["day"] = rows.game_id.map(self.day)
        rows = rows.dropna(subset=["day"])
        rows["length"] = rows.game_id.map(self.length)
        missing = rows.minutes.isna()
        rows.loc[missing & (rows.starter == 1), "minutes"] = rows.length if fill else np.nan
        if not fill:
            rows = rows.dropna(subset=["minutes"])
        rows["minutes"] = rows.minutes.fillna(0)
        rows["starter"] = rows.starter.fillna((rows.minutes > 0).astype(int))
        return rows.sort_values(["day", "game_id"])


# K by kind of international (World Football Elo style), set by hand.
INTERNATIONAL_K = {"FIFA World Cup": 60.0, "UEFA Euro": 50.0, "Copa América": 50.0,
                   "African Cup of Nations": 50.0, "AFC Asian Cup": 50.0, "Gold Cup": 50.0,
                   "Friendly": 20.0}


def international_k(tournament: str) -> float:
    if tournament in INTERNATIONAL_K:
        return INTERNATIONAL_K[tournament]
    if "qualification" in tournament or "Nations League" in tournament:
        return 40.0
    return 30.0


def national_elo(games: pd.DataFrame) -> dict:
    """National-team strength before each listed match: (game id, team id) -> Elo.
    From every international since 1872 when national.py has been run (K by
    tournament, the margin multiplier, home advantage 100); otherwise a plain
    Elo from the store's tournament results only (K 40), which is compressed.
    Only a strength measure for the national-team points, never fed into
    player ratings."""
    results = store.international_results()
    if results.empty:
        return tournament_elo(games)
    ratings, history = {}, {}
    for r in results.itertuples():
        home, away = ratings.get(r.home, 1500.0), ratings.get(r.away, 1500.0)
        advantage = 0.0 if r.neutral else 100.0
        difference = r.home_goals - r.away_goals
        expected = te.expected_score(home + advantage - away)
        step = international_k(r.tournament) * te.goal_difference_multiplier(difference) * \
            (te.score_of(difference) - expected)
        ratings[r.home], ratings[r.away] = home + step, away - step
        for team, value in ((r.home, home + step), (r.away, away - step)):
            days, values = history.setdefault(team, ([], []))
            days.append(r.day)
            values.append(value)
    names = store.national_team_names()

    def before(team_id: int, day: int) -> float:
        days, values = history.get(names.get(team_id), ([], []))
        i = np.searchsorted(days, day, side="left") - 1
        return float(values[i]) if i >= 0 else 1500.0

    result = {}
    for game in games.itertuples():
        for team in (game.home_team_id, game.away_team_id):
            result[(game.game_id, team)] = before(team, game.day)
    return result


def tournament_elo(games: pd.DataFrame) -> dict:
    """The earlier national-team Elo, from tournament results only (K 40, the
    margin multiplier, host advantage 100)."""
    ratings, before = {}, {}
    for game in games.sort_values(["day", "game_id"]).itertuples():
        home = ratings.get(game.home_team_id, 1500.0)
        away = ratings.get(game.away_team_id, 1500.0)
        before[(game.game_id, game.home_team_id)] = home
        before[(game.game_id, game.away_team_id)] = away
        advantage = 0.0 if game.neutral else 100.0
        expected = te.expected_score(home + advantage - away)
        step = 40.0 * te.goal_difference_multiplier(game.goal_difference) * (te.score_of(game.goal_difference) - expected)
        ratings[game.home_team_id] = home + step
        ratings[game.away_team_id] = away - step
    return before


def stints(listings: pd.DataFrame) -> list[tuple[int, int, int]]:
    """(team, first day, last day) for each consecutive run at one club."""
    runs = []
    for row in listings.itertuples():
        if runs and runs[-1][0] == row.team_id:
            runs[-1][2] = int(row.day)
        else:
            runs.append([int(row.team_id), int(row.day), int(row.day)])
    return [tuple(r) for r in runs]


class Player:

    def __init__(self, variant: Variant):
        self.v = variant
        self.level = None
        self.offset = 0.0
        self.offset_variance = OFFSET_PRIOR_VARIANCE
        self.discount = 0.0
        self.window = deque(maxlen=variant.window)
        self.team = None
        self.last_played = None
        self.last_listed = None
        self.last_offset_day = None

    def rating(self) -> float:
        return self.level + self.offset

    def match(self, row, listed: bool, minutes: float) -> None:
        share = min(minutes, row.length) / row.length
        if self.level is None:
            self.level = row.rating - DEBUTANT_OFFSET
        if self.team is not None and self.team != row.team_id:
            self.transfer()
        self.team = row.team_id
        if not self.v.absence:
            self.apply_decay(row.day)
        usual = np.mean(self.window) if self.window else share
        if self.v.direct:
            self.level = row.rating + row.swing
        elif self.v.split:
            self.level += row.swing + LEVEL_RATE * share * (row.rating - self.level)
            if self.v.weighted:
                self.weighted_evidence(row, share - usual)
            else:
                self.offset += (share - usual) * row.swing
        else:
            self.level += share * row.swing + share * LEVEL_RATE * (row.rating - self.level)
        if self.v.absence:
            self.absence_step(row, listed, share)
        if listed or not self.v.squad_window:
            self.window.append(share)
        if share > 0:
            self.last_played = row.day
        if listed:
            self.last_listed = row.day

    def weighted_evidence(self, row, deviation: float) -> None:
        """A Kalman step on the team's surprise: his deviation from his usual share
        changed the team's strength by deviation × offset ÷ 11."""
        if self.last_offset_day is not None:
            self.offset_variance += OFFSET_NOISE_PER_DAY * (row.day - self.last_offset_day)
        self.last_offset_day = row.day
        if abs(deviation) < 1e-9 or row.spread <= 0:
            return
        slope = te.LOGISTIC_SLOPE
        exposure = deviation / PLAYERS_ON_PITCH
        residual_elo = row.surprise / (slope * row.spread)
        noise = 1.0 / (slope * slope * row.spread)
        gain = self.offset_variance * exposure / (exposure * exposure * self.offset_variance + noise)
        self.offset += gain * (residual_elo - exposure * self.offset)
        self.offset_variance *= 1 - gain * exposure

    def transfer(self) -> None:
        if self.v.weighted:
            self.offset_variance += TRANSFER_INFLATION
        if self.v.selection:
            pass

    def absence_step(self, row, listed: bool, share: float) -> None:
        if share > 0:
            self.discount *= 0.5 ** share
        elif not listed:
            gap = DISCOUNT_CAP - self.discount
            self.discount += gap * (1 - math.exp(-7.0 / DISCOUNT_DAYS))

    def apply_decay(self, day: int) -> None:
        if self.last_played is None:
            return
        idle = day - self.last_played - GRACE_DAYS
        if idle > 0:
            kept = max(0, DECAY_DAYS - idle) / DECAY_DAYS
            self.level = REPLACEMENT + (self.rating() - REPLACEMENT) * kept - self.offset
            self.last_played = day - GRACE_DAYS

    def published(self, day: int, context: Context) -> float:
        rating = self.rating()
        if self.v.absence:
            listed = self.last_listed if self.last_listed is not None else day
            if day - listed > RETIRED_AFTER_DAYS:
                over = day - listed - RETIRED_AFTER_DAYS
                rating = REPLACEMENT + (rating - REPLACEMENT) * max(0, DECAY_DAYS - over) / DECAY_DAYS
            rating -= self.discount
        else:
            if self.last_played is not None:
                idle = day - self.last_played - GRACE_DAYS
                if idle > 0:
                    rating = REPLACEMENT + (rating - REPLACEMENT) * max(0, DECAY_DAYS - idle) / DECAY_DAYS
        return rating + self.bonus(day, context) + self.national_points(day, context)

    def national_points(self, day: int, context: "Context") -> float:
        """Points for being a regular in a national team, never for its results:
        his minutes share over his last 10 national-team call-ups in the past two
        years, times how strong the team he plays in is (`national`):
        flat (no strength), clubs (mean club rating of the line-up, a measure of
        how stacked the squad is), or elo (the national team's own Elo)."""
        if self.v.national == "none":
            return 0.0
        if self.v.nt_matches:
            return self.national_share_points(day, context)
        recent = [c for c in getattr(self, "call_ups", []) if day - 730 <= c[0] < day][-10:]
        if not recent:
            return 0.0
        share = float(np.mean([c[1] for c in recent]))
        if self.v.national == "flat":
            strength = 1.0
        else:
            column = 2 if self.v.national == "clubs" else 3
            level = float(np.mean([c[column] for c in recent]))
            strength = max(0.0, level - 1600.0) / 200.0
        return self.v.national_scale * share * strength

    def national_share_points(self, day: int, context: "Context") -> float:
        """Points only ever added, so a player who is not selected falls behind those
        who are: over his nation's last `nt_matches` covered matches, each match is
        worth his minutes share (at least `nt_credit` if he was in the squad, 0 if he
        was not) times the team's strength, and the sum is divided by the number of
        matches. Strength: the squad's average club rating without him (`clubs`), the
        national Elo on the same spread (`elo`), or 1 (`flat`)."""
        calls = [c for c in getattr(self, "call_ups", []) if c[0] < day]
        if not calls:
            return 0.0
        nation = calls[-1][5]
        days = context.nation_days.get(nation, np.array([]))
        earliest = day - self.v.nt_days if self.v.nt_days else -10 ** 9
        window = days[(days < day) & (days >= earliest)][-self.v.nt_matches:]
        if len(window) == 0:
            return 0.0
        mine = {c[0]: c for c in calls if c[5] == nation and c[0] >= window[0]}
        total = 0.0
        for d in window:
            c = mine.get(int(d))
            if c is None:
                continue
            value = max(c[1], self.v.nt_credit)
            if self.v.national == "flat":
                strength = 1.0
            else:
                level = c[4] if self.v.national == "clubs" else c[6]
                strength = max(0.0, level - 1600.0) / 200.0
            total += value * strength
        return self.v.national_scale * total / len(window)

    def bonus(self, day: int, context: Context) -> float:
        if self.team is None:
            return 0.0
        squad = context.squad_mean_at(self.team, day, self.v.squad_top)
        if self.v.selection:
            share = np.mean(self.window) if self.window else squad
        else:
            share = self.team_window_share(day, context)
        return self.v.bonus_scale * (share - squad)

    def team_window_share(self, day: int, context: Context) -> float:
        return self._team_share.get(day, 0.0) if hasattr(self, "_team_share") else 0.0


def series(player_id: int, variant: Variant, context: Context, snapshot_days: list[int]) -> pd.DataFrame:
    """The player's published rating at each snapshot day, with his team's rating."""
    listings = context.listings(player_id, variant.fill)
    if listings.empty:
        return pd.DataFrame(columns=["day", "player_id", "rating", "team_id", "team_rating"])
    listed = {(int(r.game_id), int(r.team_id)): float(r.minutes) for r in listings.itertuples()}
    timeline = []
    for team, first, last in stints(listings):
        schedule = context.by_team.get(team)
        if schedule is None:
            continue
        end = last
        timeline.append(schedule[(schedule.day >= first) & (schedule.day <= end)])
    if not timeline:
        return pd.DataFrame(columns=["day", "player_id", "rating", "team_id", "team_rating"])
    timeline = pd.concat(timeline).sort_values(["day", "game_id"]).drop_duplicates("game_id")
    state = Player(variant)
    state.call_ups = context.national_call_ups.get(int(player_id), [])
    own_shares = deque()
    rows = []
    position = 0
    events = list(timeline.itertuples())
    for snapshot in snapshot_days:
        while position < len(events) and events[position].day < snapshot:
            row = events[position]
            position += 1
            key = (int(row.game_id), int(row.team_id))
            is_listed = key in listed
            minutes = listed.get(key, 0.0)
            state.match(row, is_listed, minutes)
            own_shares.append((row.day, min(minutes, row.length) / row.length, row.team_id))
        if state.level is None:
            continue
        while own_shares and own_shares[0][0] < snapshot - 365:
            own_shares.popleft()
        team_rows = [s for d, s, t in own_shares if t == state.team]
        team_count = int(((context.by_team[state.team].day >= snapshot - 365) & (context.by_team[state.team].day < snapshot)).sum())
        state._team_share = {snapshot: (sum(team_rows) / team_count) if team_count else 0.0}
        team_now = context.by_team[state.team]
        before = team_now[team_now.day < snapshot]
        team_rating = float(before.rating.iloc[-1] + before.swing.iloc[-1]) if len(before) else np.nan
        rows.append((snapshot, player_id, state.published(snapshot, context), state.team, team_rating))
    return pd.DataFrame(rows, columns=["day", "player_id", "rating", "team_id", "team_rating"])
