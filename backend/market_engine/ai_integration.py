"""
SB ME AI Market Integration — gives SB ME AI access to all five market tools.

The AI uses these functions to answer questions like:
- "Show me the biggest line moves today"
- "Compare the best odds for this game"
- "Show me Aaron Judge's props across books"
- "Are there any mathematical arbitrage opportunities?"
- "Calculate a $100 three-leg parlay"
- "Which player props support my DFS lineup?"
"""
from __future__ import annotations

import logging
from typing import Optional

from providers.integration import SGOIntegration
from market_engine import (
    american_to_decimal, decimal_to_american, implied_probability,
    check_arbitrage, calculate_parlay, ParlayLeg, ParlayResult,
)
from market_engine.live_odds import get_live_markets, format_live_markets, detect_movements
from market_engine.comparison import compare_odds, find_best_price, compute_consensus, format_comparison
from market_engine.props import analyze_player_props, build_dfs_projection, props_intelligence_card
from market_engine.arbitrage import arbitrage_check, scan_arbitrage, format_arbitrage_response
from market_engine.parlay import build_parlay, validate_parlay_legs

logger = logging.getLogger(__name__)


class SBMEAI_MarketTools:
    """
    AI-accessible wrapper for all five market tools.

    Usage from AI routes:
        tools = SBMEAI_MarketTools()
        async with tools:
            moves = await tools.live_odds(event_id="abc")
            comparison = await tools.compare_odds(event_id="abc")
            props = await tools.player_props("MLB", player_id="123")
            arb = await tools.scan_arbitrage("MLB")
            parlay = tools.calculate_parlay([...], stake=100)
    """

    def __init__(self):
        self._sgo: SGOIntegration | None = None

    async def __aenter__(self):
        self._sgo = SGOIntegration()
        await self._sgo.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._sgo:
            await self._sgo.__aexit__(*args)

    # ── Live Odds ─────────────────────────────────────────────

    async def live_odds(self, event_id: str) -> dict:
        """Get live odds and line movements for an event."""
        result = await get_live_markets(self._sgo, event_id)
        return format_live_markets(event_id, result.get("snapshots", {}))

    async def biggest_moves(self, league: str = "MLB", limit: int = 10) -> list[dict]:
        """Find the biggest line moves across a league."""
        events = await self._sgo.get_events(league_id=league)
        all_moves = []
        for event in events[:15]:  # limit to 15 events for rate safety
            try:
                result = await get_live_markets(self._sgo, event.id)
                moves = detect_movements(
                    result.get("snapshots", {}),
                    result.get("snapshots", {}),  # compare current to stored previous
                )
                for m in moves:
                    if m.movement_type.value != "NO_CHANGE":
                        all_moves.append({
                            "event_id": event.id,
                            "matchup": f"{event.away_team} @ {event.home_team}",
                            "bookmaker": m.bookmaker,
                            "market": m.market_identity.stat_id or m.market_identity.market_type.value,
                            "type": m.movement_type.value,
                            "amount": m.movement_amount,
                            "previous": m.previous_line,
                            "current": m.current_line,
                        })
            except Exception as e:
                logger.warning(f"Movement check failed for {event.id}: {e}")

        all_moves.sort(key=lambda x: abs(x["amount"]), reverse=True)
        return all_moves[:limit]

    # ── Odds Comparison ──────────────────────────────────────

    async def compare_odds(self, event_id: str, market_type: str = None) -> dict:
        """Compare odds across bookmakers for an event."""
        result = await get_live_markets(self._sgo, event_id)
        snapshot = result.get("snapshots", {})
        comparison = compare_odds(snapshot, market_type)
        return format_comparison(event_id, comparison, snapshot)

    async def best_prices(self, event_id: str) -> dict:
        """Find best prices for each market in an event."""
        result = await get_live_markets(self._sgo, event_id)
        return find_best_price(result.get("snapshots", {}))

    # ── Player Props ─────────────────────────────────────────

    async def player_props(self, sport: str, player_id: str = None,
                           event_id: str = None) -> dict:
        """Analyze player props across bookmakers."""
        if event_id:
            result = await get_live_markets(self._sgo, event_id)
            props_data = result.get("props", [])
            return analyze_player_props(props_data, player_id, sport)

        # Without event context, return empty
        return {"error": "event_id required for player props analysis"}

    async def dfs_projection_edge(self, sport: str, player_id: str,
                                  dfs_projection: float, event_id: str) -> dict:
        """Compare DFS projection to SGO fantasyScore market line."""
        result = await get_live_markets(self._sgo, event_id)
        props_data = result.get("props", [])
        return build_dfs_projection(player_id, dfs_projection, props_data, sport)

    async def player_intelligence(self, sport: str, player_id: str,
                                  event_id: str) -> dict:
        """Full player intelligence card with props + projection + context."""
        result = await get_live_markets(self._sgo, event_id)
        odds = result.get("odds", {})
        props = result.get("props", [])
        return props_intelligence_card(
            player_id=player_id,
            sport=sport,
            props_data=props,
            odds_data=odds,
        )

    # ── Arbitrage ────────────────────────────────────────────

    def check_arbitrage(self, odds_a: int, odds_b: int,
                        odds_c: int = None, bankroll: float = 1000.0) -> dict:
        """Manual arbitrage calculator."""
        return arbitrage_check(odds_a, odds_b, odds_c, bankroll=bankroll)

    async def scan_arbitrage(self, league: str = "MLB") -> list[dict]:
        """Auto-scan for arbitrage opportunities."""
        events = await self._sgo.get_events(league_id=league)
        opportunities = []
        for event in events[:10]:
            try:
                result = await get_live_markets(self._sgo, event.id)
                opps = scan_arbitrage(
                    event.id,
                    result.get("odds", {}),
                    result.get("props", []),
                )
                opportunities.extend(opps)
            except Exception as e:
                logger.warning(f"Arb scan failed for {event.id}: {e}")
        return format_arbitrage_response(opportunities, league)

    # ── Parlay ──────────────────────────────────────────────

    def calculate_parlay(self, legs: list[dict], stake: float = 100.0) -> dict:
        """Calculate parlay odds and payout."""
        validation = validate_parlay_legs(legs)
        if validation.get("errors"):
            return {"valid": False, "errors": validation["errors"],
                    "warnings": validation.get("warnings", [])}

        parlay_legs = [
            ParlayLeg(
                event_id=leg.get("event_id", ""),
                market=leg.get("market", ""),
                selection=leg.get("selection", ""),
                bookmaker=leg.get("bookmaker", ""),
                odds=int(leg.get("odds", 0)),
            )
            for leg in legs
        ]
        result = build_parlay(parlay_legs, stake)
        return {
            "valid": True,
            "legs": [
                {"event_id": l.event_id, "market": l.market,
                 "selection": l.selection, "bookmaker": l.bookmaker,
                 "odds": l.odds, "decimal": american_to_decimal(l.odds)}
                for l in result.legs
            ],
            "leg_count": result.leg_count,
            "combined_decimal": result.combined_decimal,
            "combined_american": result.combined_american,
            "implied_probability": result.implied_probability,
            "stake": result.stake,
            "potential_payout": result.potential_payout,
            "potential_profit": result.potential_profit,
            "is_same_game": result.is_same_game,
            "sgp_available": result.sgp_available,
            "warnings": validation.get("warnings", []),
        }

    # ── Usage ────────────────────────────────────────────────

    async def usage_stats(self) -> dict:
        """Get SGO API usage statistics."""
        raw = await self._sgo.get_usage()
        return {
            "sgo_usage": raw,
            "cache_stats": {
                "requests": self._sgo._request_count,
            },
        }


# ── Convenience function for AI routes ──

async def ai_market_query(query_type: str, **kwargs) -> dict:
    """
    Single-entry AI query dispatch.

    query_type:
        live_odds, biggest_moves, compare_odds, best_prices,
        player_props, dfs_projection_edge, player_intelligence,
        check_arbitrage, scan_arbitrage, calculate_parlay, usage
    """
    async with SBMEAI_MarketTools() as tools:
        handlers = {
            "live_odds": tools.live_odds,
            "biggest_moves": tools.biggest_moves,
            "compare_odds": tools.compare_odds,
            "best_prices": tools.best_prices,
            "player_props": tools.player_props,
            "dfs_projection_edge": tools.dfs_projection_edge,
            "player_intelligence": tools.player_intelligence,
            "scan_arbitrage": tools.scan_arbitrage,
            "usage": tools.usage_stats,
        }
        handler = handlers.get(query_type)
        if handler:
            return await handler(**kwargs)

        # Synchronous handlers
        if query_type == "check_arbitrage":
            return tools.check_arbitrage(**kwargs)
        if query_type == "calculate_parlay":
            return tools.calculate_parlay(**kwargs)

        return {"error": f"Unknown query_type: {query_type}"}