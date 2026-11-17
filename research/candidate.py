"""The simplified candidate and its metrics (FINDINGS.md, owner review of 2026-11-12).

Team: Elo with an uncertainty per team and the margin multiplier, forward only:
no hindsight correction, no corners. Players: the team swing shared by minutes,
the pull towards the team's rating, and the minutes bonus. Each tracked player's
series is computed straight from the precomputed team ratings, one loop over his
own appearances; only the line-up test (C6) needs the whole pool.
"""

import itertools
import json
from multiprocessing import Pool

import numpy as np
import pandas as pd

import player_checks as pc
import playerelo as pe
import store
import team_checks
import teamelo as te

TOP_LEAGUES = ["GB1", "ES1", "IT1", "L1", "FR1", "PO1", "NL1", "BE1", "TR1", "SC1"]
GRID = list(itertools.product([0.05, 0.1, 0.2], [0.2, 0.3], [0, 100, 200]))
_SHARED = {}


def team_constants() -> te.TeamConstants:
    fitted = json.loads(team_checks.CONSTANTS_PATH.read_text())["constants"]["uncertainty + goal difference"]
    return te.TeamConstants(**fitted)


def top_league_inputs() -> pe.PlayerInputs:
    """Player inputs for clubs of the top 10 leagues only (all their club matches);
    team Elo still uses every match."""
    clubs = store.query(f"""SELECT DISTINCT home_team_id AS team_id FROM game
                            WHERE competition_id IN ({','.join('?' * len(TOP_LEAGUES))})""", tuple(TOP_LEAGUES))
    clubs = set(clubs.team_id)
    appearances = store.appearances()
    appearances = appearances[appearances.team_id.isin(clubs)]
    lineups = store.lineups()
    lineups = lineups[lineups.team_id.isin(clubs) & (lineups.starter == 1)]
    return pe.PlayerInputs(pe.appearances_by_match(appearances), pe.starters_by_match(lineups),
                           pe.match_lengths(appearances), store.national_games().iloc[0:0])


def load_shared():
    _SHARED["constants"] = team_constants()
    _SHARED["matches"] = te.load_matches()
    _SHARED["predictions"], _ = te.run(_SHARED["matches"], _SHARED["constants"])
    _SHARED["inputs"] = top_league_inputs()


def _job(config):
    anchor, weight, bonus = config
    constants = pe.PlayerConstants(anchor_rate=anchor, lineup_weight=weight, bonus_scale=bonus)
    _, lineup = pe.run(_SHARED["matches"], _SHARED["predictions"], _SHARED["inputs"], constants,
                       _SHARED["constants"], score_lineups=True)
    team_only, with_lineup = pe.lineup_scores(lineup)
    return config, with_lineup.fit_log_loss - team_only.fit_log_loss, with_lineup.test_losses, team_only.test_losses


def fit_players() -> dict:
    load_shared()
    with Pool(3) as pool:
        results = pool.map(_job, GRID)
    best = min(results, key=lambda r: r[1])
    config, fit_gain, losses, team_only = best
    no_bonus = next(r for r in results if r[0] == (config[0], config[1], 0))
    return {
        "grid": [{"anchor": c[0], "lineup weight": c[1], "bonus": c[2], "fit gain": round(g, 5),
                  "test gain": round(float(l.mean() - t.mean()), 5)} for c, g, l, t in results],
        "chosen": {"anchor": config[0], "lineup weight": config[1], "bonus": config[2]},
        "C6 test gain (lineup vs team only)": te.paired_difference(losses, team_only),
        "bonus vs none at same constants": te.paired_difference(losses, no_bonus[2]) if config[2] else None,
    }


def squad_shares(appearances: pd.DataFrame, lengths: dict) -> pd.DataFrame:
    """Each appearance's share of a full match, with team and day."""
    appearances = appearances[appearances.minutes > 0].copy()
    appearances["length"] = appearances.game_id.map(lengths).fillna(90)
    appearances["share"] = np.minimum(appearances.minutes, appearances.length) / appearances.length
    return appearances


def bonus_at(day: int, team: int, player: int, shares_by_team: dict, team_days: dict, scale: float) -> float:
    if scale == 0:
        return 0.0
    days = team_days.get(team)
    rows = shares_by_team.get(team)
    if days is None or rows is None:
        return 0.0
    window = (days > day - 365) & (days < day)
    count = int(window.sum())
    if count == 0:
        return 0.0
    recent = rows[(rows.day > day - 365) & (rows.day < day)]
    totals = recent.groupby("player_id").share.sum() / count
    if player not in totals.index:
        return 0.0
    return scale * (totals.loc[player] - totals.mean())


def tracked_series(constants: pe.PlayerConstants, team: te.TeamConstants) -> pd.DataFrame:
    """Monthly ratings for the tracked players, each from his own appearances."""
    matches = te.load_matches()
    predictions, _ = te.run(matches, team)
    sides = {}
    for p in predictions:
        sides[(p.match.game_id, p.match.home)] = (p.match.day, p.home_rating, p.home_swing)
        sides[(p.match.game_id, p.match.away)] = (p.match.day, p.away_rating, p.away_swing)
    inputs = pe.PlayerInputs.load()
    shares = squad_shares(store.appearances(), inputs.lengths)
    shares["day"] = shares.game_id.map({p.match.game_id: p.match.day for p in predictions})
    shares = shares.dropna(subset=["day"])
    shares_by_team = {t: g[["day", "player_id", "share"]] for t, g in shares.groupby("team_id")}
    team_days = {}
    for p in predictions:
        team_days.setdefault(p.match.home, []).append(p.match.day)
        team_days.setdefault(p.match.away, []).append(p.match.day)
    team_days = {t: np.array(sorted(set(d))) for t, d in team_days.items()}
    snapshots = team_checks.month_starts()
    model = pe.PlayerModel(constants, team)
    rows = []
    tracked = shares[shares.player_id.isin(pc.tracked_ids())].sort_values("day")
    for player, career in tracked.groupby("player_id"):
        state = None
        events = list(career.itertuples())
        position = 0
        for snapshot in snapshots:
            while position < len(events) and events[position].day < snapshot:
                event = events[position]
                position += 1
                side = sides.get((event.game_id, event.team_id))
                if side is None:
                    continue
                _, rating_before, swing = side
                if state is None:
                    state = pe.PlayerState(rating_before - constants.debutant_offset, int(event.day), int(event.team_id))
                state.rating = model.decayed(state, int(event.day))
                gap = rating_before - state.rating
                state.rating += event.share * swing + event.share * constants.anchor_rate * gap
                state.last_day, state.team = int(event.day), int(event.team_id)
            if state is None:
                continue
            published = model.decayed(state, snapshot) + bonus_at(snapshot, state.team, player, shares_by_team,
                                                                  team_days, constants.bonus_scale)
            rows.append((snapshot, player, published, published, state.team, state.last_day))
    return pd.DataFrame(rows, columns=["day", "player_id", "rating", "forward_rating", "team_id", "last_day"])


def metrics(snapshots: pd.DataFrame) -> dict:
    result = {}
    for name, players in (("set A", set(pc.set_a_ids())), ("set B", set(pc.set_b_groups()))):
        moves = pc.substantial_moves(players)
        coverage = pc.Coverage(players)
        series = pc.RatingSeries(snapshots[snapshots.player_id.isin(players)])
        result[name] = {
            "C7 primary window": pc.directional(moves, series, coverage, 6, 6),
            "lag scan": {f"{lag:+d}": round(pc.directional(moves, series, coverage, 6, 6, lag)["share"], 3)
                         for lag in range(-12, 13, 3)},
            "rises": pc.directional(moves[moves.direction > 0], series, coverage, 6, 6)["share"],
            "falls": pc.directional(moves[moves.direction < 0], series, coverage, 6, 6)["share"],
        }
    groups = pc.player_groups()
    players = set(groups)
    coverage = pc.Coverage(players)
    catch = pc.catch_up_times(pc.substantial_moves(players), pc.RatingSeries(snapshots), coverage)
    per_player = catch.groupby("player_id").agg(moves=("caught", "size"), caught=("caught", "mean"),
                                                months=("months", "median"))
    per_player["group"] = [groups[p] for p in per_player.index]
    by_group = per_player.groupby("group").agg(players=("moves", "size"), moves=("moves", "sum"),
                                               caught=("caught", "mean"), median_months=("months", "median"))
    names = store.players().set_index("player_id")["name"].to_dict()
    result["C8b catch-up by group"] = by_group.round(3).reset_index().to_dict("records")
    result["never caught up"] = [names.get(p, p) for p in per_player[per_player.caught == 0].index]
    events = pc.separating_events(players)
    waits, gaps, eligible, within = [], [], 0, 0
    for player, days in coverage.days.items():
        if len(days) == 0 or days[-1] - days[0] < 365:
            continue
        eligible += 1
        later = [d for d in events.get(player, []) if d >= days[0]]
        if later:
            waits.append(later[0] - days[0])
            within += later[0] - days[0] <= 365
            gaps += list(np.diff(later))
    result["C8a separating events"] = {
        "eligible": eligible, "share with one in first season": within / eligible,
        "mean days between events": float(np.mean(gaps)), "p90 days between": float(np.percentile(gaps, 90)),
        "longest stretch (days)": int(np.max(gaps))}
    return result
