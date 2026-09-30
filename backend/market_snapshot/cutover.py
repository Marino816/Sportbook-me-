"""Cutover and rollback configuration. Neither is activated by importing this module."""

from __future__ import annotations

from market_snapshot.flags import collect_enabled, flag_status, oddsapi_enabled

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
        "surface": "assistant tools",
        "path": "backend/assistant/tools.py",
        "via": "Odds API cache rows; SGO event IDs return structured unavailable",
        "compatible": True,
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
    {
        "surface": "DFS SGO intelligence",
        "path": "projection.sgo_intelligence",
        "via": "Empty dict (no player keys) when SGO is blocked; no invented projections",
        "compatible": True,
    },
)

INCOMPATIBLE_CONSUMERS = ()

HANDLED_UNAVAILABLE_CAPABILITIES = (
    {"capability": "live_scores", "reason": "Odds API snapshot has no live scores."},
    {"capability": "sgo_odd_id", "reason": "SGO oddIDs are not Odds API selection ids."},
    {"capability": "sgo_team_props", "reason": "Nested SGO team props are not in the Odds API snapshot."},
    {"capability": "sbme_game_environment", "reason": "Environment is derived from nested SGO markets."},
    {"capability": "dfs_sgo_intelligence", "reason": "SGO player prop intelligence is not fetched while Odds API serving is on."},
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
        "note": "Auth plus Pro Arena or Elite Stack (active/trialing). Unknown active plans are denied.",
    },
    {
        "surface": "Assistant Odds API event/odds/prop lookup",
        "class": "working_replacement",
        "note": "Reads shared cache. SGO event IDs return unavailable. Not a live-score source.",
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
        "class": "unavailable_capability",
        "note": "Odds API featured snapshot has no scores/period/status. /sgo/events is blocked while serving Odds API.",
    },
    {
        "surface": "Line movement / steam",
        "class": "unavailable_capability",
        "note": "No opening-vs-current movement series. Field is labeled unavailable.",
    },
    {
        "surface": "Assistant live scores, team props, SB ME environment",
        "class": "unavailable_capability",
        "note": "Structured unavailable. Tools must not invent scores or nested SGO environment.",
    },
    {
        "surface": "DFS SGO intelligence",
        "class": "unavailable_capability",
        "note": "build_sgo_intelligence returns {} when SGO is blocked. No invented player projections.",
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
        "note": "Installed/App Store binary was not rebuilt or exercised. Source edits do not establish compatibility.",
    },
    {
        "surface": "Shared Redis in enabled production mode",
        "class": "untested_client",
        "note": "Behavior is coded and unit-tested. Live Docker Postgres/Redis verification remains blocked until Docker exists.",
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
        "flags": flag_status(),
    }
