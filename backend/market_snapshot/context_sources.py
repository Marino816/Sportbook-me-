"""Source registry for scores, weather, and injuries. No secrets."""

from __future__ import annotations

SCORES = {
    "provider": "The Odds API",
    "docs": "https://the-odds-api.com/liveapi/guides/v4/#get-scores",
    "endpoint": "GET /v4/sports/{sport}/scores",
    "cost_without_days_from": 1,
    "cost_with_days_from": 2,
    "days_from_range": "1-3",
    "update_frequency": "Live scores update approximately every 30 seconds (provider documentation).",
    "fields_supplied": [
        "id", "sport_key", "sport_title", "commence_time", "completed",
        "home_team", "away_team", "scores[{name,score}]", "last_update",
    ],
    "fields_not_in_schema": ["period", "inning", "clock", "postponed", "canceled", "delayed"],
    "event_id_matches_odds": True,
    "empty_body_credits": "Empty data does not consume credits (provider documentation).",
    "commercial": "Existing Odds API terms already recorded for Market Tools UI display; scores use the same key.",
    "sampled_this_assignment": ["americanfootball_nfl", "baseball_mlb"],
    "untested": [
        "NCAAF", "NBA", "NHL", "WNBA", "NCAAB", "MLS", "EPL", "other soccer", "golf",
    ],
}

WEATHER = {
    "provider": "National Weather Service API",
    "docs": "https://www.weather.gov/documentation/services-web-api",
    "host": "https://api.weather.gov",
    "cost": 0,
    "commercial": (
        "Official NWS documentation (retrieved 2026-09-30): information via the API is "
        "intended to be open data, free to use for any purpose, as a public service of "
        "the United States Government. No fees. Rate limits exist and are not public. "
        "A User-Agent identifying the application is required."
    ),
    "attribution": "National Weather Service",
    "coverage": "United States forecast offices / NWS grid. Not a global weather API.",
    "forecast_horizon": "About seven days (hourly and 12-hour forecast products).",
    "kind": "forecast",
    "observation_not_fetched": True,
    "update_frequency": "NWS grid forecasts; cache-friendly expiry. Not polled continuously here.",
    "venue_coords": "Used only to stamp saved NWS collection-target coordinates. Not an event venue.",
}

from market_snapshot.injury_sources import INJURIES

ASSIGNMENT_BUDGET = {
    "max_additional_odds_credits": 10,
    "max_data_provider_http": 12,
    "starting_remaining_credits_reported": 422,
    "planned": [
        {
            "source": "The Odds API",
            "path": "/v4/sports/americanfootball_nfl/scores",
            "params": "daysFrom=1",
            "max_credits": 2,
            "http": 1,
            "why": "Live, upcoming, and recently completed NFL; match by source event id.",
        },
        {
            "source": "The Odds API",
            "path": "/v4/sports/baseball_mlb/scores",
            "params": "daysFrom=1",
            "max_credits": 2,
            "http": 1,
            "why": "Outdoor MLB sample for scores/status plus weather matching.",
        },
        {
            "source": "National Weather Service",
            "path": "/points/{lat},{lon} then forecastHourly",
            "max_credits": 0,
            "http": 2,
            "why": "One outdoor US venue forecast at event time.",
        },
    ],
    "planned_http_total": 4,
    "planned_odds_credits_max": 4,
    "not_planned": [
        "Injury HTTP (permission not established)",
        "daysFrom=3 (extra credits, not required for the sample)",
        "NCAAF/NBA/NHL scores (untested this assignment)",
        "Retries, polling, historical Odds API, continuous collect",
    ],
}

SCHEDULED_FETCH_ENABLED = False
