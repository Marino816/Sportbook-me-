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
        "via": "GET /api/market-tools/internal/snapshot after auth",
        "compatible": True,
    },
    {
        "surface": "internal parlay/resolve",
        "path": "api.market_tools_internal",
        "via": "namespaced oddsapi quote ids",
        "compatible": True,
    },
)

INCOMPATIBLE_CONSUMERS = (
    {
        "surface": "mobile Market Tools",
        "path": "mobile/app/(tabs)/market-tools",
        "reason": "GET /market-tools/live-odds?league=MLB expects SGO nested rows (game_id, home_team_name, moneyline). Odds API cards are a different shape.",
    },
    {
        "surface": "assistant tools",
        "path": "backend/assistant/tools.py",
        "reason": "Tools take optional SGO event IDs and call find_event_by_id on nested /v2/events.",
    },
    {
        "surface": "existing web Market Tools pages",
        "path": "web/src/app/market-tools/{live-odds,compare,player-props,parlay,arbitrage}",
        "reason": "These pages consume SGO event.id from /api/sgo/events. Approved layout replaces them only when Odds API serving is on.",
    },
    {
        "surface": "market_engine identity",
        "path": "backend/market_engine",
        "reason": "odd_id is an SGO oddID; event_id is SGO. Odds API quote ids are namespaced and not oddIDs.",
    },
    {
        "surface": "bookmaker catalog sgo_ids",
        "path": "web/src/lib/platforms.ts",
        "reason": "Sportsbook keys are SGO ids, not Odds API bookmaker keys.",
    },
    {
        "surface": "DFS SGO intelligence",
        "path": "projection.sgo_intelligence / api.sgo_data",
        "reason": "Player/event joins use SGO ids. Unrelated to Market Tools UI but breaks if SGO fetch is blocked globally.",
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
        "flags": flag_status(),
    }
