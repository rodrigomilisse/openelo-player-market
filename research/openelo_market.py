#!/usr/bin/env python3
"""OpenELO vs Transfermarkt market-value validation tool (Phase 1).

Subcommands:
    scrape        Resolve + fetch Transfermarkt market-value history for the
                   curated player list (data/openelo_market.sqlite3). Scrapes
                   each player once; re-run is a no-op unless --force.
    list           Show scrape status for every curated player.
    compare NAME   Plot OpenELO vs Transfermarkt value over time for one player.
    average        Plot the average OpenELO vs average Transfermarkt value
                   across every scraped player.
    correlation    Lagged cross-correlation between OpenELO and Transfermarkt
                   value (single player, or averaged across all if omitted),
                   to check whether a phase shift is needed.

Examples:
    python openelo_market.py scrape
    python openelo_market.py scrape --player "Lionel Messi" --force
    python openelo_market.py compare "Lionel Messi" --out outputs/messi.png
    python openelo_market.py average --out outputs/average.png
    python openelo_market.py correlation --max-lag 24
    python openelo_market.py correlation --player "Cristiano Ronaldo"
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

import analysis
import db
import tm_client
from players import MANUAL_TM_ID_OVERRIDES, PLAYER_NAMES

OUTPUTS_DIR = Path(__file__).parent / "outputs"

SCRAPE_DELAY_SECONDS = 1.5  # be polite to the (rate-limited) API


def cmd_scrape(args: argparse.Namespace) -> None:
    db.init_db()
    import time

    names = [args.player] if args.player else PLAYER_NAMES
    unknown = [n for n in names if n not in PLAYER_NAMES]
    if unknown:
        print(f"Not in curated PLAYER_NAMES list: {unknown}", file=sys.stderr)
        sys.exit(1)

    with db.connect() as conn:
        for name in names:
            player = db.get_or_create_player(conn, name)
            if player["scraped_at"] and not args.force:
                print(f"[skip] {name} (already scraped at {player['scraped_at']})")
                continue

            tm_id = MANUAL_TM_ID_OVERRIDES.get(name)
            tm_name = None
            if not tm_id:
                try:
                    results = tm_client.search_player(name)
                except tm_client.TransfermarktClientError as exc:
                    print(f"[error] search failed for {name}: {exc}", file=sys.stderr)
                    continue
                if not results:
                    print(f"[error] no Transfermarkt search results for {name}", file=sys.stderr)
                    continue
                top = results[0]
                tm_id, tm_name = top["id"], top["name"]
                if len(results) > 1:
                    others = ", ".join(f"{r['name']} ({r['id']})" for r in results[1:4])
                    print(
                        f"[ambiguous?] {name} -> picked {tm_name} ({tm_id}); "
                        f"other candidates: {others}. Add to MANUAL_TM_ID_OVERRIDES "
                        f"in players.py if wrong."
                    )
            else:
                tm_name = f"(manual override {tm_id})"

            db.set_resolution(conn, player["id"], tm_id, tm_name)

            try:
                history = tm_client.get_market_value_history(tm_id)
            except tm_client.TransfermarktClientError as exc:
                print(f"[error] market value fetch failed for {name}: {exc}", file=sys.stderr)
                continue

            rows = [
                {
                    "date": h["date"],
                    "market_value_eur": h.get("marketValue"),
                    "club_name": h.get("clubName"),
                    "age": h.get("age"),
                }
                for h in history
            ]
            db.replace_market_values(conn, player["id"], rows)
            print(f"[ok] {name} -> {tm_name} ({tm_id}): {len(rows)} data points")
            time.sleep(SCRAPE_DELAY_SECONDS)


def cmd_list(args: argparse.Namespace) -> None:
    db.init_db()
    with db.connect() as conn:
        rows = db.get_all_players(conn)
    known = {r["name"]: r for r in rows}
    for name in PLAYER_NAMES:
        r = known.get(name)
        if not r or not r["scraped_at"]:
            print(f"[not scraped] {name}")
        else:
            print(f"[scraped]     {name} -> tm_id={r['tm_id']} ({r['tm_name']})")


def cmd_compare(args: argparse.Namespace) -> None:
    db.init_db()
    with db.connect() as conn:
        player = db.get_player_by_name(conn, args.player)
        if not player or not player["scraped_at"]:
            print(f"'{args.player}' has not been scraped yet. Run `scrape --player \"{args.player}\"` first.", file=sys.stderr)
            sys.exit(1)
        frame = analysis.player_frame(conn, player)

    if frame.empty:
        print(f"No market value data for {args.player}", file=sys.stderr)
        sys.exit(1)

    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax1.plot(frame.index, frame["market_value_eur"] / 1e6, color="tab:blue", label="Transfermarkt value (EUR M)")
    ax1.set_ylabel("Transfermarkt market value (EUR M)", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.set_xlabel("Date")

    ax2 = ax1.twinx()
    ax2.plot(frame.index, frame["openelo"], color="tab:red", label="OpenELO")
    ax2.set_ylabel("OpenELO", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    plt.title(f"OpenELO vs Transfermarkt value — {args.player}")
    fig.tight_layout()
    _save_or_show(fig, args.out, default_name=f"{args.player.replace(' ', '_')}.png")


def cmd_average(args: argparse.Namespace) -> None:
    db.init_db()
    with db.connect() as conn:
        players = db.get_scraped_players(conn)
        if not players:
            print("No players scraped yet. Run `scrape` first.", file=sys.stderr)
            sys.exit(1)
        frame = analysis.average_frame(conn, players)

    if frame.empty:
        print("No market value data available across scraped players.", file=sys.stderr)
        sys.exit(1)

    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax1.plot(frame.index, frame["market_value_eur"] / 1e6, color="tab:blue", label="Avg Transfermarkt value (EUR M)")
    ax1.set_ylabel("Avg Transfermarkt market value (EUR M)", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.set_xlabel("Date")

    ax2 = ax1.twinx()
    ax2.plot(frame.index, frame["openelo"], color="tab:red", label="Avg OpenELO")
    ax2.set_ylabel("Avg OpenELO", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    plt.title(f"Average OpenELO vs Average Transfermarkt value ({len(players)} players)")
    fig.tight_layout()
    _save_or_show(fig, args.out, default_name="average.png")


def cmd_correlation(args: argparse.Namespace) -> None:
    db.init_db()
    with db.connect() as conn:
        if args.player:
            player = db.get_player_by_name(conn, args.player)
            if not player or not player["scraped_at"]:
                print(f"'{args.player}' has not been scraped yet.", file=sys.stderr)
                sys.exit(1)
            frame = analysis.player_frame(conn, player)
            label = args.player
        else:
            players = db.get_scraped_players(conn)
            if not players:
                print("No players scraped yet. Run `scrape` first.", file=sys.stderr)
                sys.exit(1)
            frame = analysis.average_frame(conn, players)
            label = f"average across {len(players)} players"

    if frame.empty:
        print("No data to correlate.", file=sys.stderr)
        sys.exit(1)

    cc = analysis.lagged_cross_correlation(
        frame["openelo"], frame["market_value_eur"], max_lag_months=args.max_lag
    )
    print(f"Lagged cross-correlation (OpenELO vs Transfermarkt value) for {label}:")
    print(cc.to_string(index=False))

    best = analysis.best_lag(cc)
    if best is None:
        print("\nNo valid correlation could be computed (insufficient overlapping data).")
        return

    lag, r = int(best["lag_months"]), best["pearson_r"]
    print(f"\nStrongest correlation at lag = {lag:+d} months, Pearson r = {r:.3f}")
    if lag == 0:
        print("No phase shift indicated: correlation peaks at zero lag.")
    elif lag > 0:
        print(
            f"Transfermarkt value appears to lag OpenELO by ~{lag} month(s) — "
            f"a phase shift forward by {lag} month(s) may improve alignment."
        )
    else:
        print(
            f"Transfermarkt value appears to lead OpenELO by ~{-lag} month(s) — "
            f"OpenELO may need to shift backward by {-lag} month(s), or the "
            f"model needs a faster-reacting term."
        )


def _save_or_show(fig, out: str | None, default_name: str) -> None:
    if out:
        path = Path(out)
    else:
        OUTPUTS_DIR.mkdir(exist_ok=True)
        path = OUTPUTS_DIR / default_name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    print(f"Saved graph to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="Scrape Transfermarkt market value history (once per player)")
    p_scrape.add_argument("--player", help="Only scrape this one player (must be in players.PLAYER_NAMES)")
    p_scrape.add_argument("--force", action="store_true", help="Re-scrape even if already cached")
    p_scrape.set_defaults(func=cmd_scrape)

    p_list = sub.add_parser("list", help="Show scrape status for the curated player list")
    p_list.set_defaults(func=cmd_list)

    p_compare = sub.add_parser("compare", help="Plot OpenELO vs Transfermarkt value for one player")
    p_compare.add_argument("player", help="Player name, must match players.PLAYER_NAMES")
    p_compare.add_argument("--out", help="Output PNG path (default outputs/<player>.png)")
    p_compare.set_defaults(func=cmd_compare)

    p_avg = sub.add_parser("average", help="Plot average OpenELO vs average Transfermarkt value across all scraped players")
    p_avg.add_argument("--out", help="Output PNG path (default outputs/average.png)")
    p_avg.set_defaults(func=cmd_average)

    p_corr = sub.add_parser("correlation", help="Lagged cross-correlation to check if a phase shift is needed")
    p_corr.add_argument("--player", help="Restrict to one player (default: average across all scraped players)")
    p_corr.add_argument("--max-lag", type=int, default=12, help="Max lag in months to test in each direction (default 12)")
    p_corr.set_defaults(func=cmd_correlation)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
