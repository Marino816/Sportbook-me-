"""Monthly credit estimate for expanded Market Tools. Shared server-side collection only."""

from __future__ import annotations

from market_snapshot.source_record import SOURCE

# Budget-controlled shared refresh. Not per customer. Continuous refresh is not enabled.
ASSUMPTIONS = {
    "collection": "scheduled_shared_server_side",
    "continuous_refresh_this_assignment": False,
    "region": "us",
    "peak_us_sports": ["NFL", "NCAAF", "NBA", "NHL", "MLB"],
    "peak_us_credits_per_refresh": 15,
    "shoulder_us_sports": ["WNBA", "NCAAB"],
    "shoulder_us_credits_per_refresh": 6,
    "soccer_leagues": 9,
    "soccer_markets": "h2h,spreads,totals",
    "soccer_credits_per_refresh": 27,
    "golf_active_majors_per_year": 4,
    "golf_days_per_major": 7,
    "golf_refreshes_per_day": 4,
    "golf_credits_per_refresh": 1,
    "peak_hours_per_week": 20,
    "peak_refresh_seconds": 600,
    "offpeak_hours_per_week": 148,
    "offpeak_refresh_seconds": 1800,
    "soccer_hours_per_week": 28,
    "soccer_refresh_seconds": 1800,
    "player_prop_events_per_peak_refresh": 0,
    "reserve_fraction": 0.25,
    "notes": (
        "Peak US featured (3 markets × 5 in-season sports). Off-peak same 5 sports at 30 minutes. "
        "Soccer 9 leagues × 3 markets every 30 minutes during a 28-hour weekly window. "
        "Golf majors only, 4 refreshes/day during 7 tournament days. Props are not on the shared refresh until sampled."
    ),
}


def estimate_monthly() -> dict:
    a = ASSUMPTIONS
    peak_refreshes = int((a["peak_hours_per_week"] * 3600) / a["peak_refresh_seconds"])
    off_refreshes = int((a["offpeak_hours_per_week"] * 3600) / a["offpeak_refresh_seconds"])
    soccer_refreshes = int((a["soccer_hours_per_week"] * 3600) / a["soccer_refresh_seconds"])
    weekly_us = peak_refreshes * a["peak_us_credits_per_refresh"] + off_refreshes * a["peak_us_credits_per_refresh"]
    weekly_soccer = soccer_refreshes * a["soccer_credits_per_refresh"]
    yearly_golf = (
        a["golf_active_majors_per_year"]
        * a["golf_days_per_major"]
        * a["golf_refreshes_per_day"]
        * a["golf_credits_per_refresh"]
    )
    monthly_us = weekly_us * 52 / 12
    monthly_soccer = weekly_soccer * 52 / 12
    monthly_golf = yearly_golf / 12
    monthly_shoulder = (peak_refreshes * a["shoulder_us_credits_per_refresh"]) * 16 / 12
    base = monthly_us + monthly_soccer + monthly_golf + monthly_shoulder
    with_reserve = base * (1 + a["reserve_fraction"])
    plans = {k: v for k, v in SOURCE["homepage_plans_usd"].items() if k != "source"}
    sufficient = [{"name": name, **plan} for name, plan in plans.items() if plan["credits_per_month"] >= with_reserve]
    under_149 = sorted([p for p in sufficient if p["price_usd"] < 149], key=lambda p: (p["price_usd"], p["credits_per_month"]))
    cheapest = under_149[0] if under_149 else None
    tradeoff_30 = (
        "The $30 / 20,000 plan cannot cover this expanded slate. A $30 tradeoff would drop soccer "
        "spreads/totals, golf, WNBA/NCAAB, and props, and refresh four US sports hourly (~17k credits "
        "with reserve). That is less coverage than this preview."
    )
    return {
        "assumptions": a,
        "weekly_us_featured_credits": weekly_us,
        "weekly_soccer_credits": weekly_soccer,
        "monthly_us_featured_credits": round(monthly_us),
        "monthly_soccer_credits": round(monthly_soccer),
        "monthly_golf_credits": round(monthly_golf),
        "monthly_shoulder_credits": round(monthly_shoulder),
        "monthly_base_credits": round(base),
        "monthly_with_reserve": round(with_reserve),
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
        "cheapest_sufficient_under_149": cheapest,
        "tradeoff_if_none": None if cheapest else (
            "No documented homepage plan under $149 covers this expanded refresh model."
        ),
        "thirty_dollar_tradeoff": tradeoff_30,
    }
