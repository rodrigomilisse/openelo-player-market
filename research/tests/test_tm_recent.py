"""Parser and minutes tests for tm_recent.py on saved Transfermarkt pages (no network).

    cd research && .venv/bin/python -m unittest discover -s tests
"""

import copy
import gzip
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tm_recent  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "tm"


def page(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes()).decode("utf-8")


def report(game_id: int) -> dict:
    return tm_recent.parse_report(page(f"game_{game_id}"), game_id)


class ScheduleTest(unittest.TestCase):
    def test_finished_games_with_dates_and_clubs(self):
        games = tm_recent.parse_schedule(page("schedule_FAC_2026"))
        self.assertEqual(len(games), 40)
        by_id = {g["game_id"]: g for g in games}
        self.assertEqual(by_id[5084017], {"game_id": 5084017, "date": "2026-11-07", "result": "4:5on pens",
                                          "home_club_id": 2962, "away_club_id": 1045})
        # a row that shares its date with the row above still gets the date
        self.assertEqual(by_id[5084007]["date"], "2026-11-06")


class ReportTest(unittest.TestCase):
    def test_second_leg_matches_the_dataset(self):
        """Bayern 1-1 PSG, CL semi-final 2nd leg; expected values are the main dataset's."""
        r = report(4814380)
        self.assertEqual(r["round"], "Semi-Finals 2nd Leg")
        self.assertEqual((r["teams"]["home"]["id"], r["teams"]["away"]["id"]), (27, 583))
        self.assertEqual((r["home_goals"], r["away_goals"], r["extra_time"], r["length"]), (1, 1, False, 90))
        self.assertEqual(r["stadium"], "Allianz Arena")
        self.assertEqual(sum(p["starter"] for p in r["lineups"]), 22)
        rows, issues = tm_recent.derive(r)
        self.assertEqual(issues, [])
        by_id = {row["player_id"]: row for row in rows}
        self.assertEqual(len(rows), 30)  # unused substitutes get no appearance
        expected = {  # player: (minutes, goals, assists, yellow, red)
            196357: (68, 0, 0, 1, 0),    # Tah, off at 68
            503482: (22, 0, 0, 0, 0),    # Kim, on at 68
            424204: (23, 0, 1, 0, 0),    # Davies, on at 67, assist
            132098: (90, 1, 0, 0, 0),    # Kane, goal at 90+4
            502670: (90, 0, 1, 1, 0),    # Kvaratskhelia
            288230: (65, 1, 0, 0, 0),    # Dembélé
            1075147: (5, 0, 0, 0, 0),    # Karl, on at 85
        }
        for player_id, values in expected.items():
            row = by_id[player_id]
            self.assertEqual((row["minutes"], row["goals"], row["assists"], row["yellow"], row["red"]), values,
                             player_id)

    def test_half_time_substitution_counts_at_45(self):
        rows, _ = tm_recent.derive(report(4626170))
        minutes = {row["player_id"]: row["minutes"] for row in rows}
        self.assertEqual(minutes[356141], 45)  # Kamada, off at half time
        self.assertEqual(minutes[744149], 17)  # Wharton, on at half time, off at 62

    def test_extra_time(self):
        r = report(5084004)
        self.assertEqual((r["extra_time"], r["penalties"], r["length"]), (True, False, 120))
        rows, issues = tm_recent.derive(r)
        self.assertEqual(issues, [])
        self.assertTrue(all(row["minutes"] <= 120 for row in rows))
        self.assertIn(120, {row["minutes"] for row in rows})

    def test_penalty_shootout(self):
        r = report(5084017)
        self.assertEqual((r["penalties"], r["length"], r["score_line"]), (True, 120, (4, 5)))
        self.assertEqual((r["home_goals"], r["away_goals"]), (2, 2))  # after extra time
        self.assertEqual(len(r["shootout"]), 10)
        game, _, appearances, events, issues = tm_recent.tables_for(r, "FAC", 2026, "domestic_cup", None)
        self.assertEqual(issues, [])
        # the dataset's convention: scored kicks are added to the score and listed as events
        self.assertEqual((game["home_club_goals"], game["away_club_goals"]), (4, 5))
        self.assertEqual(sum(e["type"] == "Shootout" and e["description"] == "Scored" for e in events), 5)
        self.assertTrue(appearances)

    def test_broken_lineup_is_flagged_and_gets_no_minutes(self):
        r = copy.deepcopy(report(4814380))
        r["lineups"] = [p for p in r["lineups"] if p["player_id"] != 17259]  # drop a starter
        game, lineups, appearances, _, issues = tm_recent.tables_for(r, "CL", 2025, "international_cup", None)
        self.assertIn("starters_not_11", issues)
        self.assertIn("starters_not_11", game["data_issue"])
        self.assertEqual(appearances, [])
        self.assertTrue(lineups)

    def test_teams_must_match_the_schedule(self):
        r = report(4814380)
        row = {"date": "2026-05-06", "home_club_id": 583, "away_club_id": 27}
        game, *_ = tm_recent.tables_for(r, "CL", 2025, "international_cup", row)
        self.assertIn("teams_differ_from_schedule", game["data_issue"])

    def test_a_page_that_is_not_a_report_fails_loudly(self):
        with self.assertRaises(tm_recent.ParseError):
            tm_recent.parse_report(page("player_1075147"), 1)


class PlayerTest(unittest.TestCase):
    def test_profile(self):
        self.assertEqual(tm_recent.parse_player(page("player_1075147"), 1075147), {
            "player_id": 1075147, "name": "Lennart Karl", "position": "Midfield",
            "sub_position": "Attacking Midfield", "date_of_birth": "2008-02-22",
            "country_of_citizenship": "Germany"})


if __name__ == "__main__":
    unittest.main()
