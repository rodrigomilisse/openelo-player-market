import datetime as dt
import os

import psycopg
import pytest

from apisports_loader import db, jobs
from apisports_loader.client import Client, Fatal
from apisports_loader.fetcher import Fetcher

URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@/loader_test?host=/tmp&port=5544")


class FakeResponse:
    def __init__(self, body, remaining):
        self._body, self.status_code = body, 200
        self.headers = {"x-ratelimit-requests-remaining": str(remaining), "x-ratelimit-remaining": "9"}

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


class FakeApi:
    """Stands in for API-Football and counts what it is asked."""

    def __init__(self, fixtures, daily=100, errors=None):
        self.fixtures, self.daily, self.errors, self.calls = fixtures, daily, errors or {}, []

    def get(self, url, params, headers, timeout):
        endpoint = url.rsplit("/v3.football.api-sports.io/", 1)[-1].split("/", 3)[-1] if False else url.split("io/")[-1]
        if endpoint == "status":
            return FakeResponse({"errors": self.errors.get("status", []), "response": {
                "requests": {"current": 100 - self.daily, "limit_day": 100}}}, self.daily)
        self.calls.append((endpoint, dict(params)))
        self.daily -= 1
        if endpoint in self.errors:
            return FakeResponse({"errors": self.errors[endpoint], "response": []}, self.daily)
        if endpoint == "fixtures":
            items = [f for f in self.fixtures if all(
                (k == "league" and f["league"]["id"] == v) or (k == "season" and f["league"]["season"] == v)
                or (k == "date" and f["fixture"]["date"].startswith(v)) for k, v in params.items())]
            return FakeResponse({"errors": [], "response": items}, self.daily)
        fid = params["fixture"]
        return FakeResponse({"errors": [], "response": players(fid)}, self.daily)


def fixture(fid, league=39, season=2023, status="FT", date="2024-01-10T20:00:00+00:00"):
    return {"fixture": {"id": fid, "date": date, "status": {"short": status}},
            "league": {"id": league, "season": season, "name": "Premier League", "country": "England", "round": "R1"},
            "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
            "goals": {"home": 2, "away": 1}, "score": {"extratime": {"home": None, "away": None}}}


def players(fid):
    def side(team, base):
        return {"team": {"id": team, "name": "T"}, "players": [
            {"player": {"id": base, "name": f"P{base}"}, "statistics": [{"games": {"minutes": 90, "substitute": False, "position": "M"},
                                                                         "goals": {"total": 1, "assists": 0}}]},
            {"player": {"id": base + 1, "name": f"P{base + 1}"}, "statistics": [{"games": {"minutes": None, "substitute": True},
                                                                                  "goals": {"total": None, "assists": None}}]}]}
    return [side(1, 100), side(2, 200)]


@pytest.fixture
def conn():
    c = psycopg.connect(URL)
    c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    db.migrate(c)
    yield c
    c.close()


def make(conn, api, **kw):
    client = Client(base="https://v3.football.api-sports.io", key="k", session=api, sleep=lambda s: None,
                    max_requests=kw.pop("max_requests", None))
    return Fetcher(conn, client, **kw)


def silent(*a, **k):
    pass


def test_second_run_asks_the_api_for_nothing(conn):
    api = FakeApi([fixture(1), fixture(2), fixture(3)])
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    assert len(api.calls) == 4                      # 1 fixture list + 3 matches
    assert conn.execute("SELECT count(*) FROM appearance").fetchone()[0] == 12
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    assert len(api.calls) == 4                      # nothing new was requested


def test_budget_stops_and_the_next_run_continues_where_it_left_off(conn):
    api = FakeApi([fixture(i) for i in range(1, 6)])
    why = jobs.history(make(conn, api, max_requests=3), {39: "PL"}, [2023], None, log=silent)
    assert "budget" in why and len(api.calls) == 3   # list + 2 matches
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    fetched = [c[1]["fixture"] for c in api.calls if c[0] == "fixtures/players"]
    assert sorted(fetched) == [1, 2, 3, 4, 5] and len(fetched) == len(set(fetched))   # no match twice


def test_max_matches(conn):
    api = FakeApi([fixture(i) for i in range(1, 6)])
    why = jobs.history(make(conn, api), {39: "PL"}, [2023], 2, log=silent)
    assert "requested" in why and len([c for c in api.calls if c[0] == "fixtures/players"]) == 2


def test_daily_quota_reserve(conn):
    api = FakeApi([fixture(i) for i in range(1, 10)], daily=6)
    client = Client(base="https://v3.football.api-sports.io", key="k", session=api, reserve=3, sleep=lambda s: None)
    client.status()
    why = jobs.history(Fetcher(conn, client), {39: "PL"}, [2023], None, log=silent)
    assert "stopped" in why and api.daily == 3      # never dipped below the reserve


def test_plan_block_is_remembered(conn):
    api = FakeApi([fixture(1)], errors={"fixtures": {"plan": "Free plans do not have access to this season"}})
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    assert len(api.calls) == 1                      # the refusal cost one request, once
    jobs.history(make(conn, api, retry_blocked=True), {39: "PL"}, [2023], None, log=silent)
    assert len(api.calls) == 2


def test_suspended_account_is_a_clear_stop(conn):
    api = FakeApi([], errors={"status": {"access": "Your account is suspended"}})
    with pytest.raises(Fatal, match="dedicated static IP"):
        Client(base="https://v3.football.api-sports.io", session=api).status()


def test_refetch_is_the_only_way_to_repeat(conn):
    api = FakeApi([fixture(1)])
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    jobs.history(make(conn, api, refetch=True), {39: "PL"}, [2023], None, log=silent)
    assert len(api.calls) == 4
    assert conn.execute("SELECT count(*) FROM raw_payload").fetchone()[0] == 4   # append-only


def test_recent_open_day_is_asked_again_but_a_finished_day_is_not(conn):
    today = dt.date(2024, 1, 11)
    api = FakeApi([fixture(1, date="2024-01-10T20:00:00+00:00"), fixture(2, status="NS", date="2024-01-11T20:00:00+00:00")])
    jobs.recent(make(conn, api), {39: "PL"}, dt.date(2024, 1, 10), today, log=silent)
    days = [c for c in api.calls if c[0] == "fixtures"]
    assert len(days) == 2
    jobs.recent(make(conn, api), {39: "PL"}, dt.date(2024, 1, 10), today, log=silent)
    days = [c[1]["date"] for c in api.calls if c[0] == "fixtures"]
    assert days.count("2024-01-10") == 1 and days.count("2024-01-11") == 2   # only the open day again


def test_rebuild_needs_no_requests(conn):
    api = FakeApi([fixture(1), fixture(2)])
    jobs.history(make(conn, api), {39: "PL"}, [2023], None, log=silent)
    before = len(api.calls)
    jobs.rebuild(conn, log=silent)
    assert len(api.calls) == before
    assert conn.execute("SELECT count(*) FROM appearance WHERE started").fetchone()[0] == 4


def test_research_import_is_idempotent(conn, tmp_path):
    import sqlite3
    from apisports_loader import research_import
    store = tmp_path / "r.sqlite3"
    lite = sqlite3.connect(store)
    lite.executescript("""
        CREATE TABLE game (game_id INTEGER PRIMARY KEY, date TEXT NOT NULL, national INTEGER NOT NULL);
        CREATE TABLE transfer (player_id INTEGER NOT NULL, date TEXT NOT NULL, fee_eur INTEGER);
        INSERT INTO game VALUES (1, '2026-07-06', 0), (2, '2026-07-05', 0);
        INSERT INTO transfer VALUES (7, '2026-01-01', 100);""")
    lite.commit()
    first = research_import.import_store(conn, store, log=silent)
    assert first["added"] == {"game": 2, "transfer": 1} and first["newest"] == "2026-07-06"
    lite.execute("INSERT INTO game VALUES (3, '2026-07-07', 0)")
    lite.commit()
    second = research_import.import_store(conn, store, log=silent)
    assert second["added"] == {"game": 1, "transfer": 0}       # only the new match
