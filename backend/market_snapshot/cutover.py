"""Cutover and rollback configuration. Neither is activated by importing this module."""

from __future__ import annotations

from market_snapshot.feature_gap import feature_gap_report
from market_snapshot.final_refresh_test import final_refresh_plan
from market_snapshot.flags import collect_enabled, flag_status, oddsapi_enabled
from market_snapshot.mobile_installed_test_path import installed_app_test_path

# Apply only by setting process environment in a later, explicit activation assignment.
CUTOVER_ENV = {
    "MARKET_TOOLS_ODDSAPI_ENABLED": "true",
    "MARKET_TOOLS_ODDSAPI_COLLECT": "true",
    "MARKET_TOOLS_PROVIDER": "sgo",
}

ROLLBACK_ENV = {
    "MARKET_TOOLS_ODDSAPI_ENABLED": "false",
    "MARKET_TOOLS_ODDSAPI_COLLECT": "false",
    "MARKET_TOOLS_PROVIDER": "sgo",
}

COMPATIBLE_CONSUMERS = (
    {
        "surface": "web approved Market Tools",
        "path": "web/src/components/market-tools-approved",
        "via": "GET /api/market-tools/internal/snapshot after auth+entitlement",
        "compatible": True,
    },
    {
        "surface": "internal parlay/resolve",
        "path": "api.market_tools_internal",
        "via": "namespaced oddsapi quote ids; plan entitlement required",
        "compatible": True,
    },
    {
        "surface": "existing web Market Tools routes",
        "path": "web/src/app/market-tools/{live-odds,compare,player-props,parlay,arbitrage,bookmakers}",
        "via": "Approved layout when Odds API serving is on; /sgo/events returns structured unavailable for live scores",
        "compatible": True,
    },
    {
        "surface": "mobile Market Tools",
        "path": "mobile/app/(tabs)/market-tools",
        "via": "GET /market-tools/live-odds projected to game_id/home_team_name/moneyline; unavailable handled in screens",
        "compatible": True,
    },
    {
        "surface": "assistant Odds API cache recitation",
        "path": "backend/assistant/tools.py",
        "via": "Reads shared Odds API cache rows for events/odds/props when present. This is recitation, not SGO tool replacement.",
        "compatible": True,
        "replaces_sgo_tools": False,
    },
    {
        "surface": "market_engine identity",
        "path": "backend/market_engine",
        "via": "odd_id stays empty for Odds API quotes; sgo_odd_id_unavailable for leftover SGO oddIDs",
        "compatible": True,
    },
    {
        "surface": "bookmaker catalog",
        "path": "web/src/lib/platforms.ts and market_snapshot.books",
        "via": "Odds API keys mapped by catalog display name only; unknown keys unavailable",
        "compatible": True,
    },
)

INCOMPATIBLE_CONSUMERS = (
    {
        "surface": "DFS SGO intelligence",
        "path": "projection.sgo_intelligence",
        "compatible": False,
        "lost": True,
        "via": "Listed Odds API Over lines map onto existing DFS prop keys as market_lines thresholds. Per-player records are returned even when unmatched. fantasyScore stays None. Empty fantasyScore is not an SGO fantasyScore replacement.",
    },
    {
        "surface": "Assistant nested SGO tools",
        "path": "backend/assistant/tools.py",
        "compatible": False,
        "lost": True,
        "via": "SGO event IDs stay structured unavailable. Events/odds/props recite the Odds API cache. Team-prop tools return featured_game_markets (game h2h/spreads/totals) and empty team_props. Environment tools return weather/schedule context and null sbme_environment. Steam and SGP stay unavailable.",
    },
)

HANDLED_UNAVAILABLE_CAPABILITIES = (
    {"capability": "live_scores", "reason": "Odds API scores attach on unique id + commence_time. Completed unmatched games render as score-only cards. Period, inning, and clock are not in the documented scores schema."},
    {"capability": "sourced_injuries", "reason": "NFL.com and NBA.com terms do not permit automated collection and commercial display without consent. Official report links only. Live injury HTTP was not sent."},
    {"capability": "sgo_odd_id", "reason": "SGO oddIDs are not Odds API selection ids."},
    {"capability": "sgo_team_props", "reason": "Nested SGO team props are not in the Odds API snapshot."},
    {"capability": "sbme_game_environment", "reason": "Environment is derived from nested SGO markets."},
    {"capability": "dfs_sgo_intelligence", "reason": "SGO nested markets including fantasyScore are not fetched while Odds API serving is on. Listed Odds API Over lines map onto existing DFS prop keys; fantasyScore is not invented."},
)

FEATURE_IMPACT = (
    {
        "surface": "Web approved Market Tools (4 tabs)",
        "class": "working_replacement",
        "note": "Local snapshot/fixture path: Game Odds, Compare, Player Props, Parlay Builder. Namespaced Odds API ids.",
    },
    {
        "surface": "Existing web Market Tools routes under Odds API serving",
        "class": "working_replacement",
        "note": "Layout switch to approved UI. Live-score pages handle structured /sgo/events unavailable.",
    },
    {
        "surface": "Internal snapshot / parlay / resolve APIs",
        "class": "working_replacement",
        "note": "Auth plus Pro Arena or Elite Stack (active/trialing) or canceled-but-paid-through until current_period_end. Unknown active plans are denied. PayKings unchanged.",
    },
    {
        "surface": "Assistant Odds API event/odds/prop lookup",
        "class": "partial_cache_recitation_not_sgo_replacement",
        "note": "Recites saved Odds API events plus de-vigged fair h2h/spreads/totals and per-side book consensus when a complete outcome set exists. SGO event IDs, nested live clock, team props, environment, steam, and SGP remain unavailable. Structured unavailable is not a replacement.",
    },
    {
        "surface": "market_engine selection identity",
        "class": "working_replacement",
        "note": "Odds API quote ids; odd_id stays empty. SGO oddIDs refused.",
    },
    {
        "surface": "Bookmaker catalog mapping",
        "class": "working_replacement",
        "note": "Known Odds API keys map by display name. Unknown keys unavailable.",
    },
    {
        "surface": "Mobile source live-odds contract",
        "class": "working_replacement",
        "note": "Source projects game_id/home_team_name/moneyline. Not proof for the installed App Store client.",
    },
    {
        "surface": "Live scores",
        "class": "working_replacement",
        "note": "Saved Odds API NFL/MLB scores. Unique id plus identical commence_time. Completed games without matching odds render as Odds unavailable. Period/clock not supplied.",
    },
    {
        "surface": "Completed score-only events",
        "class": "working_replacement",
        "note": "Unmatched completed scores keep event id, league, teams, start time, score, and last_update. Labeled Saved result—not a live refresh. Same-team future matchups are not scored from old results.",
    },
    {
        "surface": "Schedules in customer timezone",
        "class": "working_replacement",
        "note": "UTC commence_time from saved odds; UI displays local time with timezone abbreviation.",
    },
    {
        "surface": "Venue weather",
        "class": "working_replacement",
        "note": "Shown only with an event-specific verified venue. Home-team stadium mapping is not used. Saved NWS hourly forecast reused when coordinates and event time match. Forecasts are not observations.",
    },
    {
        "surface": "Sourced injuries",
        "class": "unavailable_capability",
        "note": "NFL.com and NBA.com terms: source-link-only. Official report links plus Live injury feed not connected. Zero injury HTTP. Labeled fixtures are not live coverage.",
    },
    {
        "surface": "Line movement / steam",
        "class": "unavailable_capability",
        "note": "No opening-vs-current movement series. Field is labeled unavailable.",
    },
    {
        "surface": "Assistant live scores, team props, SB ME environment",
        "class": "unavailable_capability",
        "note": "Scores flow through the shared cache when matched. Team-total markets stay empty; featured game h2h/spreads/totals are returned separately as featured_game_markets. Nested SGO environment stays null; venue weather/schedule context is attached when present. Period/clock not invented.",
    },
    {
        "surface": "DFS SGO intelligence",
        "class": "sgo_feature_lost",
        "note": "Listed Odds API Over lines map onto existing DFS prop keys as market_lines thresholds when cached. Per-player records are returned even when unmatched. SGO fantasyScore is gone and not invented. MLB slates stay unenriched until those markets are collected.",
    },
    {
        "surface": "Period / alternate / SGP quotes",
        "class": "unavailable_capability",
        "note": "Not in this Odds API featured snapshot. Combined same-game price suppressed.",
    },
    {
        "surface": "Production Odds API collect and cutover",
        "class": "explicitly_disabled",
        "note": "MARKET_TOOLS_ODDSAPI_ENABLED and MARKET_TOOLS_ODDSAPI_COLLECT default false. Cutover env not applied.",
    },
    {
        "surface": "Provider HTTP from browsing",
        "class": "explicitly_disabled",
        "note": "browsing_triggers_upstream remains false.",
    },
    {
        "surface": "Currently released mobile client",
        "class": "untested_client",
        "note": "App Store/TestFlight bakes EXPO_PUBLIC_API_URL to Railway. getApiUrl() has no runtime override. Isolated overlay released_eas.isolated.json retargets only development profiles to 127.0.0.1:8010. Paid EAS not started. Store submission forbidden.",
    },
    {
        "surface": "Shared Redis in enabled production mode",
        "class": "isolated_live_verified",
        "note": "Isolated Docker Postgres 15 + Redis 7: TEMP TABLE roundtrip, fixture replacement, cross-worker reads, SET NX lock, outage, recovery. Production flags stay off. Named volume was created empty and is not deleted.",
    },
)


def activation_state() -> dict:
    """Report whether cutover or rollback is currently in effect. Importing does not activate."""
    enabled = oddsapi_enabled()
    return {
        "cutover_prepared": True,
        "cutover_applied": enabled,
        "rollback_prepared": True,
        "rollback_applied": not enabled,
        "collect_applied": collect_enabled(),
        "cutover_env": dict(CUTOVER_ENV),
        "rollback_env": dict(ROLLBACK_ENV),
        "compatible_consumers": list(COMPATIBLE_CONSUMERS),
        "incompatible_consumers": list(INCOMPATIBLE_CONSUMERS),
        "handled_unavailable_capabilities": list(HANDLED_UNAVAILABLE_CAPABILITIES),
        "feature_impact": list(FEATURE_IMPACT),
        "feature_gap": feature_gap_report(),
        "mobile_installed_test_path": installed_app_test_path(),
        "final_refresh_test": final_refresh_plan(execute=False),
        "flags": flag_status(),
    }
