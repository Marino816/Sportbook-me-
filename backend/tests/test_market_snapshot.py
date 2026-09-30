"""Market Tools Odds API snapshot tests. No provider HTTP."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_snapshot.adapter import build_preview, combine_parlay, compare_groups, flatten_odds
from market_snapshot.bounded_fetch import redact_url
from market_snapshot.contracts import american_to_decimal, decimal_to_american
from market_snapshot.cost_estimate import estimate_monthly


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
        away = next(g for g in groups if g["selection"] == "Away")
        self.assertEqual(away["book_count"], 1)
        self.assertIn("FanDuel", away["missing_books"])


class ParlayTests(unittest.TestCase):
    def test_parlay_is_analytical_and_flags_same_game(self):
        result = combine_parlay([
            {"event_id": "e1", "american": -110, "selection": "A"},
            {"event_id": "e1", "american": -110, "selection": "B"},
        ])
        self.assertTrue(result["ok"])
        self.assertFalse(result["bookmaker_confirmed_quote"])
        self.assertTrue(result["same_game"])
        self.assertIn("same-game", (result["same_game_warning"] or "").lower())
        cross = combine_parlay([
            {"event_id": "e1", "american": 150, "selection": "A"},
            {"event_id": "e2", "american": -110, "selection": "B"},
        ])
        self.assertFalse(cross["same_game"])
        empty = combine_parlay([{"event_id": "e1", "american": None, "selection": "A"}])
        self.assertFalse(empty["ok"])


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
        self.assertEqual(preview["label"], "Snapshot")
        self.assertTrue(preview["coverage"]["NFL"]["featured_h2h"])
        self.assertEqual(preview["coverage"]["NCAAF"]["event_count"], 0)
        self.assertEqual(preview["player_props"][0]["player"], "QB One")
        est = estimate_monthly()
        self.assertGreater(est["monthly_with_reserve"], 500)
        cheapest = est["cheapest_sufficient_under_149"]
        self.assertIsNotNone(cheapest)
        self.assertLess(cheapest["price_usd"], 149)
        self.assertGreaterEqual(cheapest["credits_per_month"], est["monthly_with_reserve"])


if __name__ == "__main__":
    unittest.main()
