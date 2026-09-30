"""Market Tools Odds API snapshot tests. No provider HTTP."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_snapshot.adapter import (
    build_event_cards,
    build_preview,
    combine_parlay,
    compare_groups,
    flatten_odds,
    parlay_conflict,
    parlay_duplicate,
)
from market_snapshot.bounded_fetch import redact_url
from market_snapshot.contracts import american_to_decimal, decimal_to_american
from market_snapshot.cost_estimate import estimate_monthly
from market_snapshot.leagues import LEAGUES


class RedactTests(unittest.TestCase):
    def test_redact_does_not_keep_api_key(self):
        url = "https://api.the-odds-api.com/v4/sports/?apiKey=secret-value"
        red = redact_url(url)
        self.assertNotIn("secret-value", red)
        self.assertIn("REDACTED", red)


class ConversionTests(unittest.TestCase):
    def test_odds_conversion_and_missing_price(self):
        self.assertEqual(american_to_decimal(100), 2.0)
        self.assertEqual(american_to_decimal(-110), round(1.0 + 100 / 110, 4))
        self.assertIsNone(american_to_decimal(None))
        self.assertEqual(decimal_to_american(2.0), 100)


class CompareTests(unittest.TestCase):
    def test_compare_groups_same_event_market_selection_line_period(self):
        rows = flatten_odds("americanfootball_nfl", "NFL", [
            {
                "id": "e1",
                "commence_time": "2026-10-04T17:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
                "bookmakers": [
                    {"key": "draftkings", "title": "DraftKings", "last_update": "2026-09-30T12:00:00Z",
                     "markets": [{"key": "h2h", "outcomes": [{"name": "Home", "price": -120}, {"name": "Away", "price": 100}]}]},
                    {"key": "fanduel", "title": "FanDuel", "last_update": "2026-09-30T12:01:00Z",
                     "markets": [{"key": "h2h", "outcomes": [{"name": "Home", "price": -118}, {"name": "Away", "price": None}]}]},
                ],
            }
        ])
        groups = compare_groups(rows)
        home = next(g for g in groups if g["selection"] == "Home")
        self.assertEqual(home["book_count"], 2)
        self.assertTrue(any(p["best_listed"] for p in home["prices"]))
        away = next(g for g in groups if g["selection"] == "Away")
        self.assertEqual(away["book_count"], 1)
        self.assertIn("FanDuel", away["missing_books"])


class SoccerGolfTests(unittest.TestCase):
    def test_soccer_draw_and_separate_lines(self):
        rows = flatten_odds("soccer_epl", "England Premier League", [{
            "id": "s1",
            "commence_time": "2026-10-04T14:00:00Z",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "bookmakers": [{
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Arsenal", "price": -140},
                        {"name": "Chelsea", "price": 320},
                        {"name": "Draw", "price": 260},
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "price": -110, "point": 2.5},
                        {"name": "Over", "price": 120, "point": 3.5},
                    ]},
                ],
            }],
        }])
        cards = build_event_cards(rows)
        h2h = cards[0]["books"][0]["h2h"]
        self.assertIn("draw", h2h)
        groups = compare_groups(rows)
        overs = [g for g in groups if g["selection"] == "Over"]
        self.assertEqual(len(overs), 2)

    def test_golf_outright_player_rows(self):
        rows = flatten_odds("golf_masters_tournament_winner", "Masters Tournament Winner", [{
            "id": "g1",
            "commence_time": "2027-04-08T12:00:00Z",
            "home_team": "Masters",
            "away_team": None,
            "bookmakers": [{
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [{"key": "outrights", "outcomes": [{"name": "Scottie Scheffler", "price": 400}]}],
            }],
        }])
        self.assertEqual(rows[0]["player"], "Scottie Scheffler")
        self.assertEqual(rows[0]["kind"], "outright")
        card = build_event_cards(rows)[0]
        self.assertEqual(card["books"][0]["outrights"][0]["player"], "Scottie Scheffler")


class ParlayTests(unittest.TestCase):
    def test_same_game_suppresses_combined_odds(self):
        result = combine_parlay([
            {"event_id": "e1", "american": -110, "selection": "A", "market": "h2h", "period": "game"},
            {"event_id": "e1", "american": -110, "selection": "B", "market": "spreads", "period": "game", "line": -3.5},
        ])
        self.assertFalse(result["ok"])
        self.assertTrue(result["combined_suppressed"])
        self.assertTrue(result["same_game"])

    def test_cross_game_is_illustrative_not_a_quote(self):
        cross = combine_parlay([
            {"event_id": "e1", "american": 150, "selection": "A", "market": "h2h", "period": "game", "bookmaker": "DraftKings"},
            {"event_id": "e2", "american": -110, "selection": "B", "market": "h2h", "period": "game", "bookmaker": "FanDuel"},
        ])
        self.assertTrue(cross["ok"])
        self.assertFalse(cross["bookmaker_confirmed_quote"])
        self.assertIn("not a sportsbook quote", cross["label"].lower())
        self.assertTrue(cross["mixed_books"])

    def test_conflict_and_duplicate(self):
        a = {"event_id": "e1", "market": "h2h", "selection": "Home", "period": "game", "line": None, "player": ""}
        b = {"event_id": "e1", "market": "h2h", "selection": "Away", "period": "game", "line": None, "player": ""}
        self.assertTrue(parlay_conflict(a, b))
        self.assertTrue(parlay_duplicate(a, dict(a)))
        blocked = combine_parlay([{**a, "american": -110}, {**b, "american": 120}])
        self.assertTrue(blocked.get("conflict"))


class PreviewTests(unittest.TestCase):
    def test_preview_fixture_and_monthly_estimate(self):
        payloads = {
            "sports": [{"key": "americanfootball_nfl", "title": "NFL"}],
            "odds": {
                "americanfootball_nfl": [{
                    "id": "e1",
                    "commence_time": "2026-10-04T17:00:00Z",
                    "home_team": "Home",
                    "away_team": "Away",
                    "bookmakers": [{
                        "key": "draftkings",
                        "title": "DraftKings",
                        "last_update": "2026-09-30T12:00:00Z",
                        "markets": [
                            {"key": "h2h", "outcomes": [{"name": "Home", "price": -130}, {"name": "Away", "price": 110}]},
                            {"key": "spreads", "outcomes": [{"name": "Home", "price": -110, "point": -3.5}]},
                            {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 44.5}]},
                        ],
                    }],
                }],
                "americanfootball_ncaaf": [],
                "baseball_mlb": [],
            },
            "player_props": {
                "id": "e1",
                "sport_key": "americanfootball_nfl",
                "sport_title": "NFL",
                "commence_time": "2026-10-04T17:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
                "bookmakers": [{
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [{
                        "key": "player_pass_tds",
                        "last_update": "2026-09-30T12:00:00Z",
                        "outcomes": [{"name": "Over", "description": "QB One", "price": -150, "point": 1.5}],
                    }],
                }],
            },
            "index": {
                "imported_at": "2026-09-30T12:00:00+00:00",
                "http_requests_used": 6,
                "credits_used_from_headers": 10,
                "player_props_note": "player-prop sample returned",
                "player_props": {"requested_market": "player_pass_tds"},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "latest_payloads.json").write_text(json.dumps(payloads))
            preview = build_preview(root=root)
        self.assertFalse(preview["live_data"])
        self.assertEqual(preview["notice"], "Preview • Saved odds • Not live.")
        nfl = preview["coverage_by_title"]["NFL"]
        self.assertEqual(nfl["markets"]["h2h"], "present")
        self.assertEqual(preview["coverage_by_title"]["NCAAF"]["event_count"], 0)
        self.assertEqual(preview["coverage_by_title"]["NCAAB"]["status"], "documented_not_in_catalog")
        self.assertEqual(preview["player_props"][0]["player"], "QB One")
        self.assertEqual(preview["player_props"][0]["market_label"], "Pass Touchdowns")
        self.assertTrue(preview["events"])
        est = estimate_monthly()
        self.assertGreater(est["monthly_with_reserve"], 20000)
        cheapest = est["cheapest_sufficient_under_149"]
        self.assertIsNotNone(cheapest)
        self.assertLess(cheapest["price_usd"], 149)
        self.assertGreaterEqual(cheapest["credits_per_month"], est["monthly_with_reserve"])
        self.assertEqual(len(LEAGUES), 20)


if __name__ == "__main__":
    unittest.main()
