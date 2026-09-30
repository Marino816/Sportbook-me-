"""Monthly credit estimate from documented cost formula. No provider HTTP."""

from __future__ import annotations

from market_snapshot.source_record import SOURCE

# Explicit refresh model for shared server-side Market Tools.
ASSUMPTIONS = {
    "sports": ["NFL", "NCAAF", "MLB"],
    "featured_markets_per_sport": 3,
    "region": "us",
    "credits_per_featured_refresh": 9,
    "peak_hours_per_week": 16,
    "peak_refresh_seconds": 120,
    "offpeak_hours_per_week": 152,
    "offpeak_refresh_seconds": 900,
    "player_prop_events_per_refresh": 3,
    "player_prop_markets_per_event": 1,
    "reserve_fraction": 0.25,
}


def estimate_monthly() -> dict:
    a = ASSUMPTIONS
    peak_refreshes = int((a["peak_hours_per_week"] * 3600) / a["peak_refresh_seconds"])
    off_refreshes = int((a["offpeak_hours_per_week"] * 3600) / a["offpeak_refresh_seconds"])
    weekly_featured = (peak_refreshes + off_refreshes) * a["credits_per_featured_refresh"]
    weekly_props = (peak_refreshes + off_refreshes) * a["player_prop_events_per_refresh"] * a["player_prop_markets_per_event"]
    monthly_featured = weekly_featured * 52 / 12
    monthly_props = weekly_props * 52 / 12
    base = monthly_featured + monthly_props
    with_reserve = base * (1 + a["reserve_fraction"])
    plans = SOURCE["homepage_plans_usd"]
    sufficient = []
    for name, plan in plans.items():
        if name == "source":
            continue
        if plan["credits_per_month"] >= with_reserve:
            sufficient.append({"name": name, **plan})
    under_149 = [p for p in sufficient if p["price_usd"] < 149]
    under_149.sort(key=lambda p: (p["price_usd"], p["credits_per_month"]))
    cheapest = under_149[0] if under_149 else None
    return {
        "assumptions": a,
        "weekly_featured_credits": weekly_featured,
        "weekly_prop_credits": weekly_props,
        "monthly_featured_credits": round(monthly_featured),
        "monthly_prop_credits": round(monthly_props),
        "monthly_base_credits": round(base),
        "monthly_with_reserve": round(with_reserve),
        "plans_from_homepage": plans,
        "cheapest_sufficient_under_149": cheapest,
        "tradeoff_if_none": None if cheapest else (
            "No documented homepage plan under $149 covers this peak+off-peak featured+prop refresh model."
        ),
    }
