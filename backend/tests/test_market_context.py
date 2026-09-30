"""Labeled fixtures for Market Tools scores, weather, injuries, and matching."""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "market_snapshot" / "fixtures" / "context_labeled.json"
NOW = datetime(2026, 9, 30, 16, 5, tzinfo=timezone.utc)


class ContextMatchingTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        os.environ["MARKET_TOOLS_CONTEXT_FIXTURES"] = "1"
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_CONTEXT_COLLECT", None)

    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_CONTEXT_FIXTURES", None)

    def _fixtures(self):
        return json.loads(FIXTURE.read_text())

    def test_unique_id_match_and_ambiguous_reject(self):
        from market_snapshot.context import match_score_row, score_block, status_from_oddsapi

        event = {
            "id": "oddsapi:americanfootball_nfl:abcabcabcabcabcabcabcabcabcabcab",
            "sport_key": "americanfootball_nfl",
            "home_team": "Cleveland Browns",
            "away_team": "Pittsburgh Steelers",
            "commence_time": "2026-10-02T00:15:00Z",
        }
        row = {
            "id": "abcabcabcabcabcabcabcabcabcabcab",
            "sport_key": "americanfootball_nfl",
            "home_team": "Cleveland Browns",
            "away_team": "Pittsburgh Steelers",
            "commence_time": "2026-10-02T00:15:00Z",
            "completed": False,
            "scores": None,
        }
        self.assertEqual(match_score_row(event, [row])["id"], row["id"])
        twin = dict(row)
        self.assertIsNone(match_score_row(event, [row, twin]))
        mismatch = dict(row, home_team="Buffalo Bills")
        self.assertIsNone(match_score_row(event, [mismatch]))
        self.assertEqual(status_from_oddsapi(row), "scheduled")
        block = score_block(event, row, retrieved_at="2026-09-30T16:00:00Z", now=NOW)
        self.assertIsNone(block["home_score"])
        self.assertIsNone(block["clock"])
        self.assertIsNone(block["period"])

    def test_status_matrix_and_no_wall_clock_inference(self):
        from market_snapshot.context import attach_event_context, extract_team_scores, status_from_oddsapi

        self.assertEqual(status_from_oddsapi({"completed": True, "scores": []}), "final")
        self.assertEqual(status_from_oddsapi({"completed": False, "scores": [{"name": "A", "score": "1"}]}), "in_progress")
        self.assertEqual(status_from_oddsapi({"status": "postponed", "completed": False, "scores": None}), "postponed")
        late = {
            "id": "oddsapi:americanfootball_nfl:late",
            "sport_key": "americanfootball_nfl",
            "home_team": "A",
            "away_team": "B",
            "commence_time": "2026-09-30T12:00:00Z",
        }
        attached = attach_event_context(late, {
            "retrieved_at": "2026-09-30T16:00:00Z",
            "scores": [{
                "id": "late",
                "sport_key": "americanfootball_nfl",
                "home_team": "A",
                "away_team": "B",
                "commence_time": "2026-09-30T12:00:00Z",
                "completed": False,
                "scores": None,
            }],
            "weather_by_home": {},
            "injuries": [],
        }, now=NOW)
        self.assertEqual(attached["context"]["score"]["status"], "scheduled")
        self.assertIsNone(attached["context"]["score"]["clock"])
        self.assertIsNone(extract_team_scores({"home_team": "A", "away_team": "B", "scores": None})[0])

    def test_timezone_date_boundary(self):
        from market_snapshot.context import schedule_block

        sched = schedule_block("2026-10-05T03:30:00Z")
        self.assertEqual(sched["commence_time_utc"], "2026-10-05T03:30:00Z")
        self.assertTrue(sched["crosses_local_date"])
        self.assertEqual(sched["utc_date"], "2026-10-05")
        self.assertEqual(sched["local_date"], "2026-10-04")
        self.assertEqual(sched["timezone_abbreviation"], "EDT")

    def test_labeled_fixtures_edge_cases(self):
        from market_snapshot.context import attach_context

        fixtures = self._fixtures()
        preview = {"events": [], "player_props": []}
        attach_context(preview, collected={}, fixtures=fixtures, now=NOW)
        by_label = {e.get("fixture_label"): e for e in preview["events"]}
        self.assertEqual(by_label["CTX_SCHEDULED"]["context"]["score"]["status"], "scheduled")
        self.assertIsNone(by_label["CTX_SCHEDULED"]["context"]["score"]["home_score"])
        self.assertEqual(by_label["CTX_IN_PROGRESS"]["context"]["score"]["status"], "in_progress")
        self.assertEqual(by_label["CTX_IN_PROGRESS"]["context"]["score"]["home_score"], 3)
        self.assertEqual(by_label["CTX_IN_PROGRESS"]["context"]["score"]["away_score"], 2)
        self.assertIsNone(by_label["CTX_IN_PROGRESS"]["context"]["score"]["clock"])
        self.assertEqual(by_label["CTX_IN_PROGRESS"]["context"]["score"]["freshness"], "fresh")
        self.assertEqual(by_label["CTX_FINAL"]["context"]["score"]["status"], "final")
        self.assertEqual(by_label["CTX_POSTPONED"]["context"]["score"]["status"], "postponed")
        self.assertEqual(by_label["CTX_DELAYED"]["context"]["score"]["status"], "delayed")
        self.assertEqual(by_label["CTX_CANCELED"]["context"]["score"]["status"], "canceled")
        self.assertEqual(by_label["CTX_STALE"]["context"]["score"]["freshness"], "stale")
        self.assertEqual(by_label["CTX_WEATHER_HORIZON"]["context"]["weather"]["label"], "Forecast not yet available.")
        self.assertEqual(by_label["CTX_INDOOR"]["context"]["weather"]["label"], "Indoor")
        self.assertEqual(by_label["CTX_MISSING_SCORE"]["context"]["score"]["home_score"], None)
        injuries = by_label["CTX_INJURY"]["context"]["injuries"]
        self.assertEqual(len(injuries), 2)
        report = next(r for r in injuries if r["certainty"] == "report")
        confirmed = next(r for r in injuries if r["certainty"] == "confirmed")
        self.assertEqual(report["source_wording"], "Questionable — ankle, per team report")
        self.assertEqual(confirmed["certainty_label"], "Confirmed availability")
        self.assertEqual(report["projection_adjustment"], "not_applied")
        weather = by_label["CTX_IN_PROGRESS"]["context"]["weather"]
        self.assertEqual(weather["kind"], "forecast")
        self.assertEqual(weather["temperature"], 82)
        self.assertEqual(weather["precipitation_probability"], 15)
        self.assertTrue(weather["not_observation"])
        self.assertTrue(weather["venue_verified"])
        self.assertFalse(by_label["CTX_FINAL"]["context"]["venue"]["verified"])
        self.assertEqual(by_label["CTX_FINAL"]["context"]["weather"]["kind"], "unavailable")

    def test_old_result_not_attached_to_future_matchup(self):
        from market_snapshot.context import attach_context, match_score_row

        future = {
            "id": "oddsapi:baseball_mlb:futurephiibraves000000000001",
            "sport_key": "baseball_mlb",
            "selector": "mlb",
            "home_team": "Atlanta Braves",
            "away_team": "Philadelphia Phillies",
            "commence_time": "2026-09-30T23:10:00Z",
            "kind": "game",
            "books": [{"bookmaker": "DraftKings"}],
        }
        completed = {
            "id": "08d921971324aaaaaaaaaaaaaaaaaaaaaa",
            "sport_key": "baseball_mlb",
            "sport_title": "MLB",
            "home_team": "Atlanta Braves",
            "away_team": "Philadelphia Phillies",
            "commence_time": "2026-09-29T18:16:21Z",
            "completed": True,
            "scores": [
                {"name": "Atlanta Braves", "score": "5"},
                {"name": "Philadelphia Phillies", "score": "3"},
            ],
            "last_update": "2026-09-30T10:21:31Z",
        }
        self.assertIsNone(match_score_row(future, [completed]))
        preview = {"events": [future], "player_props": []}
        attach_context(
            preview,
            collected={"retrieved_at": "2026-09-30T16:38:31Z", "scores": [completed], "weather_by_home": {}},
            fixtures={"demo_events": [], "scores": [], "weather_by_home": {}, "injuries": []},
            now=NOW,
        )
        score_only = [e for e in preview["events"] if e.get("saved_result")]
        self.assertEqual(len(score_only), 1)
        self.assertEqual(score_only[0]["odds_notice"], "Odds unavailable.")
        self.assertEqual(score_only[0]["context"]["score"]["home_score"], 5)
        self.assertEqual(score_only[0]["context"]["score"]["away_score"], 3)
        self.assertEqual(score_only[0]["last_update"], "2026-09-30T10:21:31Z")
        future_row = next(e for e in preview["events"] if e["id"] == future["id"])
        self.assertIsNone(future_row["context"]["score"]["home_score"])
        self.assertNotEqual(future_row["id"], score_only[0]["id"])

    def test_unverified_home_stadium_does_not_show_weather(self):
        from market_snapshot.context import venue_record, weather_block

        event = {"home_team": "Atlanta Braves", "commence_time": "2026-09-30T18:00:00Z"}
        self.assertFalse(venue_record(event)["verified"])
        block = weather_block(
            event,
            {
                "Atlanta Braves": {
                    "lat": 33.8908,
                    "lon": -84.4678,
                    "periods": [{
                        "startTime": "2026-09-30T18:00:00+00:00",
                        "endTime": "2026-09-30T19:00:00+00:00",
                        "temperature": 82,
                        "temperatureUnit": "F",
                    }],
                }
            },
            retrieved_at="2026-09-30T16:38:31Z",
            now=NOW,
        )
        self.assertEqual(block["kind"], "unavailable")
        self.assertFalse(block["venue_verified"])

    def test_verified_venue_reuses_saved_nws_forecast(self):
        from market_snapshot.context import weather_block

        event = {
            "home_team": "Atlanta Braves",
            "commence_time": "2026-09-30T18:00:00Z",
            "event_venue": {
                "verified": True,
                "source": "Authoritative labeled schedule for this event",
                "name": "Truist Park",
                "lat": 33.8908,
                "lon": -84.4678,
                "city": "Atlanta, GA",
                "neutral_site": False,
                "indoor": False,
                "roof": "outdoor",
            },
        }
        block = weather_block(
            event,
            {
                "Atlanta Braves": {
                    "lat": 33.8908,
                    "lon": -84.4678,
                    "retrieved_at": "2026-09-30T16:38:31Z",
                    "source_updated_at": "2026-09-30T12:47:11Z",
                    "periods": [{
                        "startTime": "2026-09-30T18:00:00+00:00",
                        "endTime": "2026-09-30T19:00:00+00:00",
                        "temperature": 77,
                        "temperatureUnit": "F",
                        "windSpeed": "6 mph",
                        "windDirection": "W",
                        "shortForecast": "Mostly Sunny",
                        "probabilityOfPrecipitation": {"value": 5},
                    }],
                }
            },
            retrieved_at="2026-09-30T16:38:31Z",
            now=NOW,
        )
        self.assertEqual(block["kind"], "forecast")
        self.assertTrue(block["not_observation"])
        self.assertTrue(block["venue_verified"])
        self.assertEqual(block["temperature"], 77)
        self.assertEqual(block["venue"]["source"], "Authoritative labeled schedule for this event")

    def test_injury_board_source_link_only(self):
        from market_snapshot.injury_sources import INJURIES, injury_board_for_selector

        self.assertFalse(INJURIES["live_feed_connected"])
        self.assertFalse(INJURIES["nfl"]["automated_collection_commercial_display"])
        self.assertFalse(INJURIES["nba"]["automated_collection_commercial_display"])
        self.assertEqual(INJURIES["public_source_downloads_this_assignment"], 0)
        self.assertEqual(INJURIES["nfl"]["classification"], "source_link_only")
        self.assertEqual(INJURIES["nba"]["classification"], "source_link_only")
        nfl = injury_board_for_selector("nfl")
        self.assertEqual(nfl["message"], "Live injury feed not connected")
        self.assertFalse(nfl["live_feed_connected"])
        self.assertEqual(nfl["reports"], [])
        self.assertTrue(any("nfl.com/injuries" in (row["url"] or "") for row in nfl["official_links"]))
        nba = injury_board_for_selector("nba")
        self.assertTrue(any("official.nba.com" in (row["url"] or "") for row in nba["official_links"]))
        self.assertIsNone(injury_board_for_selector("mlb"))

    def test_restore_saved_preview_after_fixture(self):
        from market_snapshot.adapter import load_payloads
        from market_snapshot.cache import replace_from_payloads, reset_for_tests, restore_saved_preview

        try:
            load_payloads()
        except FileNotFoundError:
            self.skipTest("No saved Odds API snapshot")
        os.environ.pop("MARKET_TOOLS_CONTEXT_FIXTURES", None)
        reset_for_tests()
        fixture = json.loads(
            (Path(__file__).resolve().parents[1] / "market_snapshot" / "fixtures" / "fixture_a_baseline.json").read_text()
        )
        replaced = replace_from_payloads(fixture, fixture_label="FIXTURE_A_BASELINE", source="fixture")
        self.assertTrue(any(e.get("home_team") == "Fixture Home" for e in replaced.get("events") or []))
        restored = restore_saved_preview()
        self.assertEqual(restored.get("ingest_source"), "restore_saved_preview")
        ids = {e.get("id") for e in restored.get("events") or []}
        self.assertNotIn("oddsapi:americanfootball_nfl:ffffffffffffffffffffffffffffffff", ids)
        self.assertTrue(any((e.get("books") or []) and e.get("selector") == "nfl" for e in restored.get("events") or []))

    def test_cost_plan_before_http_and_collect_off(self):
        from market_snapshot.context_collect import collect_bounded
        from market_snapshot.context_sources import SCHEDULED_FETCH_ENABLED
        from market_snapshot.flags import context_collect_enabled

        plan = collect_bounded(execute=False)
        self.assertFalse(plan["executed"])
        self.assertEqual(plan["plan"]["planned_http_total"], 4)
        self.assertEqual(plan["plan"]["planned_odds_credits_max"], 4)
        self.assertLessEqual(plan["plan"]["planned_odds_credits_max"], 10)
        self.assertFalse(SCHEDULED_FETCH_ENABLED)
        self.assertFalse(context_collect_enabled())

    def test_consumer_scores_when_context_present(self):
        from market_snapshot.consumers import assistant_event_row, event_card_to_mobile_game

        ev = {
            "id": "oddsapi:baseball_mlb:x",
            "home_team": "Atlanta Braves",
            "away_team": "Philadelphia Phillies",
            "commence_time": "2026-09-30T18:00:00Z",
            "selector": "mlb",
            "books": [],
            "context": {
                "schedule": {"commence_time_utc": "2026-09-30T18:00:00Z"},
                "score": {
                    "status": "in_progress",
                    "status_display": "In progress",
                    "home_score": 3,
                    "away_score": 2,
                    "period": None,
                    "clock": None,
                    "source_updated_at": "2026-09-30T16:04:30Z",
                    "retrieved_at": "2026-09-30T16:00:00Z",
                },
                "weather": {"kind": "forecast", "temperature": 82},
                "injuries": [],
            },
        }
        mobile = event_card_to_mobile_game(ev)
        self.assertEqual(mobile["live_score"], "available")
        self.assertEqual(mobile["home_score"], 3)
        self.assertIsNone(mobile["clock"])
        self.assertFalse(mobile["installed_mobile_tested"])
        row = assistant_event_row(ev, "MLB")
        self.assertEqual(row["away_score"], 2)
        self.assertEqual(row["live_score"], "available")


if __name__ == "__main__":
    unittest.main()
