"""Builds the research store from downloaded raw data (fetch once, read forever).

Sources, all static and offline (Spec §5):

- transfermarkt-datasets (github.com/dcaribou/transfermarkt-datasets, CC0):
  games, minutes, lineups, players, market values and transfers, 2012/13 to
  2025/26, scraped from Transfermarkt.
- Club-Football-Match-Data (github.com/xgabora/Club-Football-Match-Data, MIT):
  football-data.co.uk results with corners, cards and bookmaker odds, and
  clubelo.com rating snapshots. Used only as references and for the tier-2
  test, never as rating inputs.

Raw files are untrusted input: they are parsed as data and never executed.
This script imports nothing from this directory, so it runs in isolated mode:

    .venv/bin/python -I ingest.py --fetch
"""

import argparse
import re
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
DOWNLOADS = RAW_DIR / "downloads"
STORE_PATH = RAW_DIR / "openelo_research.sqlite3"

TMD_DIR = DOWNLOADS / "transfermarkt-datasets"
TMD_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/{table}.csv.gz"
TMD_TABLES = [
    "competitions", "clubs", "national_teams", "players", "games", "game_events",
    "appearances", "game_lineups", "player_valuations", "transfers",
]

CFMD_DIR = DOWNLOADS / "club-football-match-data"
CFMD_URL = "https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data/main/data/{name}"
CFMD_FILES = ["Matches.csv", "EloRatings.csv"]

FIRST_SEASON_START = "2012-07-01"

# The mirror's own note: its rating snapshots after this date are its author's
# continuation, not clubelo's.
CLUBELO_LAST_GENUINE = "2025-06-01"

# football-data.co.uk division -> transfermarkt-datasets competition
DIVISION_TO_COMPETITION = {
    "E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1", "N1": "NL1",
    "P1": "PO1", "B1": "BE1", "T1": "TR1", "G1": "GR1", "SC0": "SC1", "RUS": "RU1",
    "DEN": "DK1", "AUT": "A1", "SUI": "C1", "POL": "PL1", "ROM": "RO1", "SWE": "SE1",
    "NOR": "NO1", "ARG": "ARG1", "BRA": "BRA1", "MEX": "MEX1", "USA": "MLS1", "JAP": "JAP1",
}

NATIONAL_TEAM_COMPETITIONS = {"FIWC", "EURO", "COPA", "AFAC", "AFCN"}

# Host nations play at home; every other national-team tournament match is neutral.
TOURNAMENT_HOSTS = {
    ("FIWC", 2005): {"Germany"}, ("FIWC", 2009): {"South Africa"}, ("FIWC", 2013): {"Brazil"},
    ("FIWC", 2017): {"Russia"}, ("FIWC", 2021): {"Qatar"},
    ("FIWC", 2025): {"United States", "Mexico", "Canada"},
    ("EURO", 2007): {"Austria", "Switzerland"}, ("EURO", 2011): {"Poland", "Ukraine"},
    ("EURO", 2015): {"France"}, ("EURO", 2023): {"Germany"},
    ("COPA", 2025): {"United States"}, ("AFAC", 2024): {"Qatar"}, ("AFCN", 2025): {"Morocco"},
}

SCHEMA = """
CREATE TABLE competition (
    competition_id TEXT PRIMARY KEY, name TEXT, type TEXT, sub_type TEXT, country TEXT
);
CREATE TABLE team (
    team_id INTEGER PRIMARY KEY, name TEXT, kind TEXT NOT NULL, domestic_competition_id TEXT
);
CREATE TABLE game (
    game_id INTEGER PRIMARY KEY, competition_id TEXT NOT NULL, season INTEGER NOT NULL,
    round TEXT, date TEXT NOT NULL, home_team_id INTEGER NOT NULL, away_team_id INTEGER NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL, goal_difference INTEGER NOT NULL,
    shootout INTEGER NOT NULL,
    stage TEXT NOT NULL, leg INTEGER NOT NULL, first_leg_game_id INTEGER, neutral INTEGER NOT NULL,
    national INTEGER NOT NULL, data_issue TEXT
);
CREATE TABLE appearance (
    game_id INTEGER NOT NULL, player_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
    minutes INTEGER NOT NULL, goals INTEGER NOT NULL, yellow INTEGER NOT NULL, red INTEGER NOT NULL,
    assists INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, player_id)
);
CREATE TABLE lineup (
    game_id INTEGER NOT NULL, player_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
    starter INTEGER NOT NULL, position TEXT, PRIMARY KEY (game_id, player_id)
);
CREATE TABLE player (
    player_id INTEGER PRIMARY KEY, name TEXT, position TEXT, sub_position TEXT,
    date_of_birth TEXT, citizenship TEXT
);
CREATE TABLE valuation (
    player_id INTEGER NOT NULL, date TEXT NOT NULL, value_eur INTEGER NOT NULL, team_id INTEGER,
    PRIMARY KEY (player_id, date)
);
CREATE TABLE transfer (
    player_id INTEGER NOT NULL, date TEXT NOT NULL, from_team_id INTEGER, to_team_id INTEGER,
    fee_eur INTEGER, market_value_eur INTEGER
);
CREATE TABLE match_stats (
    game_id INTEGER PRIMARY KEY, home_corners INTEGER, away_corners INTEGER,
    home_yellow INTEGER, away_yellow INTEGER, home_red INTEGER, away_red INTEGER,
    odd_home REAL, odd_draw REAL, odd_away REAL
);
CREATE TABLE clubelo (
    date TEXT NOT NULL, team_id INTEGER NOT NULL, elo REAL NOT NULL, PRIMARY KEY (date, team_id)
);
CREATE INDEX appearance_player ON appearance (player_id);
CREATE INDEX lineup_player ON lineup (player_id);
CREATE INDEX valuation_player ON valuation (player_id);
"""


def fetch() -> None:
    for table in TMD_TABLES:
        download(TMD_URL.format(table=table), TMD_DIR / f"{table}.csv.gz")
    for name in CFMD_FILES:
        download(CFMD_URL.format(name=name), CFMD_DIR / name)


def download(url: str, target: Path) -> None:
    if target.exists():
        print(f"[skip] {target.name} already downloaded")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    # The dataset host (Cloudflare) refuses urllib's default User-Agent.
    request = urllib.request.Request(url, headers={"User-Agent": "openelo-research/1.0"})
    with urllib.request.urlopen(request, timeout=600) as response, open(partial, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    partial.rename(target)
    print(f"[ok] {target.name}")


def build() -> None:
    STORE_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(STORE_PATH)
    conn.executescript(SCHEMA)

    competitions = load_competitions()
    teams = load_teams()
    games = load_games(competitions, teams)
    write(conn, "competition", competitions)
    write(conn, "team", teams)
    write(conn, "game", games)
    write(conn, "appearance", load_appearances(games))
    write(conn, "lineup", load_lineups(games))
    write(conn, "player", load_players())
    write(conn, "valuation", load_valuations())
    write(conn, "transfer", load_transfers())

    mirror = load_mirror_matches()
    names = map_mirror_team_names(mirror, games)
    write(conn, "match_stats", match_stats(mirror, names, games))
    write(conn, "clubelo", load_clubelo(names))
    conn.commit()
    report(conn)
    conn.close()


def write(conn: sqlite3.Connection, table: str, frame: pd.DataFrame) -> None:
    frame.to_sql(table, conn, if_exists="append", index=False)
    print(f"{table}: {len(frame)} rows")


def load_competitions() -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "competitions.csv.gz")
    return pd.DataFrame({
        "competition_id": raw.competition_id, "name": raw["name"], "type": raw["type"],
        "sub_type": raw.sub_type, "country": raw.country_name,
    })


def load_teams() -> pd.DataFrame:
    clubs = pd.read_csv(TMD_DIR / "clubs.csv.gz")
    nations = pd.read_csv(TMD_DIR / "national_teams.csv.gz")
    games = pd.read_csv(TMD_DIR / "games.csv.gz", usecols=[
        "home_club_id", "away_club_id", "home_club_name", "away_club_name", "competition_id"])
    named = pd.concat([
        pd.DataFrame({"team_id": clubs.club_id, "name": clubs["name"],
                      "domestic_competition_id": clubs.domestic_competition_id}),
        pd.DataFrame({"team_id": nations.national_team_id, "name": nations["name"],
                      "domestic_competition_id": None}),
    ]).drop_duplicates("team_id")
    national_ids = set(games.loc[games.competition_id.isin(NATIONAL_TEAM_COMPETITIONS), "home_club_id"]) | set(
        games.loc[games.competition_id.isin(NATIONAL_TEAM_COMPETITIONS), "away_club_id"])
    from_games = pd.concat([
        games[["home_club_id", "home_club_name"]].set_axis(["team_id", "name"], axis=1),
        games[["away_club_id", "away_club_name"]].set_axis(["team_id", "name"], axis=1),
    ]).dropna().drop_duplicates("team_id")
    missing = from_games[~from_games.team_id.isin(named.team_id)].assign(domestic_competition_id=None)
    teams = pd.concat([named, missing], ignore_index=True)
    teams["kind"] = ["national" if t in national_ids else "club" for t in teams.team_id]
    return teams[["team_id", "name", "kind", "domestic_competition_id"]]


def load_games(competitions: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "games.csv.gz")
    raw = raw[raw.date >= FIRST_SEASON_START].copy()
    raw = raw.merge(competitions[["competition_id", "type", "sub_type"]], on="competition_id", how="left")
    raw = remove_shootout_goals(raw)
    raw["national"] = raw.competition_id.isin(NATIONAL_TEAM_COMPETITIONS).astype(int)
    raw["stage"] = [stage_of(c, t, r) for c, t, r in zip(raw.competition_id, raw["type"], raw["round"])]
    raw = pair_legs(raw)
    raw["neutral"] = neutral_venues(raw, teams)
    raw["goal_difference"] = result_goal_difference(raw)
    raw["data_issue"] = None
    corrected_difference = raw.home_goals - raw.away_goals
    raw.loc[(raw.shootout == 1) & (corrected_difference != raw.goal_difference), "data_issue"] = "incomplete_shootout_events"
    duplicates = duplicate_team_days(raw)
    raw.loc[raw.game_id.isin(duplicates), "data_issue"] = "team_plays_twice_same_day"
    return raw.rename(columns={"home_club_id": "home_team_id", "away_club_id": "away_team_id"})[[
        "game_id", "competition_id", "season", "round", "date", "home_team_id", "away_team_id",
        "home_goals", "away_goals", "goal_difference", "shootout", "stage", "leg", "first_leg_game_id",
        "neutral", "national", "data_issue",
    ]]


def remove_shootout_goals(games: pd.DataFrame) -> pd.DataFrame:
    """The dataset adds scored shoot-out kicks to the match score (a 0-0 won 5-3 on
    penalties is stored as 5:3). The score after extra time is the score less them."""
    events = pd.read_csv(TMD_DIR / "game_events.csv.gz", usecols=["game_id", "type", "club_id", "description"])
    kicks = events[events["type"] == "Shootout"]
    scored = kicks[kicks.description.fillna("").str.contains("Scored")]
    scored_by_club = scored.groupby(["game_id", "club_id"]).size()
    games = games.copy()
    games["shootout"] = games.game_id.isin(kicks.game_id).astype(int)
    home_kicks = [scored_by_club.get((g, h), 0) for g, h in zip(games.game_id, games.home_club_id)]
    away_kicks = [scored_by_club.get((g, a), 0) for g, a in zip(games.game_id, games.away_club_id)]
    games["home_goals"] = games.home_club_goals - pd.Series(home_kicks, index=games.index)
    games["away_goals"] = games.away_club_goals - pd.Series(away_kicks, index=games.index)
    return games


def result_goal_difference(games: pd.DataFrame) -> pd.Series:
    """Home minus away goals after extra time; a shoot-out never counts. A single match
    that went to penalties was level. A second leg that went to penalties levelled the
    aggregate, so its difference mirrors the first leg's. Shoot-out events are sometimes
    incomplete, so neither case trusts the corrected goals."""
    by_id = games.set_index("game_id")
    difference = games.home_goals - games.away_goals
    single_shootout = (games.shootout == 1) & (games.leg != 2)
    difference[single_shootout] = 0
    second_leg_shootout = games[(games.shootout == 1) & (games.leg == 2)]
    for index, first_leg_id in zip(second_leg_shootout.index, second_leg_shootout.first_leg_game_id):
        first_leg = by_id.loc[int(first_leg_id)]
        difference[index] = first_leg.home_goals - first_leg.away_goals
    return difference.astype(int)


def stage_of(competition_id: str, competition_type: str, round_name: str) -> str:
    """Competition stage, the input to match importance."""
    name = (round_name or "").lower()
    if competition_id in NATIONAL_TEAM_COMPETITIONS:
        return "national_knockout" if not is_group_round(name) else "national_group"
    if competition_type == "domestic_league" or competition_id in {"BPO4", "EJPL", "POBE"}:
        return "league"
    if competition_id == "KLUB":
        return "club_world_cup"
    if competition_id in {"USC", "BESC", "DFL", "FRCH", "GBCS", "NLSC", "POSU", "RUSS", "SCI", "SUC", "UKRS"}:
        return "super_cup"
    if competition_id in {"CLQ", "ELQ", "ECLQ"}:
        return "continental_qualifying"
    if competition_id in {"CL", "EL", "UCOL"}:
        if name == "final":
            return "continental_final"
        return "continental_group" if is_group_round(name) else "continental_knockout"
    if "semi" in name or name == "final":
        return "cup_late"
    return "cup_early"


def is_group_round(name: str) -> bool:
    return name.startswith("group") or "league phase" in name or "matchday" in name


LEG_PATTERN = re.compile(r"\s*(1st|2nd)\s+leg\s*", re.IGNORECASE)


def pair_legs(games: pd.DataFrame) -> pd.DataFrame:
    """Second legs know their first leg, which carries the aggregate the tie stands at."""
    games = games.copy()
    leg_token = games["round"].fillna("").str.extract(LEG_PATTERN, expand=False).str.lower()
    games["leg"] = leg_token.map({"1st": 1, "2nd": 2}).fillna(0).astype(int)
    games["tie_round"] = games["round"].fillna("").str.replace(LEG_PATTERN, " ", regex=True).str.strip().str.lower()
    firsts = games[games.leg == 1][["competition_id", "season", "tie_round", "home_club_id", "away_club_id", "game_id"]]
    firsts = firsts.rename(columns={"home_club_id": "away_club_id", "away_club_id": "home_club_id",
                                    "game_id": "first_leg_game_id"})
    games = games.merge(firsts, on=["competition_id", "season", "tie_round", "home_club_id", "away_club_id"], how="left")
    games.loc[games.leg != 2, "first_leg_game_id"] = None
    games.loc[(games.leg == 2) & games.first_leg_game_id.isna(), "leg"] = 0
    games["first_leg_game_id"] = games.first_leg_game_id.astype("Int64")
    return games.drop(columns="tie_round")


def neutral_venues(games: pd.DataFrame, teams: pd.DataFrame) -> pd.Series:
    """League matches are played at the home club's chosen ground. Any other club match
    is neutral when its stadium is none of the grounds the home club used for league
    home games that season (finals, single-venue rounds). National-team tournament
    matches are neutral unless the home side is a host nation."""
    league = games[(games.stage == "league") & games.stadium.notna()]
    grounds = league.groupby(["home_club_id", "season"]).stadium.agg(set).to_dict()
    name_of = dict(zip(teams.team_id, teams["name"]))
    neutral = []
    for row in games.itertuples():
        if row.national:
            hosts = TOURNAMENT_HOSTS.get((row.competition_id, row.season), set())
            neutral.append(int(name_of.get(row.home_club_id) not in hosts))
            continue
        home_grounds = grounds.get((row.home_club_id, row.season))
        if row.stage == "league" or pd.isna(row.stadium) or home_grounds is None:
            neutral.append(0)
        else:
            neutral.append(int(row.stadium not in home_grounds))
    return pd.Series(neutral, index=games.index)


def duplicate_team_days(games: pd.DataFrame) -> set:
    sides = pd.concat([
        games[["game_id", "date", "home_club_id"]].set_axis(["game_id", "date", "team_id"], axis=1),
        games[["game_id", "date", "away_club_id"]].set_axis(["game_id", "date", "team_id"], axis=1),
    ])
    counts = sides.groupby(["date", "team_id"]).game_id.transform("size")
    return set(sides.loc[counts > 1, "game_id"])


def load_appearances(games: pd.DataFrame) -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "appearances.csv.gz", usecols=[
        "game_id", "player_id", "player_club_id", "minutes_played", "goals", "assists", "yellow_cards", "red_cards"])
    raw = raw[raw.game_id.isin(games.game_id)].drop_duplicates(["game_id", "player_id"])
    return pd.DataFrame({
        "game_id": raw.game_id, "player_id": raw.player_id, "team_id": raw.player_club_id,
        "minutes": raw.minutes_played, "goals": raw.goals, "yellow": raw.yellow_cards, "red": raw.red_cards,
        "assists": raw.assists,
    })


def load_lineups(games: pd.DataFrame) -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "game_lineups.csv.gz", usecols=["game_id", "player_id", "club_id", "type", "position"])
    raw = raw[raw.game_id.isin(games.game_id)].drop_duplicates(["game_id", "player_id"])
    return pd.DataFrame({
        "game_id": raw.game_id, "player_id": raw.player_id, "team_id": raw.club_id,
        "starter": (raw["type"] == "starting_lineup").astype(int), "position": raw.position,
    })


def load_players() -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "players.csv.gz")
    return pd.DataFrame({
        "player_id": raw.player_id, "name": raw["name"], "position": raw.position,
        "sub_position": raw.sub_position, "date_of_birth": raw.date_of_birth.str[:10],
        "citizenship": raw.country_of_citizenship,
    })


def load_valuations() -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "player_valuations.csv.gz").dropna(subset=["market_value_in_eur"])
    raw = raw.drop_duplicates(["player_id", "date"])
    return pd.DataFrame({
        "player_id": raw.player_id, "date": raw.date.str[:10],
        "value_eur": raw.market_value_in_eur.astype("int64"), "team_id": raw.current_club_id,
    })


def load_transfers() -> pd.DataFrame:
    raw = pd.read_csv(TMD_DIR / "transfers.csv.gz")
    return pd.DataFrame({
        "player_id": raw.player_id, "date": raw.transfer_date.str[:10], "from_team_id": raw.from_club_id,
        "to_team_id": raw.to_club_id, "fee_eur": raw.transfer_fee.astype("Int64"),
        "market_value_eur": raw.market_value_in_eur.astype("Int64"),
    })


def load_mirror_matches() -> pd.DataFrame:
    raw = pd.read_csv(CFMD_DIR / "Matches.csv", low_memory=False)
    raw = raw[raw.Division.isin(DIVISION_TO_COMPETITION) & (raw.MatchDate >= FIRST_SEASON_START)].copy()
    raw["competition_id"] = raw.Division.map(DIVISION_TO_COMPETITION)
    return raw.dropna(subset=["FTHome", "FTAway"])


def map_mirror_team_names(mirror: pd.DataFrame, games: pd.DataFrame) -> dict:
    """Mirror team names -> dataset team ids, voted by matches with the same
    competition, date (±1 day) and score."""
    keyed = games[["competition_id", "date", "home_goals", "away_goals", "home_team_id", "away_team_id"]].copy()
    candidates = []
    for shift in (-1, 0, 1):
        shifted = mirror.copy()
        shifted["date"] = (pd.to_datetime(shifted.MatchDate) + pd.Timedelta(days=shift)).dt.strftime("%Y-%m-%d")
        shifted["home_goals"] = shifted.FTHome.astype(int)
        shifted["away_goals"] = shifted.FTAway.astype(int)
        candidates.append(shifted.merge(keyed, on=["competition_id", "date", "home_goals", "away_goals"]))
    joined = pd.concat(candidates)
    votes = pd.concat([
        joined[["competition_id", "HomeTeam", "home_team_id"]].set_axis(["competition_id", "name", "team_id"], axis=1),
        joined[["competition_id", "AwayTeam", "away_team_id"]].set_axis(["competition_id", "name", "team_id"], axis=1),
    ])
    tally = votes.groupby(["competition_id", "name", "team_id"]).size().rename("votes").reset_index()
    best = tally.sort_values("votes", ascending=False).drop_duplicates(["competition_id", "name"])
    return {(c, n): t for c, n, t in zip(best.competition_id, best["name"], best.team_id)}


def match_stats(mirror: pd.DataFrame, names: dict, games: pd.DataFrame) -> pd.DataFrame:
    mirror = mirror.copy()
    mirror["home_team_id"] = [names.get((c, n)) for c, n in zip(mirror.competition_id, mirror.HomeTeam)]
    mirror["away_team_id"] = [names.get((c, n)) for c, n in zip(mirror.competition_id, mirror.AwayTeam)]
    mirror = mirror.dropna(subset=["home_team_id", "away_team_id"])
    keyed = games[["game_id", "competition_id", "date", "home_team_id", "away_team_id"]]
    found = []
    for shift in (0, -1, 1):
        shifted = mirror.copy()
        shifted["date"] = (pd.to_datetime(shifted.MatchDate) + pd.Timedelta(days=shift)).dt.strftime("%Y-%m-%d")
        found.append(shifted.merge(keyed, on=["competition_id", "date", "home_team_id", "away_team_id"]))
    joined = pd.concat(found).drop_duplicates("game_id")
    return pd.DataFrame({
        "game_id": joined.game_id, "home_corners": joined.HomeCorners, "away_corners": joined.AwayCorners,
        "home_yellow": joined.HomeYellow, "away_yellow": joined.AwayYellow, "home_red": joined.HomeRed,
        "away_red": joined.AwayRed, "odd_home": joined.OddHome, "odd_draw": joined.OddDraw,
        "odd_away": joined.OddAway,
    })


def load_clubelo(names: dict) -> pd.DataFrame:
    raw = pd.read_csv(CFMD_DIR / "EloRatings.csv")
    raw = raw[(raw.date >= "2012-01-01") & (raw.date <= CLUBELO_LAST_GENUINE)]
    by_name = {}
    for (_, name), team_id in names.items():
        by_name.setdefault(name, team_id)
    raw = raw.assign(team_id=raw.club.map(by_name)).dropna(subset=["team_id"])
    raw = raw.drop_duplicates(["date", "team_id"])
    return pd.DataFrame({"date": raw.date, "team_id": raw.team_id.astype(int), "elo": raw.elo})


def report(conn: sqlite3.Connection) -> None:
    for sql in [
        "SELECT data_issue, COUNT(*) FROM game GROUP BY data_issue",
        "SELECT stage, COUNT(*) FROM game GROUP BY stage ORDER BY 2 DESC",
        "SELECT leg, COUNT(*) FROM game GROUP BY leg",
        "SELECT SUM(neutral), SUM(shootout), COUNT(*) FROM game",
        "SELECT COUNT(*) FROM match_stats WHERE home_corners IS NOT NULL",
        "SELECT COUNT(DISTINCT team_id), MIN(date), MAX(date) FROM clubelo",
    ]:
        print(sql, "->", conn.execute(sql).fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fetch", action="store_true", help="download any raw file that is missing first")
    args = parser.parse_args()
    if args.fetch:
        fetch()
    build()


if __name__ == "__main__":
    main()
