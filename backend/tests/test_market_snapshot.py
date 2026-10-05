"""Market Tools Odds API snapshot tests. No provider HTTP."""

from __future__ import annotations

import json
import os
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

os.environ.pop("MARKET_TOOLS_CONTEXT_FIXTURES", None)
os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
os.environ.pop("MARKET_TOOLS_CONTEXT_COLLECT", None)


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
        spread = {"event_id": "e1", "market": "spreads", "selection": "Home", "period": "game", "line": -3.5, "player": ""}
        self.assertTrue(parlay_conflict(a, b))
        self.assertFalse(parlay_conflict(a, spread))
        self.assertTrue(parlay_duplicate(a, dict(a)))
        blocked = combine_parlay([{**a, "american": -110}, {**b, "american": 120}])
        self.assertTrue(blocked.get("conflict"))
        compatible = combine_parlay([{**a, "american": -110}, {**spread, "american": -105}])
        self.assertFalse(compatible.get("conflict"))
        self.assertTrue(compatible.get("same_game"))
        self.assertTrue(compatible.get("combined_suppressed"))
        self.assertFalse(compatible.get("ok"))


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
        self.assertEqual(preview["notice"], "Saved odds—not live")
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
        self.assertEqual(preview["fair_odds_label"], "Market-derived fair odds")
        self.assertFalse(preview["refresh"]["continuous_fetch_enabled"])
        self.assertFalse(preview["refresh"]["config"]["browsing_triggers_upstream"])
        fair = preview["events"][0]["books"][0]["fair_h2h"]
        self.assertEqual(fair["label"], "Market-derived fair odds")
        self.assertFalse(fair["sbme_predictive"])


class AnalysisTests(unittest.TestCase):
    def test_fair_complete_set_and_incomplete_unavailable(self):
        from market_snapshot.analysis import fair_from_complete
        complete = fair_from_complete([-110, -110])
        self.assertEqual(complete["label"], "Market-derived fair odds")
        self.assertFalse(complete["sbme_predictive"])
        self.assertEqual(complete["fair_american"], [100, 100])
        self.assertTrue(complete["normalized"])
        self.assertEqual(complete["probability_sum"], 1.0)
        self.assertFalse(complete["includes_bookmaker_margin"])
        self.assertTrue(complete["raw_implied_includes_margin"])
        self.assertIsNone(fair_from_complete([-110]))

    def test_spreads_devig_requires_matching_event_period_line(self):
        from market_snapshot.analysis import attach_fair_to_books
        matched = {
            "id": "e1",
            "books": [{
                "spreads": {
                    "home": {"american": -110, "line": -3.5, "period": "game", "event_id": "e1"},
                    "away": {"american": -110, "line": 3.5, "period": "game", "event_id": "e1"},
                }
            }],
        }
        attach_fair_to_books(matched)
        self.assertIsNotNone(matched["books"][0]["fair_spreads"])
        mixed_line = {
            "id": "e1",
            "books": [{
                "spreads": {
                    "home": {"american": -110, "line": -3.5, "period": "game", "event_id": "e1"},
                    "away": {"american": -110, "line": 7.0, "period": "game", "event_id": "e1"},
                }
            }],
        }
        attach_fair_to_books(mixed_line)
        self.assertIsNone(mixed_line["books"][0]["fair_spreads"])
        mixed_period = {
            "id": "e1",
            "books": [{
                "spreads": {
                    "home": {"american": -110, "line": -3.5, "period": "game", "event_id": "e1"},
                    "away": {"american": -110, "line": 3.5, "period": "1h", "event_id": "e1"},
                }
            }],
        }
        attach_fair_to_books(mixed_period)
        self.assertIsNone(mixed_period["books"][0]["fair_spreads"])

    def test_consensus_dedupes_books_and_keeps_timestamp_range(self):
        from market_snapshot.analysis import consensus_prices
        prices = [
            {"bookmaker_key": "dk", "bookmaker": "DraftKings", "american": -110, "source_timestamp": "2026-09-30T12:00:00Z"},
            {"bookmaker_key": "dk", "bookmaker": "DraftKings", "american": -105, "source_timestamp": "2026-09-30T12:05:00Z"},
            {"bookmaker_key": "fd", "bookmaker": "FanDuel", "american": -120, "source_timestamp": "2026-09-30T12:02:00Z"},
        ]
        cons = consensus_prices(prices)
        self.assertEqual(cons["book_count"], 2)
        self.assertTrue(cons["includes_bookmaker_margin"])
        self.assertFalse(cons["is_complete_distribution"])
        self.assertEqual(cons["settlement_rules"], "unconfirmed")
        self.assertEqual(cons["timestamp_range"]["earliest"], "2026-09-30T12:02:00Z")
        self.assertEqual(cons["timestamp_range"]["latest"], "2026-09-30T12:05:00Z")

    def test_soccer_requires_draw_and_rejects_two_way(self):
        from market_snapshot.analysis import scan_arbitrage
        ts = "2026-09-30T12:00:00Z"
        groups = [
            {"event_id": "s1", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Arsenal",
             "prices": [{"bookmaker_key": "dk", "bookmaker": "DK", "american": 250, "source_timestamp": ts}]},
            {"event_id": "s1", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Chelsea",
             "prices": [{"bookmaker_key": "fd", "bookmaker": "FD", "american": 250, "source_timestamp": ts}]},
        ]
        found = scan_arbitrage(groups, [{"id": "s1", "selector": "soccer"}])
        self.assertEqual(found, [])
        groups.append({
            "event_id": "s1", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Draw",
            "prices": [{"bookmaker_key": "mgm", "bookmaker": "MGM", "american": 250, "source_timestamp": ts}],
        })
        found = scan_arbitrage(groups, [{"id": "s1", "selector": "soccer"}])
        self.assertTrue(found)
        self.assertTrue(found[0]["ok"])
        self.assertGreater(found[0]["discrepancy_pct"], 0)
        self.assertTrue(found[0]["legs"])
        self.assertTrue(found[0]["source_timestamps"])
        self.assertEqual(found[0]["label"], "Historical price discrepancy—not verified live.")
        self.assertFalse(found[0]["executable"])
        self.assertFalse(found[0]["guaranteed_profit"])

    def test_integer_line_push_unsupported_and_stale_timestamps(self):
        from market_snapshot.analysis import scan_arbitrage
        groups = [
            {"event_id": "e1", "market": "totals", "period": "game", "line": 44, "player": "", "selection": "Over",
             "prices": [{"bookmaker_key": "dk", "bookmaker": "DK", "american": 150, "source_timestamp": "2026-09-30T12:00:00Z"}]},
            {"event_id": "e1", "market": "totals", "period": "game", "line": 44, "player": "", "selection": "Under",
             "prices": [{"bookmaker_key": "fd", "bookmaker": "FD", "american": 150, "source_timestamp": "2026-09-30T12:00:00Z"}]},
        ]
        found = scan_arbitrage(groups, [{"id": "e1", "selector": "nfl"}])
        self.assertTrue(found)
        self.assertFalse(found[0]["ok"])
        self.assertIn("Push/void", found[0]["reason"])
        stale = [
            {"event_id": "e2", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Home",
             "prices": [{"bookmaker_key": "dk", "bookmaker": "DK", "american": 150, "source_timestamp": "2026-09-30T10:00:00Z"}]},
            {"event_id": "e2", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Away",
             "prices": [{"bookmaker_key": "fd", "bookmaker": "FD", "american": 150, "source_timestamp": "2026-09-30T13:00:00Z"}]},
        ]
        self.assertEqual(scan_arbitrage(stale, [{"id": "e2", "selector": "nfl"}]), [])

    def test_discrepancy_never_defaults_to_zero_opportunity(self):
        from market_snapshot.analysis import _positive_discrepancy, scan_arbitrage
        self.assertIsNone(_positive_discrepancy(None))
        self.assertIsNone(_positive_discrepancy(1.0))
        self.assertIsNone(_positive_discrepancy(1.2))
        tiny = _positive_discrepancy(0.99995)
        self.assertIsNotNone(tiny)
        self.assertGreater(tiny["discrepancy_pct"], 0)
        self.assertGreaterEqual(tiny["discrepancy_precision"], 2)
        even = _positive_discrepancy(0.5 + 0.5)
        self.assertIsNone(even)
        ts = "2026-09-30T12:00:00Z"
        # -110 / -110 is not an opportunity
        groups = [
            {"event_id": "e3", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Home",
             "prices": [{"bookmaker_key": "dk", "bookmaker": "DK", "american": -110, "source_timestamp": ts}]},
            {"event_id": "e3", "market": "h2h", "period": "game", "line": None, "player": "", "selection": "Away",
             "prices": [{"bookmaker_key": "fd", "bookmaker": "FD", "american": -110, "source_timestamp": ts}]},
        ]
        found = scan_arbitrage(groups, [{"id": "e3", "selector": "nfl", "away_team": "Away", "home_team": "Home"}])
        self.assertTrue(all(not a.get("ok") or a.get("discrepancy_pct", 0) > 0 for a in found))
        self.assertFalse(any(a.get("ok") and a.get("discrepancy_pct") == 0 for a in found))


class SchedulerTests(unittest.TestCase):
    def test_quota_stop_and_single_flight_and_disabled_fetch(self):
        from market_snapshot.scheduler import (
            CONFIG,
            CONTINUOUS_FETCH_ENABLED,
            quota_allows,
            release_flight,
            simulate_usage,
            single_flight,
        )
        self.assertFalse(CONTINUOUS_FETCH_ENABLED)
        self.assertFalse(CONFIG["enabled"])
        self.assertFalse(CONFIG["collection_activated"])
        self.assertFalse(CONFIG["browsing_triggers_upstream"])
        from market_snapshot.scheduler import quota_breakdown
        parts = quota_breakdown()
        self.assertEqual(parts["configured_limit"], parts["effective_collection_stop"])
        self.assertEqual(parts["reserve_held_back_from_collection"], 0)
        self.assertFalse(parts["double_reserve_applied"])
        self.assertGreaterEqual(parts["effective_collection_stop"], parts["modeled_busiest_month"] + parts["contingency_credits"])
        self.assertFalse(quota_allows(1, used_month=CONFIG["monthly_credit_limit"], used_day=0))
        self.assertFalse(quota_allows(1, used_month=0, used_day=CONFIG["daily_credit_limit"]))
        self.assertTrue(quota_allows(10, used_month=100, used_day=10))
        self.assertTrue(quota_allows(1, used_month=parts["modeled_busiest_month"], used_day=0))
        self.assertGreaterEqual(CONFIG["monthly_credit_limit"], 468750)
        key = "nfl|h2h|us|"
        self.assertTrue(single_flight(key))
        self.assertFalse(single_flight(key))
        release_flight(key)
        self.assertTrue(single_flight(key))
        release_flight(key)
        sim = simulate_usage()
        self.assertGreater(sim["scenario_a_pregame"]["monthly_with_reserve"], 0)
        self.assertGreater(sim["scenario_b_faster"]["monthly_with_reserve"], sim["scenario_a_pregame"]["monthly_with_reserve"])
        self.assertFalse(sim["scenario_a_pregame"]["plans"]["coverage_removed_to_fit_59"])
        self.assertEqual(len(sim["full_scope"]["requested_coverage"]["soccer_keys"]), 9)


class CostModelTests(unittest.TestCase):
    def test_full_scope_partitions_hours_and_does_not_drop_coverage_for_59(self):
        from market_snapshot.cost_estimate import HOURS_WEEK, full_scope_cost
        from market_snapshot.leagues import LEAGUES
        full = full_scope_cost()
        self.assertEqual(full["requested_coverage"]["league_count"], len(LEAGUES))
        self.assertEqual(full["requested_coverage"]["soccer_competitions"], 9)
        a = full["scenario_a"]
        for row in a["busy_week"]["leagues"]:
            self.assertEqual(row["hours_accounted"], HOURS_WEEK)
        self.assertFalse(a["plans"]["coverage_removed_to_fit_59"])
        self.assertIn("price_status", a["plans"]["plan_59"])
        self.assertGreater(a["busy_day"]["total"], a["typical_day"]["total"])
        self.assertGreater(a["busy_week"]["props"]["events_modeled"], 5)
        self.assertFalse(full["live_test_budget"]["used_in_cost_model"])
        self.assertIn("all_eligible_events", a["busy_week"]["props"]["model"])
        self.assertGreater(a["busiest_30_day"]["prop_credits"], a["typical_30_day"]["prop_credits"])
        cov = a["busy_week"]["props"]["coverage"]
        self.assertIn("americanfootball_nfl", cov["supported"])
        self.assertIn("basketball_ncaab", cov["unknown"])
        self.assertIn("americanfootball_nfl", cov["sampled_in_live_test"])
        self.assertGreater(a["typical_week"]["score_credits"], 0)
        self.assertEqual(
            a["typical_week"]["total"],
            a["typical_week"]["featured_credits"] + a["typical_week"]["prop_credits"] + a["typical_week"]["score_credits"],
        )
        self.assertIn("score_credits", a["typical_30_day"])
        from market_snapshot.cost_estimate import monthly_budget_table
        table = monthly_budget_table()
        labels = [row["label"] for row in table["rows"]]
        self.assertEqual(labels, ["typical_month", "busiest_month", "blended_year_monthly"])
        typical = next(row for row in table["rows"] if row["label"] == "typical_month")
        busiest = next(row for row in table["rows"] if row["label"] == "busiest_month")
        blended = next(row for row in table["rows"] if row["label"] == "blended_year_monthly")
        self.assertEqual(typical["credits"], a["typical_30_day"]["total"])
        self.assertEqual(busiest["credits"], a["busiest_30_day"]["total"])
        self.assertEqual(blended["credits"], a["monthly_credits"])
        self.assertEqual(typical["with_25pct_reserve"], round(typical["credits"] * 1.25))
        self.assertEqual(busiest["with_25pct_reserve"], round(busiest["credits"] * 1.25))
        self.assertIn("258,694", table["explain_258694_vs_262851"])
        self.assertIn("262,851", table["explain_258694_vs_262851"])
        self.assertFalse(table["scheduler_cap_prepared"]["collection_activated"])
        self.assertFalse(table["scheduler_cap_prepared"]["double_reserve_applied"])
        self.assertEqual(
            table["scheduler_cap_prepared"]["configured_limit"],
            table["scheduler_cap_prepared"]["effective_collection_stop"],
        )
        from datetime import datetime, timezone
        from market_snapshot.final_refresh_test import final_refresh_plan, prove_path_with_fixtures, saved_event_suitability
        suit = saved_event_suitability(now=datetime(2026, 10, 2, 15, 48, tzinfo=timezone.utc))
        self.assertEqual(suit["discovery_http"], 0)
        self.assertTrue(suit["suitable"])
        self.assertNotEqual(suit["selected_event_id"], "d55cb69fed50a09170560b5b75d8de86")
        self.assertFalse(suit["discovery_if_none"]["needed"])
        plan = final_refresh_plan(execute=True)
        self.assertFalse(plan["execute"])
        self.assertTrue(plan["refused_execute"])
        self.assertEqual(plan["http_requests"], 4)
        self.assertEqual(plan["credits_max"], 12)
        self.assertEqual(plan["interval_plan_credits_max"], 12)
        self.assertEqual(plan["discovery_credits_max"], 0)
        self.assertEqual(plan["event_suitability"]["selected_event_id"], "c9d8ed8aa4889486eaf10a630138ede0")
        self.assertTrue(plan["not_initial_ingestion"])
        self.assertEqual(plan["timing"]["featured_min_seconds"], 300)
        self.assertEqual(plan["timing"]["props_min_seconds"], 600)
        self.assertTrue(plan["props_wait_is_from_props_1"])
        self.assertEqual(plan["event_suitability"]["discovery_http"], 0)
        path = prove_path_with_fixtures(require_redis=False)
        self.assertEqual(path["provider_http"], 0)
        self.assertTrue(path["internal_api"])
        self.assertTrue(path["successful_refresh_without_price_change"])
        self.assertTrue(path["actual_price_change_distinct"])
        self.assertTrue(path["older_capture_rejected"])
        self.assertTrue(path["fixture_chronology_ok"])
        self.assertTrue(path["ok"])
        from market_snapshot.feature_gap import feature_gap_report
        from market_snapshot.mobile_installed_test_path import installed_app_test_path
        gap = feature_gap_report()
        self.assertTrue(gap["empty_dfs_intelligence"]["unavailable_handling_is_not_feature_replacement"])
        self.assertTrue(gap["unavailable_assistant_tools"]["unavailable_handling_is_not_feature_replacement"])
        kinds = {row["id"]: row["kind"] for row in gap["remaining_losses_for_mario"]}
        self.assertEqual(kinds["sgo_event_and_odd_ids"], "technical_identifier")
        self.assertEqual(kinds["mlb_prop_coverage_in_current_snapshot"], "not_yet_collected")
        self.assertEqual(kinds["sgo_fantasy_score"], "unsupported_provider_capability")
        self.assertEqual(kinds["steam_opening_sgp"], "history_not_yet_stored_and_unsupported_sgp")
        from market_snapshot.consumers import assistant_market_equivalents
        fair = assistant_market_equivalents({
            "books": [{
                "bookmaker_key": "draftkings",
                "bookmaker": "DraftKings",
                "fair_h2h": {"home": {"american": -105}, "away": {"american": -105}},
                "h2h": {"home": {"american": -148}, "away": {"american": 130}},
            }],
        })
        self.assertEqual(fair["fair_odds"]["source"], "oddsapi_devig")
        self.assertEqual(fair["sgp_quote"], "unavailable")
        self.assertEqual(fair["team_props"], [])
        self.assertEqual(fair["movement"], "unavailable")
        from market_snapshot.oddsapi_intelligence import intelligence_from_prop_rows
        mapped = intelligence_from_prop_rows(
            [{
                "player": "José Ramírez",
                "market": "pitcher_strikeouts",
                "selection": "Over",
                "line": 6.5,
                "commence_time": "2026-10-01T23:00:00Z",
            }],
            [{"id": "dk-1", "name": "Jose Ramirez"}],
        )
        self.assertEqual(mapped["dk-1"]["market_lines"]["pitchingStrikeouts"], 6.5)
        self.assertEqual(mapped["dk-1"]["props"], {})
        self.assertTrue(mapped["dk-1"]["market_lines_are_thresholds"])
        self.assertTrue(mapped["dk-1"]["matched"])
        self.assertIsNone(mapped["dk-1"]["fantasyScore"])
        unmatched = intelligence_from_prop_rows(
            [{
                "player": "José Ramírez",
                "market": "pitcher_strikeouts",
                "selection": "Over",
                "line": 6.5,
            }],
            [
                {"id": "dk-1", "name": "Jose Ramirez"},
                {"id": "dk-2", "name": "Some Unmatched Batter"},
            ],
        )
        self.assertIn("dk-2", unmatched)
        self.assertEqual(unmatched["dk-2"]["market_lines"], {})
        self.assertFalse(unmatched["dk-2"]["matched"])
        self.assertIsNone(unmatched["dk-2"]["fantasyScore"])
        from projection.native import compute_projections
        projs = compute_projections(
            "MLB",
            [{"id": "dk-1", "name": "Jose Ramirez", "position": "P", "salary": 8000}],
            mapped,
        )
        self.assertEqual(projs[0].projection_source, "UNAVAILABLE")
        self.assertEqual(projs[0].base_projection, 0.0)
        mobile = installed_app_test_path()
        self.assertEqual(mobile["distributed_app_store"]["version"], "1.1.1")
        self.assertIn("127.0.0.1", mobile["prepared_test_build"]["profiles"]["development-simulator"]["url"])
        self.assertIn("192.168.1.44", mobile["prepared_test_build"]["profiles"]["development"]["url"])
        self.assertFalse(mobile["released_binary_can_target_isolated_backend"])
        self.assertIn("EAS development", mobile["exact_dependency"]["required"][0])


class CompatTests(unittest.TestCase):
    def test_sgo_ids_are_unavailable_and_oddsapi_ids_are_namespaced(self):
        from market_snapshot.compat import namespaced_event_id, preserve_or_unavailable, resolve_event
        events = [{
            "id": "oddsapi:americanfootball_nfl:abc",
            "internal_event_id": "oddsapi:americanfootball_nfl:abc",
            "source_event_id": "abc",
            "sport_key": "americanfootball_nfl",
            "home_team": "Home",
            "away_team": "Away",
        }]
        self.assertEqual(namespaced_event_id("americanfootball_nfl", "abc"), "oddsapi:americanfootball_nfl:abc")
        sgo = resolve_event("sgo:mlb-123", events)
        self.assertTrue(sgo["unavailable"])
        self.assertIsNone(sgo.get("sgo_event_id") or None)
        self.assertIn("SGO", sgo["reason"])
        found = resolve_event("oddsapi:americanfootball_nfl:abc", events)
        self.assertTrue(found["found"])
        self.assertIsNone(found["sgo_event_id"])
        missed = preserve_or_unavailable({"event_id": "sgo:nope", "selection": "Home", "market": "h2h"}, events)
        self.assertTrue(missed["unavailable"])
        self.assertFalse(missed["discarded"])
        self.assertEqual(missed["selection"], "Home")
        self.assertTrue(missed["preserved"])
        self.assertTrue(missed["unavailable"])

    def test_preview_does_not_emit_sgo_event_ids(self):
        payloads = {
            "sports": [{"key": "americanfootball_nfl", "title": "NFL"}],
            "odds": {
                "americanfootball_nfl": [{
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "commence_time": "2026-10-04T17:00:00Z",
                    "home_team": "Home",
                    "away_team": "Away",
                    "bookmakers": [{
                        "key": "draftkings",
                        "title": "DraftKings",
                        "last_update": "2026-09-30T12:00:00Z",
                        "markets": [{"key": "h2h", "outcomes": [{"name": "Home", "price": -130}, {"name": "Away", "price": 110}]}],
                    }],
                }],
            },
            "index": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "latest_payloads.json").write_text(json.dumps(payloads))
            preview = build_preview(root=root)
        ev = preview["events"][0]
        self.assertTrue(ev["id"].startswith("oddsapi:"))
        self.assertEqual(ev["source_event_id"], "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertIsNone(ev["sgo_event_id"])
        self.assertFalse(preview["compatibility"]["sgo_fields_fabricated"])
        self.assertIn("Lookup by SGO event ID", " ".join(preview["compatibility"]["unsupported_production_features"]))


class ProviderSwitchTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("NODE_ENV", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)

    def test_default_is_sgo_and_production_ignores_snapshot(self):
        from market_snapshot.provider import is_snapshot, market_tools_provider, snapshot_blocks_sgo, oddsapi_enabled, collect_enabled, serves_oddsapi

        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        os.environ["NODE_ENV"] = "development"
        self.assertEqual(market_tools_provider(), "sgo")
        self.assertFalse(snapshot_blocks_sgo())
        self.assertFalse(oddsapi_enabled())
        self.assertFalse(collect_enabled())
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        os.environ["NODE_ENV"] = "production"
        self.assertEqual(market_tools_provider(), "sgo")
        self.assertFalse(is_snapshot())
        self.assertFalse(serves_oddsapi())
        os.environ["NODE_ENV"] = "development"
        self.assertTrue(is_snapshot())
        self.assertTrue(snapshot_blocks_sgo())

    def test_production_oddsapi_flag_is_off_by_default(self):
        from market_snapshot.collector import collect
        from market_snapshot.cutover import activation_state

        os.environ["NODE_ENV"] = "production"
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        skipped = collect()
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["http_requests"], 0)
        state = activation_state()
        self.assertFalse(state["cutover_applied"])
        self.assertTrue(state["rollback_applied"])

    def test_owner_allowlist_does_not_enable_collection_or_global_flags(self):
        import asyncio
        from types import SimpleNamespace
        from market_snapshot.collector import collect
        from market_snapshot.owner_allowlist import owner_account_allows_oddsapi, request_serves_oddsapi
        from market_snapshot.provider import collect_enabled, oddsapi_enabled, serves_oddsapi

        os.environ["NODE_ENV"] = "production"
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS"] = "owner@example.com,42"
        self.assertFalse(oddsapi_enabled())
        self.assertFalse(collect_enabled())
        self.assertFalse(serves_oddsapi())
        skipped = collect()
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["http_requests"], 0)
        owner = SimpleNamespace(id=42, email="owner@example.com", role="user", active_subscription_id=1)
        other = SimpleNamespace(id=99, email="customer@example.com", role="user", active_subscription_id=2)
        self.assertTrue(owner_account_allows_oddsapi(owner))
        self.assertFalse(owner_account_allows_oddsapi(other))
        self.assertFalse(asyncio.run(request_serves_oddsapi(owner)))
        self.assertFalse(asyncio.run(request_serves_oddsapi(other)))

        class EntitledSub:
            plan_name = "Pro Arena"
            status = "active"

        class StarterSub:
            plan_name = "Starter"
            status = "active"

        class Sess:
            def __init__(self, sub):
                self.sub = sub

            async def execute(self, *a, **k):
                sub = self.sub

                class R:
                    def scalars(self):
                        class S:
                            def first(self):
                                return sub
                        return S()
                return R()

        self.assertTrue(asyncio.run(request_serves_oddsapi(owner, Sess(EntitledSub()))))
        self.assertFalse(asyncio.run(request_serves_oddsapi(owner, Sess(StarterSub()))))
        self.assertFalse(asyncio.run(request_serves_oddsapi(other, Sess(EntitledSub()))))
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS", None)


class SelectionMappingTests(unittest.TestCase):
    def test_legacy_sgo_and_missing_quote_are_unavailable(self):
        from market_snapshot.compat import resolve_selection
        events = [{
            "id": "oddsapi:americanfootball_nfl:abc",
            "internal_event_id": "oddsapi:americanfootball_nfl:abc",
            "source_event_id": "abc",
            "sport_key": "americanfootball_nfl",
        }]
        index = {"oddsapi|oddsapi:americanfootball_nfl:abc|h2h|Home|none|dk||game": {
            "id": "oddsapi|oddsapi:americanfootball_nfl:abc|h2h|Home|none|dk||game",
            "event_id": "oddsapi:americanfootball_nfl:abc",
            "selection": "Home",
        }}
        legacy = resolve_selection({"id": "sgo:old", "event_id": "sgo:old"}, index, events)
        self.assertTrue(legacy["unavailable"])
        self.assertIsNone(legacy["sgo_event_id"])
        missing = resolve_selection({
            "id": "oddsapi|oddsapi:americanfootball_nfl:abc|h2h|Away|none|dk||game",
            "event_id": "oddsapi:americanfootball_nfl:abc",
        }, index, events)
        self.assertTrue(missing["unavailable"])
        self.assertIn("not in the snapshot", missing["reason"])
        named = resolve_selection({"event_id": "oddsapi:americanfootball_nfl:abc", "selection": "Home"}, index, events)
        self.assertTrue(named["unavailable"])
        self.assertIn("Ambiguous", named["reason"])


class InternalApiTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        payloads = {
            "sports": [{"key": "americanfootball_nfl", "title": "NFL"}],
            "odds": {
                "americanfootball_nfl": [
                    {
                        "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "commence_time": "2026-10-04T17:00:00Z",
                        "home_team": "Home",
                        "away_team": "Away",
                        "bookmakers": [{
                            "key": "draftkings",
                            "title": "DraftKings",
                            "last_update": "2026-09-30T12:00:00Z",
                            "markets": [
                                {"key": "h2h", "outcomes": [{"name": "Home", "price": -130}, {"name": "Away", "price": 110}]},
                                {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 45.5}, {"name": "Under", "price": -110, "point": 45.5}]},
                            ],
                        }],
                    },
                    {
                        "id": "cccccccccccccccccccccccccccccccc",
                        "commence_time": "2026-10-04T20:00:00Z",
                        "home_team": "North",
                        "away_team": "South",
                        "bookmakers": [{
                            "key": "fanduel",
                            "title": "FanDuel",
                            "last_update": "2026-09-30T12:00:00Z",
                            "markets": [{"key": "h2h", "outcomes": [{"name": "North", "price": -115}, {"name": "South", "price": -105}]}],
                        }],
                    },
                ],
            },
            "index": {},
        }
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "latest_payloads.json").write_text(json.dumps(payloads))
        from market_snapshot import cache
        cache.reset_for_tests()
        self.preview = cache.get_preview(root=root)
        self.cache = cache

    def tearDown(self):
        self.cache.reset_for_tests()
        self.tmp.cleanup()
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)

    def test_snapshot_and_legacy_and_no_sgo(self):
        public = self.cache.public_preview()
        self.assertEqual(public["http_requests_used"], 0)
        self.assertTrue(public["events"][0]["id"].startswith("oddsapi:"))
        self.assertIsNone(public["events"][0]["sgo_event_id"])
        self.assertIn("internal_bookmaker_id", self.preview["quote_index"][next(iter(self.preview["quote_index"]))])
        legacy = self.cache.resolve_saved("sgo:not-real")
        self.assertTrue(legacy["unavailable"])
        self.assertIsNone(legacy.get("sgo_event_id"))
        home = public["events"][0]["books"][0]["h2h"]["home"]["id"]
        over = public["events"][0]["books"][0]["totals"]["over"]["id"]
        other = public["events"][1]["books"][0]["h2h"]["home"]["id"]
        dup = self.cache.parlay_from_body({"leg_ids": [home, home]})
        self.assertTrue(dup.get("duplicate") or not dup["ok"])
        same = self.cache.parlay_from_body({"leg_ids": [home, over]})
        self.assertTrue(same.get("same_game"))
        self.assertTrue(same.get("combined_suppressed"))
        cross = self.cache.parlay_from_body({"leg_ids": [home, other]})
        self.assertTrue(cross.get("ok"))
        self.assertFalse(cross.get("combined_suppressed"))
        self.assertIn("Illustrative", cross.get("label") or "")
        unmapped = self.cache.parlay_from_body({"legs": [{"id": "sgo:legacy", "event_id": "sgo:legacy"}]})
        self.assertTrue(unmapped.get("unavailable"))
        self.assertEqual(self.cache.stats()["provider_http_this_process"], 0)
        self.assertFalse(self.cache.stats()["browsing_triggers_upstream"])


class FixtureCacheReplacementTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()

    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("NODE_ENV", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)

    def test_labeled_fixtures_replace_cache_and_ui_payload(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.auth import get_current_user
        from api.market_tools_internal import router
        from market_snapshot.capture_evidence import CAPTURE_EVIDENCE
        from market_snapshot.collector import collect, verify_fixture_replacement

        skipped = collect()
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["http_requests"], 0)

        report = verify_fixture_replacement()
        self.assertEqual(report["http_requests"], 0)
        self.assertEqual(report["labels"], ["FIXTURE_A_BASELINE", "FIXTURE_B_PRICE_CHANGE"])
        self.assertTrue(report["price_changed"])
        self.assertEqual(report["ui_payload_home_american_a"], -148)
        self.assertEqual(report["ui_payload_home_american_b"], -155)
        self.assertTrue(report["source_timestamp_changed"])
        self.assertTrue(report["retrieved_at_changed"])
        self.assertTrue(report["source_timestamp_distinct_from_retrieved_a"])
        self.assertTrue(report["source_timestamp_distinct_from_retrieved_b"])
        self.assertTrue(report["generation_advanced"])
        self.assertEqual(CAPTURE_EVIDENCE["elapsed_featured_seconds"], 1)
        self.assertEqual(CAPTURE_EVIDENCE["elapsed_props_seconds"], 0)
        self.assertFalse(CAPTURE_EVIDENCE["body_changed"])
        self.assertEqual(CAPTURE_EVIDENCE["provider_http_this_report"], 0)
        self.assertEqual(CAPTURE_EVIDENCE["interval_verification"], "insufficient")
        self.assertFalse(CAPTURE_EVIDENCE["proved_provider_freshness"])

        class Dummy:
            id = 1
            is_pro = False
            role = "admin"
            active_subscription_id = None

        async def override_db():
            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return None
                            return S()
                    return R()
            yield Sess()

        app = FastAPI()
        app.include_router(router, prefix="/api/market-tools")
        app.dependency_overrides[get_current_user] = lambda: Dummy()
        from models.database import get_db
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)
        from market_snapshot.collector import load_labeled_fixture
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()
        load_labeled_fixture("fixture_a_baseline.json")
        a = client.get("/api/market-tools/internal/snapshot").json()["data"]
        load_labeled_fixture("fixture_b_price_change.json")
        b = client.get("/api/market-tools/internal/snapshot").json()["data"]
        self.assertEqual(a["events"][0]["books"][0]["h2h"]["home"]["american"], -148)
        self.assertEqual(b["events"][0]["books"][0]["h2h"]["home"]["american"], -155)
        self.assertEqual(a["events"][0]["books"][0]["h2h"]["home"]["source_timestamp"], "2026-09-30T15:00:00Z")
        self.assertEqual(b["events"][0]["books"][0]["h2h"]["home"]["source_timestamp"], "2026-09-30T15:20:00Z")
        self.assertEqual(a["retrieved_at"], "2026-09-30T15:35:43+00:00")
        self.assertEqual(b["retrieved_at"], "2026-09-30T15:45:44+00:00")
        self.assertNotEqual(a["events"][0]["books"][0]["h2h"]["home"]["source_timestamp"], a["retrieved_at"])
        self.assertEqual(a["cache"]["odds_api_http"], 0)
        self.assertEqual(b["cache"]["odds_api_http"], 0)
        from market_snapshot.timed_refresh_plan import timed_refresh_plan
        plan = timed_refresh_plan()
        self.assertFalse(plan["executable_now"])
        self.assertEqual(plan["provider_http"], 0)
        self.assertEqual(plan["minimum_wait_between_captures_seconds"]["featured_near_window"], 300)
        self.assertEqual(plan["minimum_wait_between_captures_seconds"]["props_near_window"], 600)


class SharedCacheFailureTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "true"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()

    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        os.environ.pop("NODE_ENV", None)
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()

    def test_enabled_mode_does_not_fall_back_to_memory(self):
        from unittest.mock import patch
        from market_snapshot.cache import get_preview, public_preview, acquire_collect_lock, release_collect_lock
        from market_snapshot.collector import collect

        with patch("market_snapshot.cache._redis", lambda: None):
            preview = get_preview()
            self.assertTrue(preview["unavailable"])
            self.assertEqual(preview["reason"], "redis_unavailable")
            self.assertEqual(preview["events"], [])
            pub = public_preview()
            self.assertTrue(pub["unavailable"])
            skipped = collect()
            self.assertTrue(skipped["skipped"])
            self.assertEqual(skipped["http_requests"], 0)
            os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "true"
            skipped = collect()
            self.assertTrue(skipped["skipped"])
            self.assertEqual(skipped["http_requests"], 0)
            self.assertEqual(skipped["reason"], "redis_unavailable")

        class FakeRedis:
            def __init__(self):
                self.store = {}

            def get(self, key):
                return self.store.get(key)

            def set(self, key, value, nx=False, ex=None):
                if nx and key in self.store:
                    return False
                self.store[key] = value
                return True

            def delete(self, key):
                self.store.pop(key, None)

        fake = FakeRedis()
        with patch("market_snapshot.cache._redis", lambda: fake):
            empty = get_preview()
            self.assertTrue(empty["unavailable"])
            self.assertTrue(empty["stale"])
            self.assertEqual(empty["reason"], "cache_empty_stale")
            ok1, why1 = acquire_collect_lock()
            ok2, why2 = acquire_collect_lock()
            self.assertTrue(ok1)
            self.assertEqual(why1, "acquired")
            self.assertFalse(ok2)
            self.assertEqual(why2, "duplicate_worker")
            release_collect_lock()
            ok3, why3 = acquire_collect_lock()
            self.assertTrue(ok3)
            release_collect_lock()

        class DownRedis:
            def get(self, key):
                raise ConnectionError("down")

            def set(self, *a, **k):
                raise ConnectionError("down")

            def delete(self, key):
                raise ConnectionError("down")

        with patch("market_snapshot.cache._redis", lambda: DownRedis()):
            err = get_preview()
            self.assertTrue(err["unavailable"])
            self.assertEqual(err["reason"], "redis_error")


class EntitlementTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        from market_snapshot.collector import load_labeled_fixture
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()
        load_labeled_fixture("fixture_a_baseline.json")

    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("NODE_ENV", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()

    def _client(self, user, sub=None):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.auth import get_current_user
        from api.market_tools_internal import router
        from models.database import get_db

        async def override_db():
            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return sub
                            return S()
                    return R()
            yield Sess()

        app = FastAPI()
        app.include_router(router, prefix="/api/market-tools")
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = override_db
        return TestClient(app)

    def test_auth_alone_does_not_grant_snapshot(self):
        class Starter:
            id = 9
            is_pro = False
            role = "user"
            active_subscription_id = None

        client = self._client(Starter())
        status = client.get("/api/market-tools/internal/status")
        self.assertEqual(status.status_code, 200)
        auth = status.json()["data"]["auth"]
        self.assertTrue(auth["authenticated"])
        self.assertFalse(auth["entitled"])
        snap = client.get("/api/market-tools/internal/snapshot")
        self.assertEqual(snap.status_code, 403)
        parlay = client.post("/api/market-tools/internal/parlay", json={"leg_ids": []})
        self.assertEqual(parlay.status_code, 403)
        resolve = client.post("/api/market-tools/internal/resolve", json={"id": "x"})
        self.assertEqual(resolve.status_code, 403)

    def test_is_pro_without_plan_does_not_grant_snapshot(self):
        class ProFlag:
            id = 3
            is_pro = True
            role = "user"
            active_subscription_id = None

        client = self._client(ProFlag())
        snap = client.get("/api/market-tools/internal/snapshot")
        self.assertEqual(snap.status_code, 403)

    def test_eligible_and_ineligible_plans(self):
        import asyncio
        from market_snapshot.entitlement import plan_entitlement, plan_includes_market_tools

        self.assertTrue(plan_includes_market_tools("Pro Arena"))
        self.assertTrue(plan_includes_market_tools("Pro Arena Annual"))
        self.assertTrue(plan_includes_market_tools("Elite Stack"))
        try:
            from services.paykings_plans import SBME_PLANS as PAYKINGS_PLANS
        except ImportError:
            PAYKINGS_PLANS = {}
        if PAYKINGS_PLANS:
            self.assertTrue(plan_includes_market_tools("SBME_PRO_MONTHLY"))
        else:
            self.assertFalse(plan_includes_market_tools("SBME_PRO_MONTHLY"))
        self.assertFalse(plan_includes_market_tools("Starter"))
        self.assertFalse(plan_includes_market_tools("Pro"))
        self.assertFalse(plan_includes_market_tools("DFS Only"))

        class Paid:
            id = 4
            is_pro = False
            role = "user"
            active_subscription_id = 77

        def session_for(plan_name, sub_status):
            class Sub:
                pass
            sub = Sub()
            sub.plan_name = plan_name
            sub.status = sub_status

            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return sub
                            return S()
                    return R()
            return Sess()

        eligible = asyncio.run(plan_entitlement(Paid(), session_for("Pro Arena", "active")))
        self.assertTrue(eligible["entitled"])
        elite = asyncio.run(plan_entitlement(Paid(), session_for("Elite Stack", "trialing")))
        self.assertTrue(elite["entitled"])
        ineligible_name = asyncio.run(plan_entitlement(Paid(), session_for("Pro", "active")))
        self.assertFalse(ineligible_name["entitled"])
        self.assertFalse(ineligible_name["plan_includes_market_tools"])
        starter_active = asyncio.run(plan_entitlement(Paid(), session_for("Starter", "active")))
        self.assertFalse(starter_active["entitled"])
        canceled = asyncio.run(plan_entitlement(Paid(), session_for("Pro Arena", "canceled")))
        self.assertFalse(canceled["entitled"])
        self.assertFalse(canceled["paid_through"])

        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(days=10)
        past = datetime.now(timezone.utc) - timedelta(days=1)

        def session_period(plan_name, sub_status, period_end, cancel_at_end=False):
            class Sub:
                pass
            sub = Sub()
            sub.plan_name = plan_name
            sub.status = sub_status
            sub.current_period_end = period_end
            sub.cancel_at_period_end = cancel_at_end

            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return sub
                            return S()
                    return R()
            return Sess()

        paid_through = asyncio.run(plan_entitlement(Paid(), session_period("Pro Arena", "canceled", future, True)))
        self.assertTrue(paid_through["entitled"])
        self.assertTrue(paid_through["paid_through"])
        expired = asyncio.run(plan_entitlement(Paid(), session_period("Pro Arena", "canceled", past, True)))
        self.assertFalse(expired["entitled"])
        still_active = asyncio.run(plan_entitlement(Paid(), session_period("Pro Arena", "active", future, True)))
        self.assertTrue(still_active["entitled"])

        class ArenaUser:
            id = 8
            is_pro = False
            role = "user"
            active_subscription_id = 12

        class ArenaSub:
            plan_name = "Pro Arena"
            status = "active"

        class UnknownSub:
            plan_name = "Pro"
            status = "active"

        ok = self._client(ArenaUser(), ArenaSub()).get("/api/market-tools/internal/snapshot")
        self.assertEqual(ok.status_code, 200)
        denied = self._client(ArenaUser(), UnknownSub()).get("/api/market-tools/internal/snapshot")
        self.assertEqual(denied.status_code, 403)


class OwnerAllowlistRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ["NODE_ENV"] = "production"
        os.environ["MARKET_TOOLS_PROVIDER"] = "sgo"
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS"] = "owner@example.com,42"
        from market_snapshot.collector import load_labeled_fixture
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()
        load_labeled_fixture("fixture_a_baseline.json")

    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("NODE_ENV", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS", None)
        from market_snapshot.cache import reset_for_tests
        reset_for_tests()

    def _client(self, user, sub=None):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.auth import get_current_user
        from api.market_tools import router
        from models.database import get_db

        async def override_db():
            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return sub
                            return S()
                    return R()
            yield Sess()

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = override_db
        return TestClient(app)

    def test_entitled_owner_serves_cached_oddsapi_other_customers_stay_sgo(self):
        class Owner:
            id = 42
            email = "owner@example.com"
            is_pro = False
            role = "user"
            active_subscription_id = 12

        class Other:
            id = 99
            email = "customer@example.com"
            is_pro = False
            role = "user"
            active_subscription_id = 13

        class ArenaSub:
            plan_name = "Pro Arena"
            status = "active"

        class StarterSub:
            plan_name = "Starter"
            status = "active"

        owner_ok = self._client(Owner(), ArenaSub()).get("/api/market-tools/live-odds", params={"league": "NFL"})
        self.assertEqual(owner_ok.status_code, 200)
        owner_body = owner_ok.json()["data"]
        self.assertGreater(owner_body.get("count") or 0, 0)
        self.assertTrue((owner_body.get("games") or [])[0]["game_id"].startswith("oddsapi:"))

        owner_usage = self._client(Owner(), ArenaSub()).get("/api/market-tools/usage")
        self.assertEqual(owner_usage.status_code, 200)
        self.assertEqual(owner_usage.json()["data"]["sgo_usage"], "unavailable")

        owner_starter = self._client(Owner(), StarterSub()).get("/api/market-tools/live-odds", params={"league": "NFL"})
        self.assertEqual(owner_starter.status_code, 422)

        other_entitled = self._client(Other(), ArenaSub()).get("/api/market-tools/live-odds", params={"league": "NFL"})
        self.assertEqual(other_entitled.status_code, 422)

        from market_snapshot.collector import collect
        from market_snapshot.provider import collect_enabled, oddsapi_enabled, serves_oddsapi
        self.assertFalse(oddsapi_enabled())
        self.assertFalse(collect_enabled())
        self.assertFalse(serves_oddsapi())
        skipped = collect()
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["http_requests"], 0)


class ScheduledCollectorTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ENABLED", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_COLLECT_INTERVAL", None)
        os.environ.pop("MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS", None)

    def test_lifespan_entry_stays_off_until_both_flags(self):
        import asyncio
        from unittest.mock import patch
        from market_snapshot.collector import (
            COLLECTOR_ACTIVATION,
            collect,
            collect_interval_seconds,
            collector_loop,
            scheduled_collector_enabled,
        )

        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS"] = "owner@example.com"
        self.assertFalse(scheduled_collector_enabled())
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "true"
        self.assertFalse(scheduled_collector_enabled())
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "true"
        self.assertTrue(scheduled_collector_enabled())
        self.assertEqual(collect_interval_seconds(), 1800)
        self.assertEqual(
            COLLECTOR_ACTIVATION["requires"],
            ("MARKET_TOOLS_ODDSAPI_ENABLED=true", "MARKET_TOOLS_ODDSAPI_COLLECT=true"),
        )
        self.assertFalse(COLLECTOR_ACTIVATION["owner_allowlist_starts_collection"])

        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"

        async def cancel_sleep(*_a, **_k):
            raise asyncio.CancelledError()

        async def run_one_tick():
            with patch("market_snapshot.collector.asyncio.sleep", cancel_sleep):
                await collector_loop()

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_one_tick())
        skipped = collect()
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["http_requests"], 0)


class ConsumerProjectionTests(unittest.TestCase):
    def test_mobile_game_row_and_unknown_book_and_odd_id(self):
        os.environ["NODE_ENV"] = "development"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
        from market_snapshot.consumers import event_card_to_mobile_game, filter_events_for_league
        from market_snapshot.books import map_oddsapi_book_key
        from market_engine import sgo_odd_id_unavailable, identity_from_oddsapi_quote, MarketType

        row = event_card_to_mobile_game({
            "id": "oddsapi:americanfootball_nfl:ffffffffffffffffffffffffffffffff",
            "home_team": "Fixture Home",
            "away_team": "Fixture Away",
            "commence_time": "2026-10-05T17:00:00Z",
            "selector": "nfl",
            "books": [{"bookmaker": "DraftKings", "h2h": {"home": {"american": -148}, "away": {"american": 130}}, "spreads": {"home": {"line": -3.5}}, "totals": {}}],
        })
        self.assertEqual(row["game_id"], "oddsapi:americanfootball_nfl:ffffffffffffffffffffffffffffffff")
        self.assertEqual(row["home_team_name"], "Fixture Home")
        self.assertEqual(row["moneyline_home"], -148)
        self.assertIsNone(row["sgo_event_id"])
        self.assertEqual(row["live_score"], "unavailable")
        self.assertEqual(filter_events_for_league([{"selector": "nfl"}], "UFC"), [])
        unknown = map_oddsapi_book_key("not_a_real_book")
        self.assertTrue(unknown["unavailable"])
        mapped = map_oddsapi_book_key("draftkings")
        self.assertFalse(mapped["unavailable"])
        self.assertEqual(mapped["catalog_name"], "DraftKings")
        self.assertIsNone(mapped["sgo_id"])
        blocked = sgo_odd_id_unavailable("sgo-odd-1")
        self.assertTrue(blocked["unavailable"])
        ident = identity_from_oddsapi_quote({"internal_event_id": "oddsapi:x:y", "selection": "Home", "period": "game"}, market_type=MarketType.MONEYLINE)
        self.assertEqual(ident.odd_id, "")
        self.assertEqual(ident.event_id, "oddsapi:x:y")
        os.environ.pop("MARKET_TOOLS_PROVIDER", None)
        os.environ.pop("NODE_ENV", None)


