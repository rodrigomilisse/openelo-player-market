"""Team-level evaluation (FINDINGS.md §4): fitting the constants, scoring variants
against the plain-Elo baseline, the hindsight correction, clubelo and bookmakers."""

import json
import pickle
from multiprocessing import Pool

import numpy as np
import pandas as pd

import hindsight as hs
import store
import teamelo as te

CONSTANTS_PATH = store.RESULTS_DIR / "team_constants.json"
REPLAY_PATH = store.RESULTS_DIR / "replay.pkl"

PLAIN_GRID = {
    "k_factor": [10, 14, 17, 20, 23, 26, 30, 35],
    "home_advantage": [40, 50, 60, 70, 80, 90, 100],
    "league_seed_offset": [0, 50, 100, 150, 200, 250],
    "unknown_seed_offset": [100, 200, 300, 400, 500],
}
UNCERTAINTY_GRID = {
    "process_noise": [0.5, 1, 1.5, 2, 3, 4, 6, 8],
    "initial_variance": [100 ** 2, 150 ** 2, 200 ** 2, 250 ** 2, 300 ** 2, 400 ** 2],
    "home_advantage": [50, 60, 70, 80, 90],
    "league_seed_offset": [0, 50, 100, 150, 200, 250],
    "unknown_seed_offset": [100, 200, 300, 400, 500],
}
STAGE_GRID = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
TIER2_WEIGHTS = [0.1, 0.25, 0.5, 1, 2, 4, 8]

HINDSIGHT_VARIANTS = [(30, 1), (90, 1), (180, 1), (365, 1), (90, 2), (180, 2), (365, 2), (180, 3), (180, 4)]


def quiet(_message):
    pass


def fit_team_variants() -> dict:
    """Fits every variant on the fit seasons and scores it on the test seasons."""
    matches = te.load_matches()
    rows, scores = [], {}

    plain, _ = te.coordinate_search(matches, te.TeamConstants(uncertainty=False, goal_difference=False),
                                    PLAIN_GRID, rounds=3, log=quiet)
    margin, _ = te.coordinate_search(matches, plain.with_(goal_difference=True),
                                     {"k_factor": PLAIN_GRID["k_factor"], "home_advantage": [50, 60, 70, 80, 90]},
                                     rounds=2, log=quiet)
    uncertainty, _ = te.coordinate_search(matches, te.TeamConstants(), UNCERTAINTY_GRID, rounds=3, log=quiet)
    stages, _ = te.coordinate_search(matches, uncertainty,
                                     {f"stage:{s}": STAGE_GRID for s in te.STAGES if s != "league"}, rounds=2, log=quiet)
    state, _ = te.coordinate_search(matches, uncertainty, {"state_floor": [0.0, 0.25, 0.5, 0.75, 1.0],
                                                           "goal_value": [150, 200, 300, 400, 600]}, rounds=2, log=quiet)
    with_scales = uncertainty.with_(corner_scale=share_scale(matches, uncertainty, "corner_share"),
                                    card_scale=share_scale(matches, uncertainty, "card_share"))
    corners, _ = te.coordinate_search(matches, with_scales, {"corner_weight": TIER2_WEIGHTS}, rounds=1, log=quiet)
    cards, _ = te.coordinate_search(matches, with_scales, {"card_weight": TIER2_WEIGHTS}, rounds=1, log=quiet)

    variants = {
        "plain Elo (baseline)": plain, "Elo + goal difference": margin, "uncertainty + goal difference": uncertainty,
        "+ match importance": stages, "+ competition state": state, "+ corners (tier 2)": corners,
        "+ cards (tier 2)": cards,
    }
    for name, constants in variants.items():
        predictions, _ = te.run(matches, constants)
        scores[name] = te.score(te.scored_frame(predictions))
        rows.append(scores[name].row(name))

    baseline = scores["uncertainty + goal difference"]
    decisions = {}
    for name in ["+ match importance", "+ competition state", "+ corners (tier 2)", "+ cards (tier 2)"]:
        mean, low, high = te.paired_difference(scores[name].test_losses, baseline.test_losses)
        decisions[name] = {"gain": mean, "low": low, "high": high, "adopted": bool(mean <= -0.001 and high < 0)}
    candidate = uncertainty
    if decisions["+ corners (tier 2)"]["adopted"]:
        candidate = candidate.with_(corner_scale=corners.corner_scale, corner_weight=corners.corner_weight)
    if decisions["+ cards (tier 2)"]["adopted"]:
        candidate = candidate.with_(card_scale=cards.card_scale, card_weight=cards.card_weight)
    if decisions["+ match importance"]["adopted"]:
        candidate = candidate.with_(stage_weights=stages.stage_weights)
    if decisions["+ competition state"]["adopted"]:
        candidate = candidate.with_(state_floor=state.state_floor, goal_value=state.goal_value)

    predictions, _ = te.run(matches, candidate)
    scores["candidate (forward only)"] = te.score(te.scored_frame(predictions))
    against_plain = te.paired_difference(scores["candidate (forward only)"].test_losses, scores["plain Elo (baseline)"].test_losses)
    result = {
        "table": rows, "decisions": decisions, "candidate_vs_plain": against_plain,
        "constants": {name: constants_dict(c) for name, c in variants.items()},
        "candidate": constants_dict(candidate),
        "logit": scores["candidate (forward only)"].logit.__dict__,
    }
    store.output_path(store.RESULTS_DIR, CONSTANTS_PATH.name).write_text(json.dumps(result, indent=1, default=float))
    return result


def share_scale(matches, constants, attribute: str) -> float:
    """The scale at which the expected score best predicts a tier-2 share (least
    squares on the fit seasons)."""
    predictions, _ = te.run(matches, constants)
    rows = [(p.rating_difference, getattr(p.match, attribute)) for p in predictions
            if p.match.season in te.FIT_SEASONS and getattr(p.match, attribute) is not None
            and min(p.home_prior_matches, p.away_prior_matches) >= te.MIN_PRIOR_MATCHES]
    difference = np.array([r[0] for r in rows])
    observed = np.array([r[1] for r in rows])
    best = min((float(np.mean((observed - 1 / (1 + 10 ** (-scale * difference / 400))) ** 2)), round(float(scale), 2))
               for scale in np.arange(-1.0, 1.01, 0.05))
    return best[1]


def constants_dict(constants: te.TeamConstants) -> dict:
    return dict(constants.__dict__)


def load_candidate() -> te.TeamConstants:
    if not CONSTANTS_PATH.exists():
        raise SystemExit("Run `evaluate.py team` first.")
    return te.TeamConstants(**json.loads(CONSTANTS_PATH.read_text())["candidate"])


def as_of_frame(predictions: list[te.Prediction], differences: dict) -> pd.DataFrame:
    frame = pd.DataFrame({
        "game_id": [p.match.game_id for p in predictions],
        "season": [p.match.season for p in predictions],
        "difference": [differences[i] for i in range(len(predictions))],
        "outcome": [te.outcome_of(p.match.goal_difference) for p in predictions],
        "warm": [min(p.home_prior_matches, p.away_prior_matches) >= te.MIN_PRIOR_MATCHES for p in predictions],
    })
    return frame[frame.warm]


def hindsight_job(variant: tuple[int, int]) -> dict:
    lag, iterations = variant
    constants = load_candidate()
    matches = te.load_matches()
    predictions, _ = te.run(matches, constants)
    forward = te.score(te.scored_frame(predictions))
    replay = hs.HindsightReplay(matches, predictions, constants, lag, iterations).run()
    corrected = te.score(as_of_frame(predictions, replay.as_of_differences))
    mean, low, high = te.paired_difference(corrected.test_losses, forward.test_losses)
    return {"lag_days": lag, "iterations": iterations, "fit log loss": corrected.fit_log_loss,
            "test log loss": corrected.test_log_loss, "test Brier": corrected.test_brier,
            "forward test log loss": forward.test_log_loss, "gain": mean, "low": low, "high": high}


def score_hindsight_variants(processes: int = 4) -> list[dict]:
    with Pool(processes) as pool:
        rows = pool.map(hindsight_job, HINDSIGHT_VARIANTS)
    best = min(rows, key=lambda r: r["fit log loss"])
    path = store.output_path(store.RESULTS_DIR, "hindsight_variants.json")
    path.write_text(json.dumps({"variants": rows, "chosen": best}, indent=1))
    return rows


def chosen_hindsight() -> tuple[int, int]:
    path = store.RESULTS_DIR / "hindsight_variants.json"
    if not path.exists():
        raise SystemExit("Run `evaluate.py hindsight` first.")
    chosen = json.loads(path.read_text())["chosen"]
    return chosen["lag_days"], chosen["iterations"]


def month_starts(first: str = "2013-01-01", last: str = "2026-07-01") -> list[int]:
    return [int((day - store.EPOCH).days) for day in pd.date_range(first, last, freq="MS")]


def run_final_replay() -> hs.ReplayResult:
    """The candidate with its chosen correction, as of every match day, with monthly
    snapshots for the player series and the diagnostics for §4.4."""
    constants = load_candidate()
    lag, iterations = chosen_hindsight()
    matches = te.load_matches()
    predictions, _ = te.run(matches, constants)
    core = core_league_teams()
    tracked = {t for t in core}
    references = [d for d in month_starts("2019-08-01", "2025-12-01")][::2]
    result = hs.HindsightReplay(matches, predictions, constants, lag, iterations).run(
        snapshot_days=month_starts(), reference_days=references, tracked_teams=tracked)
    with open(store.output_path(store.RESULTS_DIR, REPLAY_PATH.name), "wb") as out:
        pickle.dump(result, out)
    return result


def load_replay() -> hs.ReplayResult:
    if not REPLAY_PATH.exists():
        raise SystemExit("Run `evaluate.py replay` first.")
    with open(REPLAY_PATH, "rb") as source:
        return pickle.load(source)


CORE_LEAGUES = ["GB1", "ES1", "IT1", "L1", "FR1", "NL1", "PO1", "BE1", "TR1", "GR1", "SC1", "RU1", "UKR1", "DK1"]


def core_league_teams() -> set[int]:
    games = store.query(f"SELECT home_team_id, away_team_id FROM game WHERE competition_id IN ({','.join('?' * len(CORE_LEAGUES))})",
                        tuple(CORE_LEAGUES))
    return set(games.home_team_id) | set(games.away_team_id)


def hindsight_diagnostics(result: hs.ReplayResult) -> dict:
    moves = np.array(result.day_off_moves)
    revisions = pd.DataFrame(result.revisions, columns=["reference", "weeks", "team", "rating"])
    first = revisions[revisions.weeks == 0].set_index(["reference", "team"]).rating
    revisions = revisions.join(first.rename("published"), on=["reference", "team"]).dropna()
    revisions["moved"] = (revisions.rating - revisions.published).abs()
    by_week = revisions.groupby("weeks").moved.agg(["mean", lambda s: s.quantile(0.9), "max"]).round(2)
    by_week.columns = ["mean", "p90", "max"]
    final = revisions.sort_values("weeks").groupby(["reference", "team"]).last()
    return {
        "day_off_moves": {
            "count": int(len(moves)), "zero share": float(np.mean(moves < 1e-9)),
            "median": float(np.median(moves)), "p90": float(np.percentile(moves, 90)),
            "p99": float(np.percentile(moves, 99)), "max": float(moves.max()),
        },
        "revision_by_week": by_week.reset_index().to_dict("records"),
        "final_revision": {"mean": float(final.moved.mean()), "p90": float(final.moved.quantile(0.9)),
                           "max": float(final.moved.max())},
    }


def benchmarks() -> dict:
    """clubelo and bookmaker odds as references, on the matches each covers."""
    constants = load_candidate()
    replay = load_replay()
    matches = te.load_matches()
    predictions, _ = te.run(matches, constants)
    frame = as_of_frame(predictions, replay.as_of_differences)
    games = store.club_games().set_index("game_id")
    ours = te.score(frame)
    test = frame[frame.season.isin(te.TEST_SEASONS)].copy()
    test["ours"] = ours.test_losses.reindex(test.game_id).to_numpy()

    clubelo = clubelo_differences(frame, games)
    with_clubelo = frame.merge(clubelo, on="game_id")
    clubelo_score = te.score(with_clubelo.drop(columns="difference").rename(columns={"clubelo": "difference"}))
    common = test[test.game_id.isin(clubelo_score.test_losses.index)]
    clubelo_vs_ours = te.paired_difference(ours.test_losses.loc[common.game_id], clubelo_score.test_losses.loc[common.game_id])

    odds = games.loc[test.game_id, ["odd_home", "odd_draw", "odd_away"]].dropna()
    implied = 1.0 / odds.to_numpy()
    implied = implied / implied.sum(axis=1, keepdims=True)
    outcomes = test.set_index("game_id").loc[odds.index, "outcome"].to_numpy()
    book_loss, book_brier = te.match_losses(implied[:, [2, 1, 0]], outcomes)
    ours_on_odds = ours.test_losses.loc[odds.index]
    rank = rank_correlations(replay)
    return {
        "ours": {"matches": int(len(test)), "log loss": float(test.ours.mean())},
        "clubelo": {"matches": int(len(common)), "ours": float(ours.test_losses.loc[common.game_id].mean()),
                    "clubelo": float(clubelo_score.test_losses.loc[common.game_id].mean()),
                    "ours minus clubelo": clubelo_vs_ours},
        "bookmakers": {"matches": int(len(odds)), "ours": float(ours_on_odds.mean()),
                       "bookmakers": float(book_loss.mean()), "bookmakers Brier": float(book_brier.mean())},
        "rank": rank,
    }


def clubelo_differences(frame: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """clubelo's rating difference before each match, from its most recent snapshot at
    least one day old (snapshots are taken on the 1st and 15th)."""
    elo = store.clubelo()
    elo["day"] = (pd.to_datetime(elo.date) - store.EPOCH).dt.days
    by_team = {team: group.sort_values("day")[["day", "elo"]].to_numpy() for team, group in elo.groupby("team_id")}
    rows = []
    for game_id in frame.game_id:
        game = games.loc[game_id]
        home = latest_before(by_team.get(int(game.home_team_id)), int(game.day))
        away = latest_before(by_team.get(int(game.away_team_id)), int(game.day))
        if home is not None and away is not None:
            rows.append((game_id, home - away))
    return pd.DataFrame(rows, columns=["game_id", "clubelo"])


def latest_before(series, day: int):
    if series is None:
        return None
    position = np.searchsorted(series[:, 0], day, side="left") - 1
    if position < 0 or day - series[position, 0] > 31:
        return None
    return float(series[position, 1])


def rank_correlations(replay: hs.ReplayResult) -> dict:
    elo = store.clubelo()
    names = store.teams().set_index("team_id")["name"].to_dict()
    core = core_league_teams()
    rows, disagreements = [], []
    for year in range(2014, 2026):
        date = f"{year}-06-01"
        day = int((pd.Timestamp(date) - store.EPOCH).days)
        ours = replay.snapshot_states.get(day)
        theirs = elo[elo.date == date].set_index("team_id").elo
        if ours is None or theirs.empty:
            continue
        common = [t for t in theirs.index if t in ours and t in core]
        a = pd.Series({t: ours[t] for t in common})
        b = theirs.loc[common]
        spearman = float(a.rank().corr(b.rank()))
        rows.append({"date": date, "teams": len(common), "spearman": round(spearman, 3)})
        if year == 2025:
            ranks = pd.DataFrame({"ours": a.rank(ascending=False), "clubelo": b.rank(ascending=False)})
            ranks["gap"] = ranks.ours - ranks.clubelo
            ranks["name"] = [names.get(t, t) for t in ranks.index]
            ranks["our rating"] = a.round(0)
            ranks["clubelo rating"] = b.round(0)
            top = ranks.reindex(ranks.gap.abs().sort_values(ascending=False).index).head(12)
            disagreements = top.to_dict("records")
    return {"by_date": rows, "largest_disagreements_2025": disagreements}
