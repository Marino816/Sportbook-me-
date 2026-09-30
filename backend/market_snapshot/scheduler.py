"""Server-side refresh and budget controls. Continuous fetching stays disabled."""

from __future__ import annotations

from threading import Lock

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
    """No provider HTTP. Shared server-side collection scenarios."""
    plans = {k: v for k, v in SOURCE["homepage_plans_usd"].items() if k != "source"}
    # Busy-season overlap: NFL + NCAAF + NBA + NHL + MLB playoffs/shoulder + 4 soccer leagues.
    us_sports = 5
    soccer_leagues = 4
    main_markets = 3
    region = 1
    main_credits = (us_sports + soccer_leagues) * main_markets * region
    prop_credits = CONFIG["props"]["events_per_refresh"] * CONFIG["props"]["markets_per_event"]
    # Scenario A: 20h/week pregame windows, 5-min main, 10-min props. Off-peak 148h main every 30 min, no props.
    a_peak_h, a_off_h = 20, 148
    a_main_peak = int(a_peak_h * 3600 / 300) * main_credits
    a_prop_peak = int(a_peak_h * 3600 / 600) * prop_credits
    a_main_off = int(a_off_h * 3600 / 1800) * (us_sports * main_markets)
    a_weekly = a_main_peak + a_prop_peak + a_main_off
    a_monthly = a_weekly * 52 / 12
    a_reserve = a_monthly * (1 + CONFIG["reserve_fraction"])
    # Scenario B: 16h/week active windows, 60s main, 2-min props. Off-peak same as A.
    b_active_h = 16
    b_main = int(b_active_h * 3600 / 60) * main_credits
    b_prop = int(b_active_h * 3600 / 120) * prop_credits
    b_weekly = b_main + b_prop + a_main_off
    b_monthly = b_weekly * 52 / 12
    b_reserve = b_monthly * (1 + CONFIG["reserve_fraction"])

    def cheapest(need: float):
        under = [{"name": n, **p} for n, p in plans.items() if p["price_usd"] < 149 and p["credits_per_month"] >= need]
        under.sort(key=lambda p: p["price_usd"])
        return under[0] if under else None

    a_plan = cheapest(a_reserve)
    b_plan = cheapest(b_reserve)
    return {
        "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        "config": CONFIG,
        "assumptions": {
            "busy_season_us_sports": us_sports,
            "soccer_leagues_in_window": soccer_leagues,
            "main_markets": main_markets,
            "region": "us",
            "pregame_window_hours": 6,
            "scenario_a_windows": "20h/week defined pregame; 148h/week slower far-from-game",
            "scenario_b_windows": "16h/week defined active; 148h/week slower far-from-game",
            "provider_freshness": "Odds API featured markets are not a 60-second promise; additional markets update about every 60s and can drop ~15 minutes after suspend.",
            "not_a_freshness_sla": True,
        },
        "scenario_a_pregame": {
            "main_refresh_seconds": 300,
            "prop_refresh_seconds": 600,
            "weekly_credits": a_weekly,
            "monthly_credits": round(a_monthly),
            "monthly_with_reserve": round(a_reserve),
            "plan": a_plan,
        },
        "scenario_b_faster": {
            "main_refresh_seconds": 60,
            "prop_refresh_seconds": 120,
            "weekly_credits": b_weekly,
            "monthly_credits": round(b_monthly),
            "monthly_with_reserve": round(b_reserve),
            "plan": b_plan,
            "fits_under_149": b_plan is not None,
            "exceeds_100k": b_reserve > 100000,
        },
        "recommendation": (
            "Use scenario A on the 100K / $59 plan. Scenario B exceeds 100K credits; the next listed homepage plan under $149 is 5M / $119. Continuous fetch stays disabled."
            if a_plan and (b_plan or True) else
            "See scenario plans."
        ),
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
    }
