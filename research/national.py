"""National-team line-ups and results for 2012–26, added to the research store.

transfermarkt-datasets only has national-team line-ups from 2024 on. This adds,
from open sources on GitHub:

- StatsBomb open data: line-ups with exact minutes for Euro 2020 and 2024 and
  AFCON 2023 (World Cups 2018 and 2022 come from jfjelstul, below).
- jfjelstul/worldcup: squads, starters and substitutions for World Cups 2014,
  2018 and 2022, with birth dates (used to match players to Transfermarkt).
- martj42/international_results: every international result since 1872, for a
  national-team Elo that also sees qualifiers and friendlies.

Players are matched to Transfermarkt ids: by birth date and name for
jfjelstul, by name, citizenship and club activity for StatsBomb. Unmatched
players are left out and counted.

Everything goes into separate tables (nt_game, nt_lineup, nt_appearance,
nt_team, international_result) so the earlier checks, which read the game,
lineup and appearance tables, are unchanged. Only player_v2 reads these.

    .venv/bin/python -I national.py --fetch   # download (~15 MB), then build
    .venv/bin/python -I national.py           # build from the downloads

Imports nothing from this directory, so it runs in isolated mode (-I).
"""
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent / "data" / "raw"
STORE_PATH = ROOT / "openelo_research.sqlite3"
DL = ROOT / "downloads"
SB_DIR, JF_DIR, MJ_DIR = DL / "statsbomb", DL / "jfjelstul", DL / "martj42"

SB_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/{path}"
JF_URL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/{name}"
MJ_URL = "https://raw.githubusercontent.com/martj42/international_results/master/{name}"
JF_FILES = ["players.csv", "squads.csv", "matches.csv", "player_appearances.csv", "substitutions.csv"]
MJ_FILES = ["results.csv", "shootouts.csv"]

# (StatsBomb competition, season) -> (our competition id, season as the store numbers it, hosts)
SB_TOURNAMENTS = {
    (55, 43): ("EURO", 2020, set()),          # played across Europe: every match counts as neutral
    (55, 282): ("EURO", 2023, {"Germany"}),
    (1267, 107): ("AFCN", 2023, {"Ivory Coast"}),
}
JF_TOURNAMENTS = {"WC-2014": ("FIWC", 2013), "WC-2018": ("FIWC", 2017), "WC-2022": ("FIWC", 2021)}

# Source spellings -> the Transfermarkt national team name (our canonical name).
ALIASES = {
    "Turkey": "Türkiye", "South Korea": "Korea, South", "Korea Republic": "Korea, South",
    "Côte d'Ivoire": "Ivory Coast", "Congo DR": "Democratic Republic of the Congo",
    "DR Congo": "Democratic Republic of the Congo", "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Republic of Ireland": "Ireland", "Cape Verde Islands": "Cape Verde", "Hong Kong": "Hongkong",
    "Czechia": "Czech Republic", "North Korea": "North Korea", "Curacao": "Curaçao",
}
# Canonical name -> how Transfermarkt spells it as a player's citizenship, where it differs.
CITIZENSHIP = {
    "Ivory Coast": "Cote d'Ivoire", "Democratic Republic of the Congo": "DR Congo",
    "Curaçao": "Curacao", "Gambia": "The Gambia", "North Korea": "Korea, North",
}
SYNTHETIC_TEAM_BASE = 990_000      # team ids for national teams Transfermarkt does not list
SYNTHETIC_GAME_BASE = 900_000_000  # game ids for tournaments the store has no games for

SCHEMA = """
DROP TABLE IF EXISTS nt_team; DROP TABLE IF EXISTS nt_game; DROP TABLE IF EXISTS nt_lineup;
DROP TABLE IF EXISTS nt_appearance; DROP TABLE IF EXISTS international_result;
CREATE TABLE nt_team (team_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE nt_game (
    game_id INTEGER PRIMARY KEY, competition_id TEXT NOT NULL, season INTEGER NOT NULL,
    date TEXT NOT NULL, home_team_id INTEGER NOT NULL, away_team_id INTEGER NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL, neutral INTEGER NOT NULL,
    length INTEGER NOT NULL, source TEXT NOT NULL, in_store INTEGER NOT NULL
);
CREATE TABLE nt_lineup (
    game_id INTEGER NOT NULL, player_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
    starter INTEGER NOT NULL, PRIMARY KEY (game_id, player_id)
);
CREATE TABLE nt_appearance (
    game_id INTEGER NOT NULL, player_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
    minutes INTEGER NOT NULL, PRIMARY KEY (game_id, player_id)
);
CREATE TABLE international_result (
    date TEXT NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL, home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL, tournament TEXT NOT NULL, neutral INTEGER NOT NULL
);
"""


# ---------------------------------------------------------------- download

def fetch() -> None:
    for (competition, season) in SB_TOURNAMENTS:
        download(SB_URL.format(path=f"matches/{competition}/{season}.json"),
                 SB_DIR / "matches" / f"{competition}_{season}.json")
    ids = [m["match_id"] for (c, s) in SB_TOURNAMENTS for m in sb_matches(c, s)]
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(lambda i: download(SB_URL.format(path=f"lineups/{i}.json"),
                                         SB_DIR / "lineups" / f"{i}.json", quiet=True), ids))
    for name in JF_FILES:
        download(JF_URL.format(name=name), JF_DIR / name)
    for name in MJ_FILES:
        download(MJ_URL.format(name=name), MJ_DIR / name)


def download(url: str, target: Path, quiet: bool = False) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "openelo-research/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response, open(partial, "wb") as out:
        out.write(response.read())
    partial.rename(target)
    if not quiet:
        print(f"[ok] {target.name}")


def sb_matches(competition: int, season: int) -> list:
    return json.loads((SB_DIR / "matches" / f"{competition}_{season}.json").read_text())


# ---------------------------------------------------------------- names

def canonical(country: str) -> str:
    return ALIASES.get(country, country)


def normalise(name: str) -> str:
    name = name.lower()
    for a, b in (("ø", "o"), ("ß", "ss"), ("ł", "l"), ("đ", "d"), ("æ", "ae"), ("ı", "i"), ("œ", "oe")):
        name = name.replace(a, b)
    name = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z ]", " ", name).split())


class PlayerIndex:
    """Transfermarkt players, for matching national-team line-ups to their ids."""

    def __init__(self, conn: sqlite3.Connection):
        players = pd.read_sql("SELECT player_id, name, date_of_birth, citizenship FROM player", conn)
        players = players.dropna(subset=["name"])
        players["norm"] = players.name.map(normalise)
        players["tokens"] = players.norm.str.split().map(frozenset)
        self.players = players
        active = pd.read_sql("""
            SELECT a.player_id, MIN(g.date) first, MAX(g.date) last
            FROM appearance a JOIN game g USING (game_id) WHERE g.national = 0 GROUP BY a.player_id
        """, conn)
        self.active = {r.player_id: (r.first, r.last) for r in active.itertuples()}
        self.by_dob = {d: g for d, g in players.groupby("date_of_birth")}
        self.by_citizenship = {c: g for c, g in players.groupby("citizenship")}

    def is_active(self, player_id: int, date: str) -> bool:
        span = self.active.get(player_id)
        if span is None:
            return False
        lo = (pd.Timestamp(date) - pd.Timedelta(days=540)).strftime("%Y-%m-%d")
        hi = (pd.Timestamp(date) + pd.Timedelta(days=540)).strftime("%Y-%m-%d")
        return span[0] <= hi and span[1] >= lo

    def by_birth(self, dob: str, given: str, family: str, nation: str):
        """jfjelstul: same birth date, and a name token in common (or the only one
        of his citizenship born that day)."""
        cands = self.by_dob.get(dob)
        if cands is None or not isinstance(dob, str):
            return None
        names = set(normalise(f"{given} {family}").split())
        named = cands[cands.tokens.map(lambda t: bool(t & names))]
        if len(named) == 1:
            return int(named.player_id.iloc[0])
        citizens = cands[cands.citizenship == CITIZENSHIP.get(nation, nation)]
        pick = named[named.citizenship == CITIZENSHIP.get(nation, nation)] if len(named) > 1 else citizens
        return int(pick.player_id.iloc[0]) if len(pick) == 1 else None

    def by_name(self, name: str, nickname, nation: str, date: str):
        """StatsBomb: the best name tier among active players of his citizenship;
        if none, among all active players (dual nationals), exact names only."""
        full = normalise(name)
        tokens = set(full.split())
        nick = normalise(nickname) if nickname else None
        first, last = full.split()[0], full.split()[-1]

        def tier(row) -> int:
            if row.norm == full or (nick and row.norm == nick):
                return 1
            if len(row.tokens) >= 2 and row.tokens <= tokens:
                return 2
            parts = row.norm.split()
            if len(parts) >= 2 and parts[-1] == last and parts[0][0] == first[0]:
                return 3
            return 9

        pools = [self.by_citizenship.get(CITIZENSHIP.get(nation, nation)), self.players]
        for depth, pool in enumerate(pools):
            if pool is None:
                continue
            pool = pool[pool.player_id.map(lambda p: self.is_active(p, date))]
            if pool.empty:
                continue
            tiers = pool.apply(tier, axis=1)
            best = tiers.min()
            if best == 9 or (depth == 1 and best > 1):
                continue
            hits = pool[tiers == best]
            if len(hits) == 1:
                return int(hits.player_id.iloc[0])
        return None


# ---------------------------------------------------------------- sources

def clock(text: str) -> float:
    minutes, seconds = text.split(":")
    return int(minutes) + int(seconds) / 60


def statsbomb_games():
    """(game dict, [(player name, nickname, starter, minutes)] per team name)."""
    for (competition, season), (comp_id, store_season, hosts) in SB_TOURNAMENTS.items():
        for m in sb_matches(competition, season):
            lineups = json.loads((SB_DIR / "lineups" / f"{m['match_id']}.json").read_text())
            extra = any((p.get("to_period") or 0) >= 3 or p["from_period"] >= 3
                        for team in lineups for pl in team["lineup"] for p in pl["positions"])
            length = 120 if extra else 90
            home, away = canonical(m["home_team"]["home_team_name"]), canonical(m["away_team"]["away_team_name"])
            game = {"source_id": m["match_id"], "competition_id": comp_id, "season": store_season,
                    "date": m["match_date"], "home": home, "away": away,
                    "home_goals": m["home_score"], "away_goals": m["away_score"],
                    "neutral": int(home not in hosts), "length": length, "source": "statsbomb"}
            squads = {}
            for team in lineups:
                rows = []
                for pl in team["lineup"]:
                    spells = pl["positions"]
                    starter = int(bool(spells) and spells[0]["start_reason"] == "Starting XI")
                    played = 0.0
                    for s in spells:
                        start = clock(s["from"])
                        end = clock(s["to"]) if s["to"] else length + 6
                        played += max(0.0, end - start)
                    rows.append((pl["player_name"], pl.get("player_nickname"), starter,
                                 int(round(min(played, length)))))
                squads[canonical(team["team_name"])] = rows
            yield game, squads


def jfjelstul_games():
    """(game dict, [(jf player id, starter, minutes)] per team name) for WC 2014–22.
    Every squad member is listed for every match of his team; minutes come from
    starters and substitutions."""
    matches = pd.read_csv(JF_DIR / "matches.csv")
    squads = pd.read_csv(JF_DIR / "squads.csv")
    apps = pd.read_csv(JF_DIR / "player_appearances.csv")
    subs = pd.read_csv(JF_DIR / "substitutions.csv")
    for tid, (comp_id, store_season) in JF_TOURNAMENTS.items():
        for m in matches[matches.tournament_id == tid].itertuples():
            length = 120 if m.extra_time else 90
            game = {"source_id": m.match_id, "competition_id": comp_id, "season": store_season,
                    "date": m.match_date, "home": canonical(m.home_team_name), "away": canonical(m.away_team_name),
                    "home_goals": m.home_team_score, "away_goals": m.away_team_score,
                    "neutral": 1, "length": length, "source": "jfjelstul"}
            a = apps[apps.match_id == m.match_id]
            s = subs[subs.match_id == m.match_id]
            off = dict(zip(s[s.going_off == 1].player_id, s[s.going_off == 1].minute_regulation))
            on = dict(zip(s[s.coming_on == 1].player_id, s[s.coming_on == 1].minute_regulation))
            result = {}
            for team_name in (m.home_team_name, m.away_team_name):
                squad = squads[(squads.tournament_id == tid) & (squads.team_name == team_name)]
                ta = a[a.team_name == team_name]
                starters = set(ta[ta.starter == 1].player_id)
                rows = []
                for pid in squad.player_id:
                    if pid in starters:
                        minutes = off.get(pid, length)
                    elif pid in on:
                        minutes = off.get(pid, length) - on[pid]
                    else:
                        minutes = 0
                    rows.append((pid, int(pid in starters), int(max(0, min(minutes, length)))))
                result[canonical(team_name)] = rows
            yield game, result


# ---------------------------------------------------------------- build

def build() -> None:
    conn = sqlite3.connect(STORE_PATH)
    conn.executescript(SCHEMA)
    team_ids = dict(pd.read_sql("SELECT name, team_id FROM team WHERE kind = 'national'", conn).values)
    synthetic = {}

    def team_id(name: str) -> int:
        if name in team_ids:
            return int(team_ids[name])
        if name not in synthetic:
            synthetic[name] = SYNTHETIC_TEAM_BASE + len(synthetic)
        return synthetic[name]

    existing = pd.read_sql("SELECT game_id, date, home_team_id, away_team_id FROM game WHERE national = 1", conn)
    existing_key = {}
    for g in existing.itertuples():
        existing_key[(g.date, frozenset((g.home_team_id, g.away_team_id)))] = g.game_id

    def store_game(date: str, home: int, away: int):
        for shift in (0, -1, 1):
            d = (pd.Timestamp(date) + pd.Timedelta(days=shift)).strftime("%Y-%m-%d")
            hit = existing_key.get((d, frozenset((home, away))))
            if hit is not None:
                return int(hit)
        return None

    index = PlayerIndex(conn)
    jf_players = pd.read_csv(JF_DIR / "players.csv").set_index("player_id")
    games, lineups, appearances, stats = [], [], [], {}

    def add(game, squads, resolve):
        home, away = team_id(game["home"]), team_id(game["away"])
        in_store = store_game(game["date"], home, away)
        gid = in_store if in_store is not None else SYNTHETIC_GAME_BASE + len(games)
        games.append((gid, game["competition_id"], game["season"], game["date"], home, away,
                      int(game["home_goals"]), int(game["away_goals"]), game["neutral"], game["length"],
                      game["source"], int(in_store is not None)))
        st = stats.setdefault((game["source"], game["competition_id"], game["season"]), [0, 0, 0, 0])
        st[0] += 1
        st[1] += in_store is not None
        for name, rows in squads.items():
            tid = team_id(name)
            seen = set()
            for row in rows:
                pid = resolve(row, name, game["date"])
                st[2] += 1
                if pid is None or pid in seen:
                    continue
                seen.add(pid)
                st[3] += 1
                starter, minutes = row[-2], row[-1]
                lineups.append((gid, pid, tid, starter))
                if minutes > 0:
                    appearances.append((gid, pid, tid, minutes))

    cache = {}

    def resolve_jf(row, nation, date):
        jid = row[0]
        if jid not in cache:
            p = jf_players.loc[jid]
            cache[jid] = index.by_birth(p.birth_date, str(p.given_name), str(p.family_name), nation)
        return cache[jid]

    def resolve_sb(row, nation, date):
        key = (row[0], nation, date[:4])
        if key not in cache:
            cache[key] = index.by_name(row[0], row[1], nation, date)
        return cache[key]

    for game, squads in jfjelstul_games():
        add(game, squads, resolve_jf)
    for game, squads in statsbomb_games():
        add(game, squads, resolve_sb)

    conn.executemany("INSERT INTO nt_team VALUES (?, ?)", [(i, n) for n, i in synthetic.items()])
    conn.executemany("INSERT INTO nt_game VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", games)
    conn.executemany("INSERT INTO nt_lineup VALUES (?,?,?,?)", lineups)
    conn.executemany("INSERT INTO nt_appearance VALUES (?,?,?,?)", appearances)

    results = pd.read_csv(MJ_DIR / "results.csv").dropna(subset=["home_score", "away_score"])
    conn.executemany("INSERT INTO international_result VALUES (?,?,?,?,?,?,?)", [
        (r.date, canonical(r.home_team), canonical(r.away_team), int(r.home_score), int(r.away_score),
         r.tournament, int(str(r.neutral).upper() == "TRUE")) for r in results.itertuples()])
    conn.commit()

    print("source      tournament  games  matched to store  listed  players matched")
    for (source, comp, season), (n, matched, listed, ok) in stats.items():
        print(f"{source:<11} {comp} {season}   {n:>5}  {matched:>16}  {listed:>6}  {ok:>6} ({ok / listed:.0%})")
    print(f"international results: {len(results)}, synthetic teams: {sorted(synthetic)}")
    conn.close()


if __name__ == "__main__":
    if not STORE_PATH.exists():
        sys.exit(f"{STORE_PATH} is missing. Run `.venv/bin/python -I ingest.py --fetch` first.")
    if "--fetch" in sys.argv:
        fetch()
    build()
