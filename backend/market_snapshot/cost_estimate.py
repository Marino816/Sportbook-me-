"""Full-scope Market Tools collection cost. Shared server-side only. No provider HTTP.

Featured `/odds` cost = markets specified × regions (empty body 0).
Event props `/events/{id}/odds` cost = unique markets returned × regions (empty body 0).

Prop cost models every eligible event for explicitly listed markets.
The live test still samples a bounded event set; that cap is not used here.
"""

from __future__ import annotations

from market_snapshot.leagues import LEAGUES
from market_snapshot.source_record import SOURCE

HOURS_WEEK = 168
HOURS_DAY = 24
REGION = "us"
REGIONS = 1
RESERVE = 0.25
NEAR_WINDOW_HOURS = 6
DAYS_PER_30 = 30
WEEKS_PER_30 = DAYS_PER_30 / 7

# Live-test budget only. Not applied to the cost model.
LIVE_TEST_PROP_EVENT_CAP = 5
LIVE_TEST_PROP_MARKETS_PER_EVENT = 3

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

GOLF_MAJORS_PER_YEAR = 4
GOLF_DAYS_PER_MAJOR = 7
GOLF_REFRESHES_PER_DAY = 4

PLAN_59 = {"name": "100k", "price_usd": 59, "credits_per_month": 100000, "price_status": "quoted_homepage_snippet_awaiting_checkout_confirmation"}
PLAN_119 = {"name": "5m", "price_usd": 119, "credits_per_month": 5000000, "price_status": "quoted_homepage_snippet_awaiting_checkout_confirmation"}

FREQ_A = {"label": "pregame", "near_main_seconds": 300, "far_main_seconds": 1800, "near_prop_seconds": 600, "far_prop_seconds": None}
FREQ_B = {"label": "faster", "near_main_seconds": 60, "far_main_seconds": 1800, "near_prop_seconds": 120, "far_prop_seconds": None}

# Explicitly listed player-prop markets for requested sports/leagues.
# coverage: supported = documented for that league; sampled = one-event live test;
# unknown = requested/documented but not confirmed in this catalog.
PROP_SLATE = (
    {
        "key": "americanfootball_nfl",
        "title": "NFL",
        "markets": ("player_pass_tds", "player_pass_yds", "player_rush_yds", "player_receptions"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 0,
        "busy_day_events": 16,
        "typical_week_events": 16,
        "busy_week_events": 16,
        "note": "Documented NFL featured player props. Live test sampled one event, not the slate.",
    },
    {
        "key": "americanfootball_ncaaf",
        "title": "NCAAF",
        "markets": ("player_pass_yds", "player_rush_yds"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 0,
        "busy_day_events": 50,
        "typical_week_events": 14,
        "busy_week_events": 55,
        "note": "Documented with NFL/CFL player-prop keys. Do not assume NBA-style markets.",
    },
    {
        "key": "basketball_nba",
        "title": "NBA",
        "markets": ("player_points", "player_rebounds", "player_assists"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 6,
        "busy_day_events": 12,
        "typical_week_events": 45,
        "busy_week_events": 70,
        "note": "Documented NBA player props. Live test sampled one event.",
    },
    {
        "key": "icehockey_nhl",
        "title": "NHL",
        "markets": ("player_points", "player_goals", "player_assists"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 6,
        "busy_day_events": 12,
        "typical_week_events": 40,
        "busy_week_events": 56,
        "note": "Documented NHL player props. Early-October samples may be preseason.",
    },
    {
        "key": "baseball_mlb",
        "title": "MLB",
        "markets": ("batter_hits", "batter_home_runs", "pitcher_strikeouts"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 8,
        "busy_day_events": 15,
        "typical_week_events": 90,
        "busy_week_events": 105,
        "note": "Documented MLB batter/pitcher props. Live test sampled one event.",
    },
    {
        "key": "basketball_wnba",
        "title": "WNBA",
        "markets": ("player_points", "player_rebounds", "player_assists"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 2,
        "busy_day_events": 6,
        "typical_week_events": 12,
        "busy_week_events": 20,
        "note": "Documented WNBA player props. Off-season days are modeled at typical=2, not zeroed to hide cost.",
    },
    {
        "key": "basketball_ncaab",
        "title": "NCAAB",
        "markets": ("player_points", "player_rebounds", "player_assists"),
        "coverage": "unknown",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 40,
        "typical_week_events": 80,
        "busy_week_events": 180,
        "note": "Documented with NBA/WNBA prop keys. Not in this in-season catalog snapshot. Coverage unknown; still modeled.",
    },
    {
        "key": "soccer_usa_mls",
        "title": "MLS",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 15,
        "typical_week_events": 15,
        "busy_week_events": 15,
        "note": "Soccer props documented for MLS with EPL, Ligue 1, Bundesliga, Serie A, and La Liga.",
    },
    {
        "key": "soccer_epl",
        "title": "England Premier League",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": True,
        "typical_day_events": 0,
        "busy_day_events": 10,
        "typical_week_events": 10,
        "busy_week_events": 10,
        "note": "Live test sampled one EPL event. Full-slate cost uses every listed match.",
    },
    {
        "key": "soccer_spain_la_liga",
        "title": "Spain La Liga",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 10,
        "typical_week_events": 10,
        "busy_week_events": 10,
        "note": "Documented soccer player props. Not sampled in the live test.",
    },
    {
        "key": "soccer_italy_serie_a",
        "title": "Italy Serie A",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 10,
        "typical_week_events": 10,
        "busy_week_events": 10,
        "note": "Documented soccer player props. Not sampled in the live test.",
    },
    {
        "key": "soccer_germany_bundesliga",
        "title": "Germany Bundesliga",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 9,
        "typical_week_events": 9,
        "busy_week_events": 9,
        "note": "Documented soccer player props. Not sampled in the live test.",
    },
    {
        "key": "soccer_france_ligue_one",
        "title": "France Ligue 1",
        "markets": ("player_shots_on_target", "player_assists"),
        "coverage": "supported",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 10,
        "typical_week_events": 10,
        "busy_week_events": 10,
        "note": "Documented soccer player props. Not sampled in the live test.",
    },
    {
        "key": "soccer_uefa_champs_league",
        "title": "UEFA Champions League",
        "markets": (),
        "coverage": "unknown",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 0,
        "typical_week_events": 0,
        "busy_week_events": 0,
        "note": "Soccer player props are not listed for UEFA club competitions. Not costed as eligible events.",
    },
    {
        "key": "soccer_uefa_europa_league",
        "title": "UEFA Europa League",
        "markets": (),
        "coverage": "unknown",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 0,
        "typical_week_events": 0,
        "busy_week_events": 0,
        "note": "Soccer player props are not listed for UEFA club competitions. Not costed as eligible events.",
    },
    {
        "key": "soccer_uefa_europa_conference_league",
        "title": "UEFA Europa Conference League",
        "markets": (),
        "coverage": "unknown",
        "sampled": False,
        "typical_day_events": 0,
        "busy_day_events": 0,
        "typical_week_events": 0,
        "busy_week_events": 0,
        "note": "Soccer player props are not listed for UEFA club competitions. Not costed as eligible events.",
    },
)


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


def _prop_league_row(spec: dict, event_field: str, freq: dict) -> dict:
    interval = freq["near_prop_seconds"]
    events = int(spec.get(event_field) or 0)
    markets = list(spec.get("markets") or ())
    refreshes_per_event = _refreshes(NEAR_WINDOW_HOURS, interval)
    credits_per_event = refreshes_per_event * len(markets) * REGIONS
    credits = events * credits_per_event
    return {
        "key": spec["key"],
        "title": spec["title"],
        "markets": markets,
        "market_count": len(markets),
        "coverage": spec["coverage"],
        "sampled_in_live_test": spec["sampled"],
        "events": events,
        "event_field": event_field,
        "region": REGION,
        "near_window_hours": NEAR_WINDOW_HOURS,
        "refresh_seconds": interval,
        "far_prop_seconds": freq["far_prop_seconds"],
        "refreshes_per_event": refreshes_per_event,
        "credits_per_event": credits_per_event,
        "credits": credits,
        "note": spec.get("note"),
    }


def _prop_credits(event_field: str, freq: dict) -> dict:
    rows = [_prop_league_row(spec, event_field, freq) for spec in PROP_SLATE]
    eligible = [r for r in rows if r["market_count"] and r["events"] >= 0]
    credits = sum(r["credits"] for r in rows)
    events = sum(r["events"] for r in rows if r["market_count"])
    by_coverage = {"supported": 0, "sampled": 0, "unknown": 0}
    for spec, row in zip(PROP_SLATE, rows):
        by_coverage[spec["coverage"]] = by_coverage.get(spec["coverage"], 0) + row["credits"]
        if spec["sampled"]:
            by_coverage["sampled"] += 0  # sampled is a coverage flag, not extra credits
    sampled_keys = [s["key"] for s in PROP_SLATE if s["sampled"]]
    supported_keys = [s["key"] for s in PROP_SLATE if s["coverage"] == "supported"]
    unknown_keys = [s["key"] for s in PROP_SLATE if s["coverage"] == "unknown"]
    return {
        "model": "all_eligible_events_times_listed_markets",
        "live_test_event_cap_not_applied": LIVE_TEST_PROP_EVENT_CAP,
        "events_modeled": events,
        "events_per_refresh": events,
        "region": REGION,
        "refresh_seconds": freq["near_prop_seconds"],
        "near_window_hours_per_event": NEAR_WINDOW_HOURS,
        "credits": credits,
        "credits_per_refresh_if_all_events_polled_once": sum(
            r["events"] * r["market_count"] * REGIONS for r in rows
        ),
        "leagues": rows,
        "eligible_league_count": len([r for r in eligible if r["market_count"]]),
        "coverage": {
            "supported": supported_keys,
            "sampled_in_live_test": sampled_keys,
            "unknown": unknown_keys,
            "credits_by_coverage": {
                "supported": sum(r["credits"] for r in rows if r["coverage"] == "supported"),
                "unknown": sum(r["credits"] for r in rows if r["coverage"] == "unknown"),
            },
        },
        "far_prop_seconds": freq["far_prop_seconds"],
        "note": (
            "Each eligible event is refreshed for 6 hours before commence on listed prop markets. "
            f"Live test still samples at most {LIVE_TEST_PROP_EVENT_CAP} events; that cap is not used here."
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
        "player_props": "Golf has no listed player-prop markets in this model.",
    }


def _period(near_map: dict, total_hours: int, freq: dict, prop_event_field: str) -> dict:
    rows = [_league_row(league, near_map.get(league["key"], 0), total_hours, freq) for league in LEAGUES]
    featured = sum(r["featured_credits"] for r in rows)
    props = _prop_credits(prop_event_field, freq)
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


def _scale_30(week_credits: float) -> int:
    return round(week_credits * WEEKS_PER_30)


def full_scope_cost() -> dict:
    soccer = [row for row in LEAGUES if row["selector"] == "soccer"]
    golf = [row for row in LEAGUES if row["selector"] == "golf"]
    match = [row for row in LEAGUES if row["kind"] == "match"]
    golf_year = _golf_annual()

    def pack(freq):
        typical_week = _period(TYPICAL_NEAR_HOURS, HOURS_WEEK, freq, "typical_week_events")
        busy_week = _period(BUSY_NEAR_HOURS, HOURS_WEEK, freq, "busy_week_events")
        typical_day = _period(TYPICAL_DAY_NEAR, HOURS_DAY, freq, "typical_day_events")
        busy_day = _period(BUSY_DAY_NEAR, HOURS_DAY, freq, "busy_day_events")
        monthly = (busy_week["total_credits"] * 8 + typical_week["total_credits"] * 36 + typical_week["total_credits"] * 0.4 * 8) / 12
        monthly += golf_year["monthly_credits"]
        with_reserve = monthly * (1 + RESERVE)
        typical_30 = {
            "featured_credits": _scale_30(typical_week["featured_credits"]),
            "prop_credits": _scale_30(typical_week["props"]["credits"]),
            "total": _scale_30(typical_week["total_credits"]),
            "window": "typical_week × 30/7",
            "region": REGION,
        }
        busiest_30 = {
            "featured_credits": _scale_30(busy_week["featured_credits"]),
            "prop_credits": _scale_30(busy_week["props"]["credits"]),
            "total": _scale_30(busy_week["total_credits"]),
            "window": "busy_week × 30/7 (every week treated as overlap/busy)",
            "region": REGION,
        }
        return {
            "frequency": freq,
            "typical_day": {"featured_credits": typical_day["featured_credits"], "prop_credits": typical_day["props"]["credits"], "total": typical_day["total_credits"], "leagues": typical_day["leagues"], "props": typical_day["props"]},
            "busy_day": {"featured_credits": busy_day["featured_credits"], "prop_credits": busy_day["props"]["credits"], "total": busy_day["total_credits"], "leagues": busy_day["leagues"], "props": busy_day["props"]},
            "typical_week": {"featured_credits": typical_week["featured_credits"], "prop_credits": typical_week["props"]["credits"], "total": typical_week["total_credits"], "props": typical_week["props"]},
            "busy_week": {"featured_credits": busy_week["featured_credits"], "prop_credits": busy_week["props"]["credits"], "total": busy_week["total_credits"], "leagues": busy_week["leagues"], "props": busy_week["props"]},
            "typical_30_day": typical_30,
            "busiest_30_day": busiest_30,
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
            "event_props": "unique_markets_returned × regions (empty body 0); costed as listed_markets × eligible_events × near-window refreshes",
            "region": REGION,
            "near_window": "6 hours before commence; featured weekly/daily near hours are the UNION of those windows, not 6 × event count. Props multiply by event count because /events/{id}/odds is per event.",
            "empty_body": "Empty featured/event responses cost 0. Figures below assume in-season bodies so requested coverage is not silently under-counted.",
        },
        "requested_coverage": {
            "league_count": len(LEAGUES),
            "match_leagues": len(match),
            "soccer_competitions": len(soccer),
            "soccer_keys": [r["key"] for r in soccer],
            "golf_markets": [r["key"] for r in golf],
            "us_plus_ncaab": ["NFL", "NCAAF", "NBA", "NHL", "MLB", "WNBA", "NCAAB"],
            "event_counts": "Featured odds cost does not scale with event count. Props scale with every eligible event for listed markets.",
            "prop_slate": [
                {
                    "key": s["key"],
                    "title": s["title"],
                    "markets": list(s["markets"]),
                    "coverage": s["coverage"],
                    "sampled_in_live_test": s["sampled"],
                    "typical_week_events": s["typical_week_events"],
                    "busy_week_events": s["busy_week_events"],
                }
                for s in PROP_SLATE
            ],
        },
        "five_event_prop_limit": (
            "Removed from the cost model. Recurring props now cost every eligible event × listed markets × region us "
            f"for the 6-hour near window. The live test budget remains {LIVE_TEST_PROP_EVENT_CAP} sampled events "
            f"and is not used in these figures."
        ),
        "live_test_budget": {
            "max_events": LIVE_TEST_PROP_EVENT_CAP,
            "markets_per_sampled_event": LIVE_TEST_PROP_MARKETS_PER_EVENT,
            "used_in_cost_model": False,
        },
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
            "prop_model": "all_eligible_events",
            "live_test_prop_event_cap": LIVE_TEST_PROP_EVENT_CAP,
            "live_test_cap_used_in_cost": False,
            "reserve_fraction": RESERVE,
            "near_window_hours": NEAR_WINDOW_HOURS,
            "scenario": "A pregame 5-min main / 10-min props in each event’s 6h near window; 30-min far featured; busy/typical week mix",
        },
        "full_scope": full,
        "monthly_base_credits": a["monthly_credits"],
        "monthly_with_reserve": with_reserve,
        "typical_30_day": a["typical_30_day"],
        "busiest_30_day": a["busiest_30_day"],
        "plans_from_homepage": SOURCE["homepage_plans_usd"],
        "cheapest_sufficient_under_149": cheapest,
        "plan_59": a["plans"]["plan_59"],
        "plan_119": a["plans"]["plan_119"],
        "tradeoff_if_none": None if cheapest else "No listed homepage plan under $149 covers full requested coverage at these frequencies.",
        "thirty_dollar_tradeoff": "The $30 / 20,000 plan cannot cover the requested slate. Coverage is not dropped here to fit $30.",
    }
