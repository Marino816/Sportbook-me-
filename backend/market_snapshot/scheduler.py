"""Server-side refresh and budget controls. Continuous fetching stays disabled."""

from __future__ import annotations

from threading import Lock

from market_snapshot.cost_estimate import full_scope_cost
from market_snapshot.source_record import SOURCE

CONTINUOUS_FETCH_ENABLED = False
REFRESH_LOCK = Lock()
IN_FLIGHT: dict[str, bool] = {}

CONFIG = {
    "enabled": False,
    "region": "us",
    "daily_credit_limit": 2500,
    "monthly_credit_limit": 80000,
    "reserve_fraction": 0.25,
    "stale_after_seconds": 900,
    "per_sport": {
        "americanfootball_nfl": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "americanfootball_ncaaf": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "baseball_mlb": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "icehockey_nhl": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "basketball_nba": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "basketball_ncaab": {"far_seconds": 1800, "near_seconds": 300, "near_hours": 6},
        "basketball_wnba": {"far_seconds": 1800, "near_seconds": 600, "near_hours": 6},
        "soccer": {"far_seconds": 1800, "near_seconds": 600, "near_hours": 6},
        "golf": {"far_seconds": 21600, "near_seconds": 3600, "near_hours": 24},
    },
    "props": {"far_seconds": 3600, "near_seconds": 600, "markets_per_event": 3, "events_per_refresh": 5},
    "single_flight": True,
    "dedupe_key": "sport|markets|region|event_id",
    "browsing_triggers_upstream": False,
}


def single_flight(key: str) -> bool:
    if not CONFIG["single_flight"]:
        return True
    with REFRESH_LOCK:
        if IN_FLIGHT.get(key):
            return False
        IN_FLIGHT[key] = True
        return True


def release_flight(key: str) -> None:
    with REFRESH_LOCK:
        IN_FLIGHT.pop(key, None)


def quota_allows(cost: int, used_month: int, used_day: int) -> bool:
    reserve = int(CONFIG["monthly_credit_limit"] * CONFIG["reserve_fraction"])
    hard_month = CONFIG["monthly_credit_limit"] - reserve
    if used_month + cost > hard_month:
        return False
    if used_day + cost > CONFIG["daily_credit_limit"]:
        return False
    return True


def simulate_usage() -> dict:
    """No provider HTTP. Full requested coverage. Continuous fetching stays disabled."""
    full = full_scope_cost()
    return {
        "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        "config": CONFIG,
        "full_scope": full,
        "scenario_a_pregame": {
            "main_refresh_seconds": 300,
            "prop_refresh_seconds": 600,
            **{k: full["scenario_a"][k] for k in (
                "typical_day", "busy_day", "typical_week", "busy_week",
                "monthly_credits", "monthly_with_reserve", "plans",
            )},
        },
        "scenario_b_faster": {
            "main_refresh_seconds": 60,
            "prop_refresh_seconds": 120,
            **{k: full["scenario_b"][k] for k in (
                "typical_day", "busy_day", "typical_week", "busy_week",
                "monthly_credits", "monthly_with_reserve", "plans",
            )},
        },
        "five_event_prop_limit": full["five_event_prop_limit"],
        "price_confirmation": full["price_confirmation"],
        "recommendation_note": full["recommendation_note"],
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
    }
