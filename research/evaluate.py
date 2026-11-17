#!/usr/bin/env python3
"""Regenerates every number in FINDINGS.md from the local research store.

Run the commands in this order; each caches what the next ones read under
data/raw/results/ (gitignored):

    team           fit and score the team variants (§4.1–4.3, 4.5)       ~10 min
    hindsight      score the hindsight-correction variants (§4.4)        ~1 h, parallel
    replay         run the chosen candidate as of every match day (§4.4) ~15 min
    benchmarks     clubelo and bookmaker references (§4.6)
    players        fit the player constants on line-up predictions (§5.2) ~30 min, parallel
    rate           as-of player series at monthly snapshots (§5.3)
    transfermarkt  directional agreement with Transfermarkt (C7, §5.4)
    convergence    separating events and catch-up (C8, §5.5)
    collinearity   pairs that never separate (C10, §5.8)
    confounds      minutes-bonus confound tests (§5.9)
    positions      swing size and shape by position (§5.10)
    national       national-team calibration (§5.11)
    exact          integer reference and its checks (C1, C9, C11, C12, §6) ~1 h
    scale-zero     how the zero of the scale moves a proportional split (§6.6)
"""

import argparse
import json

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)


def show(title: str, value) -> None:
    print(f"\n== {title}")
    if isinstance(value, pd.DataFrame):
        print(value.to_string(index=False))
    elif isinstance(value, (list, dict)):
        print(json.dumps(value, indent=1, default=lambda v: round(float(v), 5)))
    else:
        print(value)


def cmd_team(_args) -> None:
    import team_checks
    result = team_checks.fit_team_variants()
    show("team variants (fit on 2014/15–2018/19, scored on 2019/20–2025/26)", pd.DataFrame(result["table"]))
    show("feature decisions (test gain over uncertainty + goal difference; adopt if ≤ −0.001 and interval < 0)",
         result["decisions"])
    show("C2: candidate minus plain Elo, test log loss (mean, 95% interval)", result["candidate_vs_plain"])
    show("candidate constants", result["candidate"])


def cmd_hindsight(args) -> None:
    import team_checks
    rows = team_checks.score_hindsight_variants(args.processes)
    show("hindsight variants, as-of scoring (gain = corrected minus forward-only test log loss)", pd.DataFrame(rows))


def cmd_replay(_args) -> None:
    import team_checks
    result = team_checks.run_final_replay()
    show("hindsight diagnostics", team_checks.hindsight_diagnostics(result))


def cmd_benchmarks(_args) -> None:
    import team_checks
    show("benchmarks", team_checks.benchmarks())


def cmd_players(args) -> None:
    import player_checks
    result = player_checks.fit_players(args.processes)
    grid = pd.DataFrame(result["grid"]).sort_values("fit gain")
    show("player constants by line-up adjusted log loss (gain = with line-up minus team only)", grid.round(5))
    show("C6 and the minutes bonus", {k: v for k, v in result.items() if k != "grid"})


def cmd_rate(_args) -> None:
    import player_checks
    show("as-of player series", player_checks.rate())


def cmd_transfermarkt(_args) -> None:
    import player_checks
    show("C7: direction against Transfermarkt", player_checks.transfermarkt())


def cmd_convergence(_args) -> None:
    import player_checks
    show("C8: convergence", player_checks.convergence())


def cmd_collinearity(_args) -> None:
    import player_checks
    show("C10: pairs that never separate", player_checks.collinearity())


def cmd_confounds(_args) -> None:
    import player_checks
    show("minutes bonus: confounds (team surprise per unit of absent start share)", player_checks.confounds())


def cmd_positions(_args) -> None:
    import player_checks
    show("swing size and shape by position", pd.DataFrame(player_checks.positions()["table"]))


def cmd_national(_args) -> None:
    import player_checks
    show("national-team calibration", player_checks.national())


def cmd_exact(args) -> None:
    import exact_checks
    if args.compute_only:
        exact_checks.run_full()
        return
    result = exact_checks.load_exact() if args.reuse else exact_checks.run_full()
    show("C11: integer against float", exact_checks.compare_with_float(result))
    show("C9: conservation", exact_checks.conservation(result))
    show("C1 and C12 (data before 2016-01-01)", exact_checks.truncated_runs())


def cmd_scale_zero(_args) -> None:
    import exact_checks
    show("dividend split against the zero of the scale (not a dividend design)",
         exact_checks.scale_zero(exact_checks.load_exact()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("team").set_defaults(func=cmd_team)
    hindsight = sub.add_parser("hindsight")
    hindsight.add_argument("--processes", type=int, default=4)
    hindsight.set_defaults(func=cmd_hindsight)
    sub.add_parser("replay").set_defaults(func=cmd_replay)
    sub.add_parser("benchmarks").set_defaults(func=cmd_benchmarks)
    players = sub.add_parser("players")
    players.add_argument("--processes", type=int, default=3)
    players.set_defaults(func=cmd_players)
    for name, func in [("rate", cmd_rate), ("transfermarkt", cmd_transfermarkt), ("convergence", cmd_convergence),
                       ("collinearity", cmd_collinearity), ("confounds", cmd_confounds),
                       ("positions", cmd_positions), ("national", cmd_national)]:
        sub.add_parser(name).set_defaults(func=func)
    exact_parser = sub.add_parser("exact")
    exact_parser.add_argument("--reuse", action="store_true", help="check the last integer run instead of redoing it")
    exact_parser.add_argument("--compute-only", action="store_true", help="run and save the integer reference, no checks")
    exact_parser.set_defaults(func=cmd_exact)
    sub.add_parser("scale-zero").set_defaults(func=cmd_scale_zero)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
