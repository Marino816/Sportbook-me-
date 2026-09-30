"""Full-scope Market Tools collection cost. Shared server-side only. No provider HTTP.

Featured `/odds` cost = markets specified × regions (empty body 0).
Event props `/events/{id}/odds` cost = unique markets returned × regions (empty body 0).
"""

from __future__ import annotations

from market_snapshot.leagues import LEAGUES
from market_snapshot.source_record import SOURCE

HOURS_WEEK = 168
HOURS_DAY = 24
REGION = "us"
REGIONS = 1
RESERVE = 0.25
PROP_EVENTS_PER_REFRESH = 5
PROP_MARKETS_PER_EVENT = 3
NEAR_WINDOW_HOURS = 6

# Union of [commence-6h, commence) per league — not 6h × event count.
# These are assumed collection hours, not measured live windows.
TYPICAL_NEAR_HOURS = {
    "americanfootball_nfl": 8,
    "americanfootball_ncaaf": 8,
    "baseball_mlb": 12,
    "icehockey_nhl": 18,
    "basketball_nba": 18,
    "basketball_ncaab": 12,
    "basketball_wnba": 6,
    "soccer_usa_mls": 6,
    "soccer_epl": 6,
    "soccer_spain_la_liga": 6,
    "soccer_italy_serie_a": 6,
    "soccer_germany_bundesliga": 6,
    "soccer_france_ligue_one": 6,
    "soccer_uefa_champs_league": 6,
    "soccer_uefa_europa_league": 4,
    "soccer_uefa_europa_conference_league": 4,
    "golf_masters_tournament_winner": 0,
    "golf_pga_championship_winner": 0,
    "golf_the_open_championship_winner": 0,
    "golf_us_open_winner": 0,
}

BUSY_NEAR_HOURS = {
    "americanfootball_nfl": 18,
    "americanfootball_ncaaf": 18,
    "baseball_mlb": 18,
    "icehockey_nhl": 24,
    "basketball_nba": 24,
    "basketball_ncaab": 18,
    "basketball_wnba": 12,
    "soccer_usa_mls": 10,
    "soccer_epl": 10,
    "soccer_spain_la_liga": 10,
    "soccer_italy_serie_a": 10,
    "soccer_germany_bundesliga": 10,
    "soccer_france_ligue_one": 10,
    "soccer_uefa_champs_league": 10,
    "soccer_uefa_europa_league": 8,
    "soccer_uefa_europa_conference_league": 8,
    "golf_masters_tournament_winner": 0,
    "golf_pga_championship_winner": 0,
    "golf_the_open_championship_winner": 0,
    "golf_us_open_winner": 0,
}

# 24-hour slices. Near + far = 24 per league. Union prop hours are not the sum of league near hours.
TYPICAL_DAY_NEAR = {
    "americanfootball_nfl": 0,
    "americanfootball_ncaaf": 0,
    "baseball_mlb": 6,
    "icehockey_nhl": 6,
    "basketball_nba": 6,
    "basketball_ncaab": 0,
    "basketball_wnba": 0,
    "soccer_usa_mls": 0,
    "soccer_epl": 6,
    "soccer_spain_la_liga": 0,
    "soccer_italy_serie_a": 0,
    "soccer_germany_bundesliga": 0,
    "soccer_france_ligue_one": 0,
    "soccer_uefa_champs_league": 6,
    "soccer_uefa_europa_league": 0,
    "soccer_uefa_europa_conference_league": 0,
    "golf_masters_tournament_winner": 0,
    "golf_pga_championship_winner": 0,
    "golf_the_open_championship_winner": 0,
    "golf_us_open_winner": 0,
}
TYPICAL_DAY_PROP_UNION_HOURS = 8

BUSY_DAY_NEAR = {
    "americanfootball_nfl": 12,
    "americanfootball_ncaaf": 10,
    "baseball_mlb": 6,
    "icehockey_nhl": 6,
    "basketball_nba": 6,
    "basketball_ncaab": 6,
    "basketball_wnba": 6,
    "soccer_usa_mls": 6,
    "soccer_epl": 6,
    "soccer_spain_la_liga": 6,
    "soccer_italy_serie_a": 6,
    "soccer_germany_bundesliga": 6,
    "soccer_france_ligue_one": 6,
    "soccer_uefa_champs_league": 6,
    "soccer_uefa_europa_league": 4,
    "soccer_uefa_europa_conference_league": 4,
    "golf_masters_tournament_winner": 0,
    "golf_pga_championship_winner": 0,
    "golf_the_open_championship_winner": 0,
    "golf_us_open_winner": 0,
}
BUSY_DAY_PROP_UNION_HOURS = 16

# Union of near hours across leagues for recurring props (not sum — overlapping games share a window).
TYPICAL_WEEK_PROP_UNION_HOURS = 28
BUSY_WEEK_PROP_UNION_HOURS = 48

GOLF_MAJORS_PER_YEAR = 4
GOLF_DAYS_PER_MAJOR = 7
GOLF_REFRESHES_PER_DAY = 4

PLAN_59 = {"name": "100k", "price_usd": 59, "credits_per_month": 100000, "price_status": "quoted_homepage_snippet_awaiting_checkout_confirmation"}
PLAN_119 = {"name": "5m", "price_usd": 119, "credits_per_month": 5000000, "price_status": "quoted_homepage_snippet_awaiting_checkout_confirmation"}

FREQ_A = {"label": "pregame", "near_main_seconds": 300, "far_main_seconds": 1800, "near_prop_seconds": 600, "far_prop_seconds": None}
FREQ_B = {"label": "faster", "near_main_seconds": 60, "far_main_seconds": 1800, "near_prop_seconds": 120, "far_prop_seconds": None}


def _league_markets(league: dict) -> int:
    return len(league.get("markets") or ())


def _partition(near: int, total: int) -> tuple[int, int]:
    near = max(0, min(int(near), total))
    return near, total - near


def _refreshes(hours: int, interval_seconds: int | None) -> int:
    if not interval_seconds or hours <= 0:
        return 0
    return int(hours * 3600 / interval_seconds)


def _league_row(league: dict, near_hours: int, total_hours: int, freq: dict) -> dict:
    near, far = _partition(near_hours, total_hours)
    markets = _league_markets(league)
    if league.get("kind") == "outright" and near == 0:
        near_r = 0
        far_r = 0
        credits = 0
        skip = "Off-major golf is counted in the annual majors line, not as 30-minute year-round featured polling."
    else:
        near_r = _refreshes(near, freq["near_main_seconds"])
        far_r = _refreshes(far, freq["far_main_seconds"])
        credits = (near_r + far_r) * markets * REGIONS
        skip = None
    return {
        "key": league["key"],
        "title": league["title"],
        "kind": league["kind"],
        "markets": list(league["markets"]),
        "market_count": markets,
        "region": REGION,
        "near_window_hours_per_event": NEAR_WINDOW_HOURS,
        "near_hours_union": near,
        "far_hours": far,
        "hours_accounted": near + far,
        "near_refresh_seconds": freq["near_main_seconds"],
        "far_refresh_seconds": freq["far_main_seconds"],
        "near_refreshes": near_r,
        "far_refreshes": far_r,
        "featured_credits": credits,
        "off_major_golf_skipped_here": skip,
        "note": "Featured cost is per league refresh, not per event. Event count does not multiply this line.",
    }


def _prop_credits(union_hours: int, freq: dict) -> dict:
    interval = freq["near_prop_seconds"]
    refreshes = _refreshes(union_hours, interval)
    per_refresh = PROP_EVENTS_PER_REFRESH * PROP_MARKETS_PER_EVENT * REGIONS
    return {
        "events_per_refresh": PROP_EVENTS_PER_REFRESH,
        "markets_per_event": PROP_MARKETS_PER_EVENT,
        "region": REGION,
        "union_near_hours": union_hours,
        "refresh_seconds": interval,
        "refreshes": refreshes,
        "credits_per_refresh": per_refresh,
        "credits": refreshes * per_refresh,
        "far_prop_seconds": freq["far_prop_seconds"],
        "coverage_limit": (
            f"Only {PROP_EVENTS_PER_REFRESH} events × {PROP_MARKETS_PER_EVENT} markets refresh each cycle. "
            "A busy NFL Sunday (~13–16 games) or NCAAF Saturday (40+ games) is not fully covered. "
            "Customers on unselected events see stale or missing props."
        ),
    }


def _golf_annual() -> dict:
    credits = GOLF_MAJORS_PER_YEAR * GOLF_DAYS_PER_MAJOR * GOLF_REFRESHES_PER_DAY * 1 * REGIONS
    return {
        "markets": "outrights (tournament winner only)",
        "majors_per_year": GOLF_MAJORS_PER_YEAR,
        "days_per_major": GOLF_DAYS_PER_MAJOR,
        "refreshes_per_day": GOLF_REFRESHES_PER_DAY,
        "region": REGION,
        "yearly_credits": credits,
        "monthly_credits": round(credits / 12, 2),
        "not_weekly_pga": True,
    }


def _period(near_map: dict, total_hours: int, freq: dict, prop_union: int) -> dict:
    rows = [_league_row(league, near_map.get(league["key"], 0), total_hours, freq) for league in LEAGUES]
    featured = sum(r["featured_credits"] for r in rows)
    props = _prop_credits(prop_union, freq)
    return {
        "leagues": rows,
        "featured_credits": featured,
        "props": props,
        "total_credits": featured + props["credits"],
    }


def _plan_fit(need: float) -> dict:
    return {
        "need_credits": round(need),
        "plan_59": {**PLAN_59, "covers": PLAN_59["credits_per_month"] >= need},
        "plan_119": {**PLAN_119, "covers": PLAN_119["credits_per_month"] >= need},
        "coverage_removed_to_fit_59": False,
    }


def full_scope_cost() -> dict:
    soccer = [row for row in LEAGUES if row["selector"] == "soccer"]
    golf = [row for row in LEAGUES if row["selector"] == "golf"]
    match = [row for row in LEAGUES if row["kind"] == "match"]
    golf_year = _golf_annual()

    def pack(freq):
        typical_week = _period(TYPICAL_NEAR_HOURS, HOURS_WEEK, freq, TYPICAL_WEEK_PROP_UNION_HOURS)
        busy_week = _period(BUSY_NEAR_HOURS, HOURS_WEEK, freq, BUSY_WEEK_PROP_UNION_HOURS)
        typical_day = _period(TYPICAL_DAY_NEAR, HOURS_DAY, freq, TYPICAL_DAY_PROP_UNION_HOURS)
        busy_day = _period(BUSY_DAY_NEAR, HOURS_DAY, freq, BUSY_DAY_PROP_UNION_HOURS)
        # 8 busy overlap weeks + 36 typical in-season weeks + 8 reduced weeks counted as typical_week * 0.4
        monthly = (busy_week["total_credits"] * 8 + typical_week["total_credits"] * 36 + typical_week["total_credits"] * 0.4 * 8) / 12
        monthly += golf_year["monthly_credits"]
        with_reserve = monthly * (1 + RESERVE)
        return {
            "frequency": freq,
            "typical_day": {"featured_credits": typical_day["featured_credits"], "prop_credits": typical_day["props"]["credits"], "total": typical_day["total_credits"], "leagues": typical_day["leagues"], "props": typical_day["props"]},
            "busy_day": {"featured_credits": busy_day["featured_credits"], "prop_credits": busy_day["props"]["credits"], "total": busy_day["total_credits"], "leagues": busy_day["leagues"], "props": busy_day["props"]},
            "typical_week": {"featured_credits": typical_week["featured_credits"], "prop_credits": typical_week["props"]["credits"], "total": typical_week["total_credits"], "props": typical_week["props"]},
            "busy_week": {"featured_credits": busy_week["featured_credits"], "prop_credits": busy_week["props"]["credits"], "total": busy_week["total_credits"], "leagues": busy_week["leagues"], "props": busy_week["props"]},
            "monthly_credits": round(monthly),
            "monthly_with_reserve": round(with_reserve),
            "plans": _plan_fit(with_reserve),
        }

    a = pack(FREQ_A)
    b = pack(FREQ_B)
    return {
        "continuous_fetch_enabled": False,
        "formulas": {
            "featured": "markets_specified × regions (empty body 0)",
            "event_props": "unique_markets_returned × regions (empty body 0)",
            "region": REGION,
            "near_window": "6 hours before commence; weekly/daily near hours are the UNION of those windows, not 6 × event count",
            "empty_body": "Empty featured/event responses cost 0. Figures below assume in-season bodies so requested coverage is not silently under-counted.",
        },
        "requested_coverage": {
            "league_count": len(LEAGUES),
            "match_leagues": len(match),
            "soccer_competitions": len(soccer),
            "soccer_keys": [r["key"] for r in soccer],
            "golf_markets": [r["key"] for r in golf],
            "us_plus_ncaab": ["NFL", "NCAAF", "NBA", "NHL", "MLB", "WNBA", "NCAAB"],
            "event_counts": "Featured odds cost does not scale with event count. Props do, and are capped at 5 events per refresh.",
        },
        "five_event_prop_limit": (
            "Recurring props collect 5 events × 3 markets per near-window refresh. "
            "That is a shared-cache cap, not per-customer coverage of the full slate."
        ),
        "golf_annual": golf_year,
        "weeks_modeled": {"busy_overlap_weeks": 8, "typical_in_season_weeks": 36, "reduced_weeks_as_0_4_typical": 8},
        "scenario_a": a,
        "scenario_b": b,
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
        "price_confirmation": "Quoted $59 / $119 prices are from official homepage search snippets (direct fetch 403). Treat as awaiting checkout confirmation. Not a purchase.",
        "recommendation_note": (
            "Full requested coverage is not reduced to make a plan fit. "
            "If a plan’s credits are below monthly_with_reserve, that plan does not cover this model."
        ),
    }


def estimate_monthly() -> dict:
    """Adapter/preview entry. Full requested coverage; no silent reductions."""
    full = full_scope_cost()
    a = full["scenario_a"]
    with_reserve = a["monthly_with_reserve"]
    plans = {k: v for k, v in SOURCE["homepage_plans_usd"].items() if k != "source"}
    sufficient = [{"name": name, **plan} for name, plan in plans.items() if plan["credits_per_month"] >= with_reserve]
    under_149 = sorted([p for p in sufficient if p["price_usd"] < 149], key=lambda p: (p["price_usd"], p["credits_per_month"]))
    cheapest = under_149[0] if under_149 else None
    return {
        "assumptions": {
            "collection": "scheduled_shared_server_side",
            "continuous_refresh_this_assignment": False,
            "region": REGION,
            "all_requested_leagues": len(LEAGUES),
            "soccer_competitions": 9,
            "golf_tournament_winner_markets": 4,
            "prop_events_per_refresh": PROP_EVENTS_PER_REFRESH,
            "reserve_fraction": RESERVE,
            "near_window_hours": NEAR_WINDOW_HOURS,
            "scenario": "A pregame 5-min main / 10-min props in union near hours; 30-min far; busy/typical week mix",
        },
        "full_scope": full,
        "monthly_base_credits": a["monthly_credits"],
        "monthly_with_reserve": with_reserve,
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
        "cheapest_sufficient_under_149": cheapest,
        "plan_59": a["plans"]["plan_59"],
        "plan_119": a["plans"]["plan_119"],
        "tradeoff_if_none": None if cheapest else "No listed homepage plan under $149 covers full requested coverage at these frequencies.",
        "thirty_dollar_tradeoff": "The $30 / 20,000 plan cannot cover the requested slate. Coverage is not dropped here to fit $30.",
    }
