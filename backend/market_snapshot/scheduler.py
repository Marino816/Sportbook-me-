"""Server-side refresh and budget controls. Continuous fetching stays disabled."""

from __future__ import annotations

import os
from threading import Lock

from market_snapshot.cost_estimate import RESERVE, full_scope_cost
from market_snapshot.source_record import SOURCE

CONTINUOUS_FETCH_ENABLED = False
REFRESH_LOCK = Lock()
IN_FLIGHT: dict[str, bool] = {}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value >= 0 else default


# Configured monthly limit already includes 25% contingency on the busiest month.
# quota_allows uses that full usable amount. The reserve is not subtracted again.
_SCOPE_A = full_scope_cost()["scenario_a"]
BUSIEST_30_DAY = int(_SCOPE_A["busiest_30_day"]["total"])
BUSY_DAY = int(round(_SCOPE_A["busy_day"]["total"]))
CONTINGENCY_CREDITS = int(round(BUSIEST_30_DAY * RESERVE))
DEFAULT_MONTHLY_CREDIT_LIMIT = BUSIEST_30_DAY + CONTINGENCY_CREDITS
DEFAULT_DAILY_CREDIT_LIMIT = int(round(BUSY_DAY * (1 + RESERVE)))


def quota_breakdown() -> dict:
    configured = int(CONFIG["monthly_credit_limit"])
    reserve_fraction = float(CONFIG["reserve_fraction"])
    reserve_credits = int(round(BUSIEST_30_DAY * reserve_fraction))
    # Usable stop is the configured limit. Contingency is already inside it.
    effective_stop = configured
    return {
        "configured_limit": configured,
        "modeled_busiest_month": BUSIEST_30_DAY,
        "contingency_credits": reserve_credits,
        "contingency_fraction": reserve_fraction,
        "reserve_held_back_from_collection": 0,
        "effective_collection_stop": effective_stop,
        "daily_limit": int(CONFIG["daily_credit_limit"]),
        "collection_activated": False,
        "double_reserve_applied": False,
        "note": (
            "configured_limit = busiest_30_day + 25% contingency. "
            "effective_collection_stop equals configured_limit. "
            "The 25% is not subtracted a second time."
        ),
    }

CONFIG = {
    "enabled": False,
    "region": "us",
    "daily_credit_limit": _int_env("MARKET_TOOLS_DAILY_CREDIT_LIMIT", DEFAULT_DAILY_CREDIT_LIMIT),
    "monthly_credit_limit": _int_env("MARKET_TOOLS_MONTHLY_CREDIT_LIMIT", DEFAULT_MONTHLY_CREDIT_LIMIT),
    "reserve_fraction": RESERVE,
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
    "props": {
        "far_seconds": 3600,
        "near_seconds": 600,
        "cost_model": "all_eligible_events",
        "live_test_events_per_refresh": 5,
    },
    "single_flight": True,
    "context_collect_scheduled": False,
    "dedupe_key": "sport|markets|region|event_id",
    "browsing_triggers_upstream": False,
    "collection_activated": False,
    "cap_source": {
        "monthly_env": "MARKET_TOOLS_MONTHLY_CREDIT_LIMIT",
        "daily_env": "MARKET_TOOLS_DAILY_CREDIT_LIMIT",
        "monthly_default": DEFAULT_MONTHLY_CREDIT_LIMIT,
        "daily_default": DEFAULT_DAILY_CREDIT_LIMIT,
        "note": (
            "Default monthly cap is busiest_30_day plus 25% contingency. "
            "quota_allows stops at that full amount. Collection stays off."
        ),
    },
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
    parts = quota_breakdown()
    if used_month + cost > parts["effective_collection_stop"]:
        return False
    if used_day + cost > parts["daily_limit"]:
        return False
    return True


def simulate_usage() -> dict:
    """No provider HTTP. Full requested coverage. Continuous fetching stays disabled."""
    full = full_scope_cost()
    return {
        "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        "config": CONFIG,
        "quota": quota_breakdown(),
        "full_scope": full,
        "scenario_a_pregame": {
            "main_refresh_seconds": 300,
            "prop_refresh_seconds": 600,
            **{k: full["scenario_a"][k] for k in (
                "typical_day", "busy_day", "typical_week", "busy_week",
                "typical_30_day", "busiest_30_day",
                "monthly_credits", "monthly_with_reserve", "plans",
            )},
        },
        "scenario_b_faster": {
            "main_refresh_seconds": 60,
            "prop_refresh_seconds": 120,
            **{k: full["scenario_b"][k] for k in (
                "typical_day", "busy_day", "typical_week", "busy_week",
                "typical_30_day", "busiest_30_day",
                "monthly_credits", "monthly_with_reserve", "plans",
            )},
        },
        "five_event_prop_limit": full["five_event_prop_limit"],
        "live_test_budget": full["live_test_budget"],
        "price_confirmation": full["price_confirmation"],
        "recommendation_note": full["recommendation_note"],
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
    }
