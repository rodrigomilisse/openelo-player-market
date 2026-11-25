"""Recent Transfermarkt match data, scraped for research use only.

The third-party dataset (transfermarkt-datasets, see ingest.py) stops at 6 July 2026.
This scrapes what came after, from transfermarkt.com, into CSV files shaped like that
dataset's, which ingest.py then loads after the main dataset (the main dataset wins on
any game id it also has).

RESEARCH USE ONLY. Spec §5 and ADR-0017 keep scraped data out of the production path;
the owner overrode that for research (docs/briefs/transfermarkt-recent-scrape.md). The
output lives under data/raw/ (gitignored) and ends up in Postgres schema `research`.
No service may import this module.

Pages, all fetched politely and cached (tm_fetch.py):

- schedule  /{slug}/gesamtspielplan/{kind}/{COMP}/saison_id/{YEAR}: finished game ids and dates.
            Schedules change as matches are played, so they are cached per day.
- report    /spielbericht/index/spielbericht/{id}: teams, score, round, venue, line-ups,
            goals, substitutions, cards, shoot-out. A finished match is final: never refetched.
- player    /-/profil/spieler/{id}: name, position, birth date, citizenship, for players
            the main dataset does not have. Never refetched.

Minutes are derived from the report, the same way the main dataset's are (checked with
--verify): a starter plays the match length (90, or 120 with extra time) unless substituted
off or sent off, a substitute from his entry minute; stoppage time is not counted (an event
at 90+3 is at minute 90). A match whose minutes fail a validation rule gets `data_issue`
and no appearance rows: wrong minutes would silently skew ratings.

    .venv/bin/python tm_recent.py                      # scrape since the main dataset ends
    .venv/bin/python tm_recent.py --competitions GB1 CL --max-requests 200
    .venv/bin/python tm_recent.py --verify 40          # check the minutes derivation
    .venv/bin/python tm_recent.py --offline            # rebuild the CSVs from cached pages only
"""

import argparse
import datetime as dt
import gzip
import hashlib
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from lxml import html

from tm_fetch import Blocked, Fetcher, NotFound

RAW_DIR = Path(__file__).parent / "data" / "raw"
TMD_DIR = RAW_DIR / "downloads" / "transfermarkt-datasets"
OUT_DIR = RAW_DIR / "downloads" / "transfermarkt-recent"
PAGES_DIR = OUT_DIR / "pages"

TOP_LEAGUES = ["GB1", "ES1", "IT1", "L1", "FR1", "PO1", "NL1", "BE1", "TR1", "SC1"]
UEFA = ["CL", "EL", "UCOL", "CLQ", "ELQ", "ECLQ", "USC"]
SEASONS = (2025, 2026)  # saison_id = year the season starts; calendar-year leagues file 2026 under 2025

# ---------------------------------------------------------------------------------------------
# Selectors. Transfermarkt changes its markup now and then; everything that reads a page is
# here so a markup change is fixed in one place. Parsers raise ParseError instead of
# returning empty rows when something expected is missing.
# ---------------------------------------------------------------------------------------------
SCHEDULE_RESULT_LINKS = "//a[contains(concat(' ', @class, ' '), ' ergebnis-link ')][@id]"
SCHEDULE_DATE_LINK = "preceding::a[contains(@href, '/datum/')][1]/@href"
SCHEDULE_ROW = "ancestor::tr[1]"
SCHEDULE_ROW_CLUBS = ".//td[contains(@class, 'hauptlink')]/a[contains(@href, '/verein/')]/@href"

REPORT_HOME = "//div[contains(@class, 'sb-team') and contains(@class, 'sb-heim')]"
REPORT_AWAY = "//div[contains(@class, 'sb-team') and contains(@class, 'sb-gast')]"
REPORT_TEAM_LINK = ".//a[contains(@class, 'sb-vereinslink')]"
REPORT_DATUM = "//div[@class='sb-spieldaten']/p[contains(@class, 'sb-datum')]"
REPORT_DATE_LINK = ".//a[contains(@href, '/datum/')]/@href"
REPORT_SCORE = "(//div[contains(@class, 'sb-endstand')])[1]"
REPORT_EXTRA_INFO = "//div[@class='sb-spieldaten']/p[contains(@class, 'sb-zusatzinfos')]"
REPORT_STADIUM = ".//a[contains(@href, '/stadion/')]/text()"
REPORT_REFEREE = ".//a[contains(@href, '/schiedsrichter/')]/@title"
REPORT_TIMELINE = "//div[contains(@class, 'sb-zeitleiste-ereignisse')]/@class"
REPORT_LINEUP_BOX = "//div[contains(@class, 'box')][h2[contains(normalize-space(.), 'Line-Ups')]]"
LINEUP_TEAMS = "./div[contains(@class, 'large-6')]"
LINEUP_FORMATION_PLAYER = ".//div[@class='formation-player-container']"
LINEUP_CAPTAIN = ".//div[contains(@class, 'kapitaenicon-formation')]"
LINEUP_NUMBER = ".//div[contains(@class, 'tm-shirt-number')]/text()"
LINEUP_FORMATION = ".//div[contains(@class, 'formation-subtitle')]/text()"
LINEUP_BENCH_ROWS = ".//table[@class='ersatzbank']//tr[.//a[contains(@href, '/spieler/')]]"
SECTION_ITEMS = "//div[@id='{section}']//li[contains(@class, 'sb-aktion-heim') or contains(@class, 'sb-aktion-gast')]"
EVENT_CLOCK = ".//div[@class='sb-aktion-uhr']/span"
EVENT_STATE = ".//div[contains(@class, 'sb-aktion-spielstand')]"
EVENT_ACTION = ".//div[@class='sb-aktion-aktion']"
EVENT_PLAYERS = ".//a[contains(@class, 'wichtig')][contains(@href, '/spieler/')]"
SUB_IN = ".//span[contains(@class, 'sb-aktion-wechsel-ein')]//a[contains(@href, '/spieler/')]"
SUB_OUT = ".//span[contains(@class, 'sb-aktion-wechsel-aus')]//a[contains(@href, '/spieler/')]"

RANKING_PATH = "/statistik/weltrangliste"           # FIFA ranking, 25 nations per page
RANKING_ROWS = "//table[@class='items']/tbody/tr"
RANKING_TEAM = ".//a[contains(@href, '/startseite/verein/')]/@href"
NATION_FIXTURES = "/{slug}/spielplan/verein/{team_id}/saison_id/{season}"  # national teams: calendar years
NATION_BOX = "ancestor::div[contains(concat(' ', @class, ' '), ' box ')][1]"
NATION_BOX_COMPETITION = ".//a[contains(@href, '/wettbewerb/')]/@href"
NATION_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
COMPETITION_RE = re.compile(r"/wettbewerb/([A-Z0-9]+)")

PLAYER_HEADLINE = "//h1"
PLAYER_SHIRT_NUMBER = "//h1//span[contains(@class, 'shirt-number')]"
PLAYER_INFO_LABELS = "//div[contains(@class, 'info-table')]/span[contains(@class, 'info-table__content--regular')]"
PLAYER_BIRTH_DATE = "//span[@itemprop='birthDate']/text()"
PLAYER_MAIN_POSITION = "//*[contains(@class, 'detail-position__position')]/text()"

ID_RE = re.compile(r"/(?:spieler|verein)/(\d+)")
SPRITE_RE = re.compile(r"background-position:\s*(-?\d+)px\s+(-?\d+)px")
SCORE_RE = re.compile(r"^\s*(\d+)\s*:\s*(\d+)\s*(.*)$")
SPRITE_CELL = 36  # the minute clock is a sprite of 36 px cells, ten minutes per row
NOT_AN_ASSIST = re.compile(r"handball by", re.IGNORECASE)
# Substitutions at the start of a period are shown at 46/91/106; the dataset counts them at the
# end of the previous period (verified with --verify), so a half-time change is 45 + 45 minutes.
PERIOD_START = {46: 45, 91: 90, 106: 105}

# Bench positions on the report are abbreviations; the dataset spells them out.
POSITION_NAMES = {
    "GK": "Goalkeeper", "CB": "Centre-Back", "LB": "Left-Back", "RB": "Right-Back",
    "DM": "Defensive Midfield", "CM": "Central Midfield", "AM": "Attacking Midfield",
    "LM": "Left Midfield", "RM": "Right Midfield", "LW": "Left Winger", "RW": "Right Winger",
    "SS": "Second Striker", "CF": "Centre-Forward",
}

# Issues that make the derived minutes untrustworthy: the match keeps its result but gets no
# appearance rows. The others are flagged and kept.
MINUTES_ISSUES = {
    "unknown_match_length", "starters_not_11", "player_listed_twice", "substitution_inconsistent",
    "minutes_out_of_range", "minutes_do_not_add_up", "substitute_minutes_too_high",
}


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------------------------
# Parsers (pure: page text in, plain data out; tested on saved pages in tests/)
# ---------------------------------------------------------------------------------------------

def _id(href: str | None) -> int:
    match = ID_RE.search(href or "")
    if not match:
        raise ParseError(f"no id in link {href!r}")
    return int(match.group(1))


def _text(element) -> str:
    return re.sub(r"\s+", " ", element.text_content()).strip()


def parse_schedule(text: str) -> list[dict]:
    """Finished games on a competition's schedule page: id, date, result text, club ids."""
    tree = html.fromstring(text)
    games = []
    for link in tree.xpath(SCHEDULE_RESULT_LINKS):
        game_id = link.get("id")
        if not game_id.isdigit():
            continue
        result = _text(link)
        if not SCORE_RE.match(result):
            continue  # not played yet ("-:-") or postponed
        dates = link.xpath(SCHEDULE_DATE_LINK)
        if not dates:
            raise ParseError(f"schedule: no date before game {game_id}")
        date = dates[0].rstrip("/").rsplit("/", 1)[-1]
        clubs = [_id(h) for h in link.xpath(SCHEDULE_ROW)[0].xpath(SCHEDULE_ROW_CLUBS)]
        games.append({"game_id": int(game_id), "date": date, "result": result,
                      "home_club_id": clubs[0] if len(clubs) >= 2 else None,
                      "away_club_id": clubs[-1] if len(clubs) >= 2 else None})
    return games


def parse_ranking(text: str) -> list[tuple[str, int]]:
    """(slug, team id) of the nations on a FIFA ranking page, best first."""
    nations = []
    for row in html.fromstring(text).xpath(RANKING_ROWS):
        links = row.xpath(RANKING_TEAM)
        if links:
            nations.append((links[0].strip("/").split("/")[0], _id(links[0])))
    if not nations:
        raise ParseError("ranking page without nations")
    return nations


def parse_nation_fixtures(text: str) -> list[dict]:
    """Finished games on a national team's fixtures page, with their competition."""
    tree = html.fromstring(text)
    games = []
    for link in tree.xpath(SCHEDULE_RESULT_LINKS):
        game_id, result = link.get("id"), _text(link)
        if not game_id.isdigit() or not SCORE_RE.match(result):
            continue
        row = link.xpath(SCHEDULE_ROW)[0]
        date = NATION_DATE.search(_text(row))
        box = link.xpath(NATION_BOX)
        competition = COMPETITION_RE.search(" ".join(box[0].xpath(NATION_BOX_COMPETITION)[:1])) if box else None
        if not date or not competition:
            raise ParseError(f"nation fixtures: no date or competition for game {game_id}")
        games.append({"game_id": int(game_id), "date": f"{date.group(3)}-{date.group(2)}-{date.group(1)}",
                      "result": result, "competition_id": competition.group(1),
                      "home_club_id": None, "away_club_id": None})
    return games


def _minute(item) -> tuple[int, int]:
    """(minute, stoppage) of an event, from the sprite clock: 90+3 is (90, 3)."""
    clocks = item.xpath(EVENT_CLOCK)
    if not clocks:
        raise ParseError("event without a clock")
    match = SPRITE_RE.search(clocks[0].get("style") or "")
    if not match:
        raise ParseError(f"clock without sprite position: {clocks[0].get('style')!r}")
    x, y = -int(match.group(1)) // SPRITE_CELL, -int(match.group(2)) // SPRITE_CELL
    extra = re.search(r"\+\s*(\d+)", _text(clocks[0]))
    return x + 1 + 10 * y, int(extra.group(1)) if extra else 0


def _side(item) -> str:
    return "home" if "sb-aktion-heim" in item.get("class") else "away"


def parse_report(text: str, game_id: int) -> dict:
    """Everything the store needs from one match report. Raises ParseError if the page
    does not look like a finished match report."""
    tree = html.fromstring(text)
    teams = {}
    for side, xpath in (("home", REPORT_HOME), ("away", REPORT_AWAY)):
        found = tree.xpath(xpath)
        if not found:
            raise ParseError(f"{game_id}: no {side} team")
        link = found[0].xpath(REPORT_TEAM_LINK)[0]
        teams[side] = {"id": _id(link.get("href")), "name": link.get("title") or _text(link)}

    datum = tree.xpath(REPORT_DATUM)
    if not datum:
        raise ParseError(f"{game_id}: no match date line")
    round_name = _text(datum[0]).split("|")[0].strip()
    round_name = re.sub(r"(\b[Ll]eg)\s+\d+$", r"\1", round_name)  # "Semi-Finals 2nd Leg 1"
    date_links = datum[0].xpath(REPORT_DATE_LINK)
    date = date_links[0].rstrip("/").rsplit("/", 1)[-1] if date_links else None

    score_nodes = tree.xpath(REPORT_SCORE)
    if not score_nodes:
        raise ParseError(f"{game_id}: no score")
    score_text = _text(score_nodes[0])
    score = SCORE_RE.match(score_text)
    if not score:
        raise ParseError(f"{game_id}: score {score_text!r} is not a result")
    suffix = score.group(3).lower()
    penalties = "pens" in suffix
    extra_time = penalties or "aet" in suffix

    info = tree.xpath(REPORT_EXTRA_INFO)
    stadium = info[0].xpath(REPORT_STADIUM) if info else []
    referee = info[0].xpath(REPORT_REFEREE) if info else []
    attendance = re.search(r"Attendance:\s*([\d.,]+)", _text(info[0])) if info else None

    timeline = tree.xpath(REPORT_TIMELINE)
    length_match = re.search(r"sb-(\d+)-minuten", timeline[0]) if timeline else None
    length = int(length_match.group(1)) if length_match else None

    goals = []
    for item in tree.xpath(SECTION_ITEMS.format(section="sb-tore")):
        minute, extra = _minute(item)
        action = item.xpath(EVENT_ACTION)[0]
        players = action.xpath(EVENT_PLAYERS)
        description = _text(action)
        assist = None
        if "Assist:" in description:
            assist_text = description.split("Assist:", 1)[1]
            # "Handball by X" names an opponent, not an assist. A won penalty is an assist
            # unless the fouled player takes it himself (the dataset's convention).
            if players[1:] and not NOT_AN_ASSIST.search(assist_text):
                assist = _id(players[1].get("href"))
                if assist == _id(players[0].get("href")):
                    assist = None
        state = SCORE_RE.match(_text(item.xpath(EVENT_STATE)[0]))
        goals.append({
            "side": _side(item), "minute": minute, "extra": extra,
            "player_id": _id(players[0].get("href")) if players else None,
            "assist_id": assist, "own_goal": "own-goal" in description.lower(),
            "state": (int(state.group(1)), int(state.group(2))) if state else None,
            "description": description,
        })

    subs = []
    for item in tree.xpath(SECTION_ITEMS.format(section="sb-wechsel")):
        minute, extra = _minute(item)
        on, off = item.xpath(SUB_IN), item.xpath(SUB_OUT)
        subs.append({"side": _side(item), "minute": minute, "extra": extra,
                     "in": _id(on[0].get("href")) if on else None,
                     "out": _id(off[0].get("href")) if off else None,
                     "description": _text(item.xpath(EVENT_ACTION)[0])})

    cards = []
    for item in tree.xpath(SECTION_ITEMS.format(section="sb-karten")):
        minute, extra = _minute(item)
        state = item.xpath(EVENT_STATE)[0]
        kinds = " ".join(state.xpath(".//span/@class"))
        kind = "second_yellow" if "gelbrot" in kinds else "red" if "sb-rot" in kinds else \
            "yellow" if "sb-gelb" in kinds else None
        players = item.xpath(EVENT_ACTION)[0].xpath(EVENT_PLAYERS)
        if kind is None:
            raise ParseError(f"{game_id}: card of unknown kind {kinds!r}")
        if not players:
            continue  # a card for a coach or official
        cards.append({"side": _side(item), "minute": minute, "extra": extra, "kind": kind,
                      "player_id": _id(players[0].get("href")),
                      "description": _text(item.xpath(EVENT_ACTION)[0])})

    shootout = []
    for item in tree.xpath(SECTION_ITEMS.format(section="sb-elfmeterscheissen")):
        players = item.xpath(EVENT_ACTION)[0].xpath(EVENT_PLAYERS)
        outcome = " ".join(item.xpath(EVENT_CLOCK + "/@title")) or _text(item.xpath(EVENT_ACTION)[0])
        shootout.append({"side": _side(item), "player_id": _id(players[0].get("href")) if players else None,
                         "scored": "scored" in outcome.lower(), "description": outcome})
    if penalties and not shootout:
        raise ParseError(f"{game_id}: decided on penalties but no shoot-out section")

    # The score line shows the shoot-out score for a match decided on penalties; the score
    # after extra time is the last goal's running score (0:0 without goals).
    if penalties:
        last = next((g["state"] for g in reversed(goals) if g["state"]), (0, 0))
        home_goals, away_goals = last
    else:
        home_goals, away_goals = int(score.group(1)), int(score.group(2))

    lineups, formations, has_lineups = [], {}, False
    boxes = tree.xpath(REPORT_LINEUP_BOX)
    if boxes:
        blocks = boxes[0].xpath(LINEUP_TEAMS)
        if len(blocks) != 2:
            raise ParseError(f"{game_id}: line-up box has {len(blocks)} team blocks")
        for side, block in zip(("home", "away"), blocks):
            team_links = block.xpath(".//a[contains(@href, '/verein/')]/@href")
            if team_links and _id(team_links[0]) != teams[side]["id"]:
                raise ParseError(f"{game_id}: line-up block order does not match the teams")
            formation = block.xpath(LINEUP_FORMATION)
            formations[side] = formation[0].split(":", 1)[-1].strip() if formation else None
            starters = block.xpath(LINEUP_FORMATION_PLAYER)
            bench = block.xpath(LINEUP_BENCH_ROWS)
            if not starters and not bench:
                continue
            if not starters:
                raise ParseError(f"{game_id}: {side} has a bench but no starters (unknown layout)")
            has_lineups = True
            for player in starters:
                link = player.xpath(".//a[contains(@href, '/spieler/')]")
                if not link:
                    raise ParseError(f"{game_id}: starter without player link")
                number = [n.strip() for n in player.xpath(LINEUP_NUMBER) if n.strip()]
                lineups.append({"side": side, "player_id": _id(link[0].get("href")),
                                "name": link[0].get("title") or _text(link[0]), "starter": True,
                                "position": None, "number": number[0] if number else None,
                                "captain": bool(player.xpath(LINEUP_CAPTAIN))})
            for row in bench:
                link = row.xpath(".//a[contains(@href, '/spieler/')]")[0]
                cells = row.xpath("./td")
                abbreviation = _text(cells[-1]) if cells else ""
                number = [n.strip() for n in row.xpath(LINEUP_NUMBER) if n.strip()]
                lineups.append({"side": side, "player_id": _id(link.get("href")),
                                "name": link.get("title") or _text(link), "starter": False,
                                "position": POSITION_NAMES.get(abbreviation, abbreviation or None),
                                "number": number[0] if number else None, "captain": False})

    return {
        "game_id": game_id, "date": date, "round": round_name, "teams": teams,
        "score_line": (int(score.group(1)), int(score.group(2))), "home_goals": home_goals, "away_goals": away_goals, "extra_time": extra_time,
        "penalties": penalties, "length": length, "stadium": stadium[0].strip() if stadium else None,
        "referee": referee[0] if referee else None,
        "attendance": int(re.sub(r"\D", "", attendance.group(1))) if attendance else None,
        "formations": formations, "has_lineups": has_lineups, "lineups": lineups,
        "goals": goals, "subs": subs, "cards": cards, "shootout": shootout,
    }


def parse_player(text: str, player_id: int) -> dict:
    tree = html.fromstring(text)
    headline = tree.xpath(PLAYER_HEADLINE)
    if not headline:
        raise ParseError(f"player {player_id}: no name")
    name = _text(headline[0])
    for number in tree.xpath(PLAYER_SHIRT_NUMBER):
        name = name.replace(_text(number), "", 1)
    name = name.strip()
    info = {}
    for label in tree.xpath(PLAYER_INFO_LABELS):
        value = label.getnext()
        if value is not None:
            info[_text(label).rstrip(":")] = value
    position = sub_position = None
    if "Position" in info:
        parts = [p.strip() for p in _text(info["Position"]).split(" - ")]
        position = parts[0] or None
        sub_position = parts[-1] if len(parts) > 1 else (parts[0] if parts[0] == "Goalkeeper" else None)
    birth = tree.xpath(PLAYER_BIRTH_DATE)
    date_of_birth = None
    if birth:
        found = re.search(r"(\d{2})/(\d{2})/(\d{4})", birth[0])
        if found:
            date_of_birth = f"{found.group(3)}-{found.group(2)}-{found.group(1)}"
    citizenship = None
    if "Citizenship" in info:
        flags = info["Citizenship"].xpath(".//img/@title")
        citizenship = flags[0] if flags else (_text(info["Citizenship"]) or None)
    return {"player_id": player_id, "name": name, "position": position, "sub_position": sub_position,
            "date_of_birth": date_of_birth, "country_of_citizenship": citizenship}


# ---------------------------------------------------------------------------------------------
# Minutes and validation
# ---------------------------------------------------------------------------------------------

def derive(report: dict) -> tuple[list[dict], list[str]]:
    """Appearance rows (players who played) and the validation issues of one match.

    Starters play from 0, substitutes from their entry minute; everyone plays to the end of
    the match (90 or 120) unless substituted off or sent off. Stoppage time is not counted."""
    issues = []
    length = report["length"] or (120 if report["extra_time"] else None)
    if length is None:
        issues.append("unknown_match_length")
        length = 90
    if report["extra_time"] and length != 120 and not report["penalties"]:
        issues.append("unknown_match_length")  # AET on the score line but a 90-minute timeline
    side_of = {p["player_id"]: p["side"] for p in report["lineups"]}
    seen = Counter(p["player_id"] for p in report["lineups"])
    if any(n > 1 for n in seen.values()):
        issues.append("player_listed_twice")
    for side in ("home", "away"):
        if sum(1 for p in report["lineups"] if p["side"] == side and p["starter"]) != 11:
            issues.append("starters_not_11")
            break

    on = {p["player_id"]: 0 for p in report["lineups"] if p["starter"]}
    off = {}
    for sub in sorted(report["subs"], key=lambda s: (s["minute"], s["extra"])):
        minute = min(PERIOD_START.get(sub["minute"], sub["minute"]) if not sub["extra"] else sub["minute"], length)
        if sub["out"] is None or sub["in"] is None or sub["out"] not in on or sub["out"] in off \
                or sub["in"] in on or side_of.get(sub["in"], sub["side"]) != sub["side"]:
            issues.append("substitution_inconsistent")
            continue
        off[sub["out"]] = minute
        on[sub["in"]] = minute
    for card in report["cards"]:
        if card["kind"] in ("red", "second_yellow") and card["player_id"] in on:
            off[card["player_id"]] = min(off.get(card["player_id"], length), min(card["minute"], length))

    goals, assists = Counter(), Counter()
    for goal in report["goals"]:
        if goal["player_id"] and not goal["own_goal"]:
            goals[goal["player_id"]] += 1
        if goal["assist_id"]:
            assists[goal["assist_id"]] += 1
    # The dataset's convention: a second yellow is two yellows and no red; red is a straight red.
    yellow, red = Counter(), Counter()
    for card in report["cards"]:
        if card["kind"] == "red":
            red[card["player_id"]] += 1
        else:
            yellow[card["player_id"]] += 1

    names = {p["player_id"]: p["name"] for p in report["lineups"]}
    rows = []
    starters = {p["player_id"] for p in report["lineups"] if p["starter"]}
    for player_id, start in on.items():
        played = off.get(player_id, length) - start
        if player_id not in starters:
            played = max(played, 1)  # a substitute in stoppage time is credited one minute
        rows.append({"player_id": player_id, "side": side_of.get(player_id), "name": names.get(player_id),
                     "minutes": played, "started": player_id in starters,
                     "goals": goals[player_id], "assists": assists[player_id],
                     "yellow": yellow[player_id], "red": red[player_id]})

    for side in ("home", "away"):
        side_rows = [r for r in rows if r["side"] == side]
        if any(r["minutes"] < 0 or r["minutes"] > 150 or (r["started"] and r["minutes"] == 0 and r["red"] == 0
                                                         and r["yellow"] < 2) for r in side_rows):
            issues.append("minutes_out_of_range")
        if sum(r["minutes"] for r in side_rows) > 11 * length * 1.05:
            issues.append("minutes_do_not_add_up")
        starter_minutes = [r["minutes"] for r in side_rows if r["started"]]
        if starter_minutes and any(r["minutes"] > max(1, length - min(starter_minutes))
                                   for r in side_rows if not r["started"]):
            issues.append("substitute_minutes_too_high")

    if report["penalties"] and report["home_goals"] != report["away_goals"]:
        issues.append("shootout_without_level_score")  # fine for a second leg; ingest checks the aggregate
    return rows, sorted(set(issues))


# ---------------------------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------------------------

@dataclass
class Scope:
    competitions: pd.DataFrame
    since: str
    until: str
    games: list = field(default_factory=list)  # (competition_id, season, schedule row)


def load_competitions() -> pd.DataFrame:
    return pd.read_csv(TMD_DIR / "competitions.csv.gz")


def default_since() -> str:
    """The day after the main dataset's newest club match. Read from the download, not the
    store: the store also holds what this script scraped, and starting after that would drop
    the earlier scraped matches from the output."""
    games = pd.read_csv(TMD_DIR / "games.csv.gz", usecols=["date", "competition_type"])
    newest = games.loc[games.competition_type != "national_team_competition", "date"].max()
    return (dt.date.fromisoformat(newest) + dt.timedelta(days=1)).isoformat()


def priority(competition_id: str) -> tuple:
    if competition_id in TOP_LEAGUES:
        return (0, TOP_LEAGUES.index(competition_id))
    if competition_id in UEFA:
        return (1, UEFA.index(competition_id))
    return (2, competition_id)


def schedule_path(row) -> str:
    """The competition's schedule path, from its dataset url (/{slug}/startseite/{kind}/{ID})."""
    match = re.search(r"\.[a-z.]+(/[^/]+)/startseite/(wettbewerb|pokalwettbewerb)/([A-Z0-9]+)", row.url)
    if not match:
        raise ParseError(f"competition {row.competition_id}: unexpected url {row.url}")
    return f"{match.group(1)}/gesamtspielplan/{match.group(2)}/{match.group(3)}"


def schedule_games(fetcher: Fetcher, row, season: int, today: str, offline: bool) -> list[dict]:
    key_prefix = f"schedule/{row.competition_id}_{season}_"
    if offline:
        cached = sorted(PAGES_DIR.glob(f"{key_prefix}*.html.gz"))
        cached = [c for c in cached if "explore" not in c.name]
        if not cached:
            return []
        text = gzip.decompress(cached[-1].read_bytes()).decode("utf-8")
    else:
        try:
            text = fetcher.get(f"{schedule_path(row)}/saison_id/{season}", key_prefix + today)
        except NotFound:
            return []
    return parse_schedule(text)


def collect_scope(fetcher: Fetcher, competitions: pd.DataFrame, since: str, until: str, offline: bool) -> Scope:
    scope = Scope(competitions, since, until)
    today = dt.date.today().isoformat()
    for row in sorted(competitions.itertuples(), key=lambda r: priority(r.competition_id)):
        for season in SEASONS:
            found = [g for g in schedule_games(fetcher, row, season, today, offline) if since <= g["date"] <= until]
            scope.games.extend((row.competition_id, season, g) for g in found)
        print(f"  schedule {row.competition_id}: {sum(1 for c, _, _ in scope.games if c == row.competition_id)} "
              f"finished matches in range", flush=True)
    # A game listed twice (a competition's page that shows another's matches) is kept once.
    unique, seen = [], set()
    for item in scope.games:
        if item[2]["game_id"] not in seen:
            seen.add(item[2]["game_id"])
            unique.append(item)
    scope.games = unique
    return scope


NATIONAL_TYPE = "national_team_competition"
# The main dataset files the 2026 World Cup under season 2025 (ingest.TOURNAMENT_HOSTS uses it).
NATIONAL_SEASON = {"FIWC": 2025}


def add_nations(fetcher: Fetcher, scope: Scope, top: int, offline: bool) -> None:
    """National-team matches of the `top` nations of the FIFA ranking: tournaments,
    qualifiers, Nations League and friendlies, whatever their fixtures pages list."""
    today = dt.date.today().isoformat()
    nations = []
    for page in range(1, (top - 1) // 25 + 2):
        path = RANKING_PATH + (f"?page={page}" if page > 1 else "")
        key = f"nations/fifa_ranking{'' if page == 1 else f'_p{page}'}_{today}"
        nations += parse_ranking(cached_or_fetch(fetcher, path, key, offline))
    nations = nations[:top]
    season = int(scope.until[:4])
    have = {g["game_id"] for _, _, g in scope.games}
    added = 0
    for slug, team_id in nations:
        try:
            text = cached_or_fetch(fetcher, NATION_FIXTURES.format(slug=slug, team_id=team_id, season=season),
                                   f"nations/{team_id}_{season}_{today}", offline)
        except NotFound as exc:
            print(f"  [skip] {slug}: {exc}")
            continue
        for game in parse_nation_fixtures(text):
            if scope.since <= game["date"] <= scope.until and game["game_id"] not in have:
                have.add(game["game_id"])
                competition_id = game.pop("competition_id")
                scope.games.append((competition_id, NATIONAL_SEASON.get(competition_id, season), game))
                added += 1
    print(f"  nations {', '.join(s for s, _ in nations)}: {added} more matches in range", flush=True)


def cached_or_fetch(fetcher: Fetcher, path: str, key: str, offline: bool) -> str:
    """A page cached per day (rankings, fixtures). Offline: the newest cached copy."""
    if offline:
        prefix = key.rsplit("_", 1)[0]
        cached = sorted(PAGES_DIR.glob(f"{prefix}_????-??-??.html.gz"))  # the date only, not _p2_
        if not cached:
            raise NotFound(f"offline and not cached: {key}")
        return gzip.decompress(cached[-1].read_bytes()).decode("utf-8")
    return fetcher.get(path, key)


def report_key(game_id: int) -> str:
    return f"game/{game_id}"


def player_key(player_id: int) -> str:
    return f"player/{player_id}"


def fetch_reports(fetcher: Fetcher, game_ids: list[int], max_requests: int | None, refetch: bool) -> int:
    missing = [g for g in game_ids if refetch or not fetcher.cached(report_key(g))]
    print(f"match reports: {len(game_ids) - len(missing)} cached, {len(missing)} to fetch "
          f"(~{len(missing) * fetcher.min_interval / 3600:.1f} h at {fetcher.min_interval}s each)", flush=True)
    started, done = time.monotonic(), 0
    for game_id in missing:
        if max_requests is not None and fetcher.fetched >= max_requests:
            print(f"stopping at --max-requests {max_requests}; run again to continue")
            break
        try:
            fetcher.get(f"/spielbericht/index/spielbericht/{game_id}", report_key(game_id), refetch=refetch)
        except NotFound as exc:
            print(f"  [missing] {exc}")
        done += 1
        if done % 25 == 0 or done == len(missing):
            rate = (time.monotonic() - started) / done
            print(f"  reports {done}/{len(missing)}, ~{(len(missing) - done) * rate / 60:.0f} min left", flush=True)
    return done


def fetch_players(fetcher: Fetcher, player_ids: list[int], max_requests: int | None) -> None:
    missing = [p for p in player_ids if not fetcher.cached(player_key(p))]
    print(f"player profiles: {len(player_ids) - len(missing)} cached, {len(missing)} to fetch", flush=True)
    for done, player_id in enumerate(missing, 1):
        if max_requests is not None and fetcher.fetched >= max_requests:
            print(f"stopping at --max-requests {max_requests}; run again to continue")
            break
        try:
            fetcher.get(f"/-/profil/spieler/{player_id}", player_key(player_id))
        except NotFound as exc:
            print(f"  [missing] {exc}")
        if done % 50 == 0:
            print(f"  players {done}/{len(missing)}", flush=True)


def read_cached(fetcher: Fetcher, key: str) -> str | None:
    return gzip.decompress(fetcher.cache_path(key).read_bytes()).decode("utf-8") if fetcher.cached(key) else None


# ---------------------------------------------------------------------------------------------
# Output: tables shaped like transfermarkt-datasets' CSVs
# ---------------------------------------------------------------------------------------------

def _hash(*parts) -> str:
    return hashlib.md5("_".join(map(str, parts)).encode()).hexdigest()


def tables_for(report: dict, competition_id: str, season: int, competition_type: str,
               schedule_row: dict | None) -> tuple[dict, list, list, list, list[str]]:
    rows, issues = derive(report)
    teams = report["teams"]
    if schedule_row and schedule_row.get("home_club_id") and \
            (schedule_row["home_club_id"], schedule_row["away_club_id"]) != (teams["home"]["id"], teams["away"]["id"]):
        issues.append("teams_differ_from_schedule")
    if report["extra_time"] and competition_type == "domestic_league":
        issues.append("extra_time_in_league")
    date = (schedule_row or {}).get("date") or report["date"]
    shootout_home = sum(1 for k in report["shootout"] if k["side"] == "home" and k["scored"])
    shootout_away = sum(1 for k in report["shootout"] if k["side"] == "away" and k["scored"])
    game_id = report["game_id"]
    # Same convention as the main dataset: scored shoot-out kicks are added into the score and
    # listed as Shootout events, which ingest.remove_shootout_goals subtracts again.
    home_goals, away_goals = report["home_goals"] + shootout_home, report["away_goals"] + shootout_away
    if report["penalties"] and (home_goals, away_goals) != tuple(report["score_line"]):
        issues.append("shootout_score_mismatch")  # the score line is goals plus scored kicks
    game = {
        "game_id": game_id, "competition_id": competition_id, "season": season, "round": report["round"],
        "date": date, "home_club_id": teams["home"]["id"], "away_club_id": teams["away"]["id"],
        "home_club_goals": home_goals, "away_club_goals": away_goals,
        "stadium": report["stadium"], "attendance": report["attendance"], "referee": report["referee"],
        "url": f"https://www.transfermarkt.com/spielbericht/index/spielbericht/{game_id}",
        "home_club_formation": report["formations"].get("home"), "away_club_formation": report["formations"].get("away"),
        "home_club_name": teams["home"]["name"], "away_club_name": teams["away"]["name"],
        "aggregate": f"{home_goals}:{away_goals}", "competition_type": competition_type,
        "extra_time": int(report["extra_time"]), "has_lineups": int(report["has_lineups"]),
        "data_issue": ",".join(sorted(set(issues))) or None,
    }
    club = {"home": teams["home"], "away": teams["away"]}
    lineups = [{
        "game_lineups_id": _hash(game_id, p["player_id"]), "date": date, "game_id": game_id,
        "player_id": p["player_id"], "club_id": club[p["side"]]["id"], "player_name": p["name"],
        "type": "starting_lineup" if p["starter"] else "substitutes", "position": p["position"],
        "number": p["number"], "team_captain": int(p["captain"]),
    } for p in report["lineups"]]
    appearances = [] if set(issues) & MINUTES_ISSUES else [{
        "appearance_id": f"{game_id}_{r['player_id']}", "game_id": game_id, "player_id": r["player_id"],
        "player_club_id": club[r["side"]]["id"], "player_current_club_id": None, "date": date,
        "player_name": r["name"], "competition_id": competition_id, "yellow_cards": r["yellow"],
        "red_cards": r["red"], "goals": r["goals"], "assists": r["assists"], "minutes_played": r["minutes"],
    } for r in rows]
    events = []
    for g in report["goals"]:
        events.append({"minute": g["minute"], "type": "Goals", "side": g["side"], "player_id": g["player_id"],
                       "description": g["description"], "player_in_id": None, "player_assist_id": g["assist_id"]})
    for s in report["subs"]:
        events.append({"minute": s["minute"], "type": "Substitutions", "side": s["side"], "player_id": s["out"],
                       "description": s["description"], "player_in_id": s["in"], "player_assist_id": None})
    for c in report["cards"]:
        events.append({"minute": c["minute"], "type": "Cards", "side": c["side"], "player_id": c["player_id"],
                       "description": c["description"], "player_in_id": None, "player_assist_id": None})
    for i, k in enumerate(report["shootout"]):
        events.append({"minute": -1, "type": "Shootout", "side": k["side"], "player_id": k["player_id"],
                       "description": "Scored" if k["scored"] else f"Missed ({k['description']})",
                       "player_in_id": None, "player_assist_id": None, "order": i})
    event_rows = [{
        "game_event_id": _hash(game_id, e["type"], e["minute"], e["player_id"], e.get("order", i)), "date": date,
        "game_id": game_id, "minute": e["minute"], "type": e["type"], "club_id": club[e["side"]]["id"],
        "club_name": club[e["side"]]["name"], "player_id": e["player_id"], "description": e["description"],
        "player_in_id": e["player_in_id"], "player_assist_id": e["player_assist_id"],
    } for i, e in enumerate(events)]
    return game, lineups, appearances, event_rows, issues


def build_tables(fetcher: Fetcher, scope: Scope) -> dict:
    types = dict(zip(load_competitions().competition_id, load_competitions()["type"]))
    games, lineups, appearances, events, failures = [], [], [], [], []
    for competition_id, season, row in scope.games:
        text = read_cached(fetcher, report_key(row["game_id"]))
        if text is None:
            continue
        try:
            report = parse_report(text, row["game_id"])
        except ParseError as exc:
            failures.append((competition_id, row["game_id"], str(exc)))
            continue
        kind = types.get(competition_id, NATIONAL_TYPE)  # only nation fixtures bring other ids
        game, lineup, appearance, event, _ = tables_for(report, competition_id, season, kind, row)
        games.append(game)
        lineups += lineup
        appearances += appearance
        events += event
    return {"games": pd.DataFrame(games), "game_lineups": pd.DataFrame(lineups),
            "appearances": pd.DataFrame(appearances), "game_events": pd.DataFrame(events), "failures": failures}


def fill_positions(lineups: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Starters' positions are not on the report (only a formation graphic); use the player's
    main position instead. The model reads only `starter`, never `position`."""
    if lineups.empty:
        return lineups
    main = dict(zip(players.player_id, players.sub_position))
    lineups = lineups.copy()
    missing = lineups.position.isna()
    lineups.loc[missing, "position"] = lineups.loc[missing, "player_id"].map(main)
    return lineups


def write_tables(tables: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("games", "game_lineups", "appearances", "game_events", "players"):
        frame = tables[name]
        target = OUT_DIR / f"{name}.csv.gz"
        partial = target.with_suffix(".part")
        frame.to_csv(partial, index=False, compression="gzip")
        partial.rename(target)
        print(f"  wrote {target.relative_to(RAW_DIR)}: {len(frame)} rows")


# ---------------------------------------------------------------------------------------------
# Verification against the main dataset (--verify)
# ---------------------------------------------------------------------------------------------

def verify(fetcher: Fetcher, n: int, max_requests: int | None) -> None:
    """Scrape n matches the main dataset already has (May-July 2026, top leagues and cups
    first) and compare per player: minutes, started, goals, assists, cards."""
    games = pd.read_csv(TMD_DIR / "games.csv.gz")
    apps = pd.read_csv(TMD_DIR / "appearances.csv.gz")
    lineups = pd.read_csv(TMD_DIR / "game_lineups.csv.gz", usecols=["game_id", "player_id", "type"])
    with_minutes = set(apps.game_id)
    recent = games[(games.date >= "2026-05-01") & games.game_id.isin(with_minutes)].copy()
    recent["p"] = [priority(c)[0] for c in recent.competition_id]
    sample = pd.concat([
        recent[recent.p == 0].sample(min(n * 2 // 3, (recent.p == 0).sum()), random_state=1),
        recent[recent.p > 0].sample(min(n - n * 2 // 3, (recent.p > 0).sum()), random_state=1),
    ])
    fetch_reports(fetcher, list(sample.game_id), max_requests, refetch=False)
    compared, diffs, per_game, issues_seen = [], [], [], Counter()
    for game in sample.itertuples():
        text = read_cached(fetcher, report_key(game.game_id))
        if text is None:
            continue
        report = parse_report(text, game.game_id)
        rows, issues = derive(report)
        issues_seen.update(issues)
        mine = {r["player_id"]: r for r in rows}
        theirs = apps[apps.game_id == game.game_id].set_index("player_id")
        starters = set(lineups[(lineups.game_id == game.game_id) & (lineups["type"] == "starting_lineup")].player_id)
        my_starters = {p["player_id"] for p in report["lineups"] if p["starter"]}
        score_ok = (report["home_goals"], report["away_goals"]) == (game.home_club_goals, game.away_club_goals) \
            or report["penalties"]
        per_game.append({"game_id": game.game_id, "competition": game.competition_id, "players": len(theirs),
                         "only_mine": len(set(mine) - set(theirs.index)),
                         "only_theirs": len(set(theirs.index) - set(mine)),
                         "starters_agree": starters == my_starters, "score_ok": score_ok,
                         "round_ok": report["round"] == game.round, "issues": ",".join(issues)})
        for player_id in set(mine) - set(theirs.index):
            diffs.append((game.game_id, player_id, mine[player_id]["name"], "only in scrape", None,
                          mine[player_id]["minutes"]))
        for player_id, their in theirs.iterrows():
            my = mine.get(player_id)
            if my is None:
                diffs.append((game.game_id, player_id, their.player_name, "missing in scrape", their.minutes_played, None))
                continue
            row = {"minutes": my["minutes"] == their.minutes_played,
                   "minutes_2": abs(my["minutes"] - their.minutes_played) <= 2,
                   "started": (player_id in my_starters) == (player_id in starters),
                   "goals": my["goals"] == their.goals, "assists": my["assists"] == their.assists,
                   "yellow": my["yellow"] == their.yellow_cards, "red": my["red"] == their.red_cards}
            compared.append(row)
            for name in ("minutes", "goals", "assists", "yellow", "red"):
                if not row[name]:
                    mine_value = my[name]
                    their_value = {"minutes": their.minutes_played, "goals": their.goals, "assists": their.assists,
                                   "yellow": their.yellow_cards, "red": their.red_cards}[name]
                    diffs.append((game.game_id, player_id, their.player_name, name, their_value, mine_value))
    table = pd.DataFrame(compared)
    games_table = pd.DataFrame(per_game)
    print(f"\nVERIFY: {len(games_table)} matches, {len(table)} player rows compared")
    for column in table.columns:
        print(f"  {column:<10} agree {table[column].mean():7.2%}")
    print(f"  starters agree in {games_table.starters_agree.mean():.0%} of matches, score in "
          f"{games_table.score_ok.mean():.0%}, round name in {games_table.round_ok.mean():.0%}")
    print(f"  players only in scrape: {games_table.only_mine.sum()}, only in dataset: {games_table.only_theirs.sum()}")
    print(f"  issues raised: {dict(issues_seen) or 'none'}")
    if diffs:
        print("  differences (game, player, name, field, dataset, scrape):")
        for d in diffs[:80]:
            print("   ", d)
    out = RAW_DIR / "results" / "tm_recent_verify.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(diffs, columns=["game_id", "player_id", "name", "field", "dataset", "scrape"]).to_csv(out, index=False)
    print(f"  differences written to {out.relative_to(RAW_DIR)}")


# ---------------------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", help="first match date (default: day after the main dataset's newest club match)")
    parser.add_argument("--until", help="last match date (default: yesterday)")
    parser.add_argument("--competitions", nargs="+", help="competition ids (default: all in the dataset)")
    parser.add_argument("--refetch", action="store_true", help="fetch match reports again even if cached")
    parser.add_argument("--offline", action="store_true", help="use cached pages only; fetch nothing")
    parser.add_argument("--max-requests", type=int, help="stop after this many page fetches (resume later)")
    parser.add_argument("--verify", type=int, metavar="N", help="check the minutes derivation on N known matches")
    parser.add_argument("--nations", type=int, default=0, metavar="N",
                        help="also the national-team matches of the top N of the FIFA ranking")
    parser.add_argument("--no-players", action="store_true", help="skip fetching profiles of new players")
    args = parser.parse_args()

    fetcher = Fetcher(PAGES_DIR, offline=args.offline)
    try:
        if args.verify:
            verify(fetcher, args.verify, args.max_requests)
            return
        run(fetcher, args)
    except Blocked as exc:
        print(f"\nSTOPPED: {exc}\nCached pages are kept; the next run continues from here.", file=sys.stderr)
        sys.exit(2)
    finally:
        print(f"requests: {fetcher.fetched} fetched, {fetcher.from_cache} from cache")


def run(fetcher: Fetcher, args) -> None:
    competitions = load_competitions()
    if args.competitions:
        unknown = set(args.competitions) - set(competitions.competition_id)
        if unknown:
            sys.exit(f"unknown competitions: {sorted(unknown)}")
        competitions = competitions[competitions.competition_id.isin(args.competitions)]
    since = args.since or default_since()
    until = args.until or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    print(f"scope: {len(competitions)} competitions, matches {since} to {until}", flush=True)
    scope = collect_scope(fetcher, competitions, since, until, args.offline)
    if args.nations:
        add_nations(fetcher, scope, args.nations, args.offline)
    print(f"{len(scope.games)} finished matches in range", flush=True)
    if not args.offline:
        fetch_reports(fetcher, [g["game_id"] for _, _, g in scope.games], args.max_requests, args.refetch)

    tables = build_tables(fetcher, scope)
    known = set(pd.read_csv(TMD_DIR / "players.csv.gz", usecols=["player_id"]).player_id)
    lineups = tables["game_lineups"]
    # Profiles only for players who played: unused substitutes never enter a rating.
    played = tables["appearances"]
    new_players = sorted(set(played.player_id) - known) if not played.empty else []
    if new_players and not args.offline and not args.no_players:
        fetch_players(fetcher, new_players, args.max_requests)
    profiles, player_failures = [], []
    for player_id in new_players:
        text = read_cached(fetcher, player_key(player_id))
        if text is None:
            continue
        try:
            profiles.append(parse_player(text, player_id))
        except ParseError as exc:
            player_failures.append(str(exc))
    players = pd.DataFrame(profiles, columns=["player_id", "name", "position", "sub_position", "date_of_birth",
                                              "country_of_citizenship"])
    players = pd.concat([players, players_from_reports(lineups, set(new_players) - set(players.player_id))],
                        ignore_index=True)
    all_positions = pd.concat([pd.read_csv(TMD_DIR / "players.csv.gz", usecols=["player_id", "sub_position"]),
                               players[["player_id", "sub_position"]]])
    tables["game_lineups"] = fill_positions(lineups, all_positions)
    tables["players"] = players
    write_tables(tables)
    summarise(scope, tables, player_failures, len(new_players))


CATEGORY = {"Goalkeeper": "Goalkeeper", "Centre-Back": "Defender", "Left-Back": "Defender",
            "Right-Back": "Defender", "Defensive Midfield": "Midfield", "Central Midfield": "Midfield",
            "Attacking Midfield": "Midfield", "Left Midfield": "Midfield", "Right Midfield": "Midfield",
            "Left Winger": "Attack", "Right Winger": "Attack", "Second Striker": "Attack", "Centre-Forward": "Attack"}


def players_from_reports(lineups: pd.DataFrame, player_ids: set) -> pd.DataFrame:
    """Minimal rows for new players without a fetched profile: the longest name the reports
    give (starters only show a short name) and the position they were most often listed
    at on the bench. No birth date or citizenship."""
    rows = []
    listed = lineups[lineups.player_id.isin(player_ids)]
    for player_id, group in listed.groupby("player_id"):
        names = group.player_name.dropna()
        bench = group.loc[group["type"] == "substitutes", "position"].dropna()
        sub_position = bench.mode().iloc[0] if not bench.empty else None
        rows.append({"player_id": player_id, "name": max(names, key=len) if not names.empty else None,
                     "position": CATEGORY.get(sub_position), "sub_position": sub_position,
                     "date_of_birth": None, "country_of_citizenship": None})
    if rows:
        print(f"  {len(rows)} new players without a profile: name and bench position from the reports")
    return pd.DataFrame(rows, columns=["player_id", "name", "position", "sub_position", "date_of_birth",
                                       "country_of_citizenship"])


def summarise(scope: Scope, tables: dict, player_failures: list, new_players: int) -> None:
    games = tables["games"]
    failures = tables["failures"]
    wanted = len(scope.games)
    print(f"\nSUMMARY {scope.since}..{scope.until}: {len(games)}/{wanted} matches parsed, "
          f"{len(failures)} unparsed, {wanted - len(games) - len(failures)} not fetched yet")
    if games.empty:
        return
    issues = Counter(i for v in games.data_issue.dropna() for i in v.split(","))
    print(f"  with line-ups {int(games.has_lineups.sum())}, appearances {len(tables['appearances'])}, "
          f"newest match {games.date.max()}")
    print(f"  data issues: {dict(issues) or 'none'}")
    print(f"  new players: {len(tables['players'])}/{new_players} profiles parsed"
          + (f", {len(player_failures)} unparsed" if player_failures else ""))
    for competition_id, game_id, message in failures[:20]:
        print(f"  [unparsed] {competition_id} {game_id}: {message}")


if __name__ == "__main__":
    main()
