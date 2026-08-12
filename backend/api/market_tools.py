"""
SB ME Market Tools API — routes for all 5 market tools.

Endpoints:
  GET  /api/market-tools/live-odds?event_id=X        → live odds + movements
  GET  /api/market-tools/compare?event_id=X&market=Y → odds comparison
  GET  /api/market-tools/player-props?player_id=X    → props across books
  POST /api/market-tools/arbitrage/check              → manual arb check
  GET  /api/market-tools/arbitrage/scan?league=MLB    → auto scan
  POST /api/market-tools/parlay/calculate             → parlay calculation
  GET  /api/market-tools/usage                        → SGO usage stats

All routes require authentication (get_current_user).
All responses use wrap_data() format.
All SGO calls go through the cache layer — never expose raw API keys.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market-tools", tags=["SB-Me Market Tools"])


# ══════════════════════════════════════════════════════════════
#  Pydantic Schemas
# ══════════════════════════════════════════════════════════════


class ArbitrageCheckRequest(BaseModel):
    odds_a: int = Field(..., description="American odds for outcome A (e.g. +150, -110)")
    odds_b: int = Field(..., description="American odds for outcome B")
    odds_c: Optional[int] = Field(None, description="American odds for outcome C (3-way markets)")
    event_id: str = ""
    market: str = ""
    outcome_a: str = "Outcome A"
    book_a: str = ""
    outcome_b: str = "Outcome B"
    book_b: str = ""
    outcome_c: str = ""
    book_c: str = ""
    bankroll: float = 1000.0


class ParlayLegRequest(BaseModel):
    event_id: str
    market: str = ""
    selection: str = ""
    book: str = ""
    bookmaker: str = ""
    odds: int


class ParlayCalculateRequest(BaseModel):
    legs: list[ParlayLegRequest]
    stake: float = 100.0


# ══════════════════════════════════════════════════════════════
#  Helper: get SGO cache instance
# ══════════════════════════════════════════════════════════════


async def _get_sgo_integration():
    """Create an SGO integration instance with caching."""
    from providers.integration import SGOIntegration
    return SGOIntegration()


async def _get_market_cache():
    """Create a MarketCache instance (raw data for market engine tools)."""
    from market_engine.cache import MarketCache
    return MarketCache()


# ══════════════════════════════════════════════════════════════
#  1. Live Odds Tracker
# ══════════════════════════════════════════════════════════════


@router.get("/live-odds")
async def get_live_odds(
    event_id: str = Query(..., description="SGO event ID"),
    user: User = Depends(get_current_user),
):
    """
    Get live odds and recent line movements for an event.

    Returns moneyline, spread, total, and player prop snapshots
    with best available prices and bookmaker rankings.
    """
    cache = await _get_market_cache()
    async with cache:
        data = await cache.get_event_data(event_id)

    if not data:
        raise HTTPException(404, f"No market data found for event {event_id}")

    from market_engine.live_odds import track_market, format_live_markets

    snapshots = track_market(
        event_id,
        odds=data.get("odds"),
        props=data.get("props"),
        consensus=data.get("consensus"),
        fair_odds=data.get("fair_odds"),
    )

    formatted = format_live_markets(event_id, snapshots)

    return wrap_data({
        "event_id": event_id,
        "snapshot_count": len(snapshots),
        "markets": formatted,
        "cache_hits": cache.stats.cache_hits,
        "cache_misses": cache.stats.cache_misses,
    }, source="sportsgameodds" if data.get("odds") else "cached")


# ══════════════════════════════════════════════════════════════
#  2. Odds Comparison
# ══════════════════════════════════════════════════════════════


@router.get("/compare")
async def compare_odds(
    event_id: str = Query(..., description="SGO event ID"),
    market_type: str = Query("all", description="Filter: moneyline, spread, total, all"),
    user: User = Depends(get_current_user),
):
    """
    Side-by-side odds comparison across all available bookmakers.

    For each market (moneyline, spread, total), shows every book's
    line and price, highlights the best price per side, and computes
    consensus lines.
    """
    cache = await _get_market_cache()
    async with cache:
        data = await cache.get_event_data(event_id)

    if not data:
        raise HTTPException(404, f"No market data found for event {event_id}")

    from market_engine.comparison import compare_odds as _compare_odds

    result = _compare_odds(
        event_id,
        odds=data.get("odds"),
        props=data.get("props"),
    )

    # Filter by market type if requested
    if market_type != "all":
        result["markets"] = [
            m for m in result.get("markets", [])
            if m.get("market") == market_type
        ]

    return wrap_data(result, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  3. Player Props Analyzer
# ══════════════════════════════════════════════════════════════


@router.get("/player-props")
async def get_player_props(
    player_id: str = Query("", description="SGO player ID"),
    sport: str = Query("MLB", description="Sport code (MLB, NFL, NBA, NHL)"),
    event_id: str = Query("", description="Optional: filter to specific event"),
    user: User = Depends(get_current_user),
):
    """
    Aggregate player prop markets across all available bookmakers.

    For each prop market, returns:
      - book_count, consensus_line, best_over_price, best_under_price
      - line_range, market_direction
      - per-book breakdown

    If event_id is provided, only props for that event are fetched.
    If player_id is provided, only that player's props are returned.
    """
    from market_engine.props import analyze_player_props, props_intelligence_card

    if not event_id:
        # Need to find an event for the sport — fetch events and use first active one
        sgo = await _get_sgo_integration()
        async with sgo:
            events = await sgo.get_events(league_id=sport)
        if not events:
            raise HTTPException(404, f"No active events found for {sport}")
        # Use the first available event
        event_id = events[0].id

    cache = await _get_market_cache()
    async with cache:
        data = await cache.get_event_data(event_id)

    if not data or not data.get("props"):
        raise HTTPException(404, f"No player prop data found for event {event_id}")

    analysis = analyze_player_props(
        data["props"],
        player_id=player_id if player_id else None,
        sport=sport,
    )

    # If player_id specified, build full intelligence card
    if player_id:
        player_props = analysis  # single player's market dict
        card = props_intelligence_card(
            player_id=player_id,
            player_name="",  # Will be populated by SGO if available
            sport=sport,
            props_analysis=player_props,
        )
        return wrap_data(card, source="sportsgameodds")

    return wrap_data({
        "event_id": event_id,
        "sport": sport,
        "player_count": len(analysis),
        "players": analysis,
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  4. Arbitrage Check (Manual Calculator)
# ══════════════════════════════════════════════════════════════


@router.post("/arbitrage/check")
async def arbitrage_check_endpoint(
    body: ArbitrageCheckRequest,
    user: User = Depends(get_current_user),
):
    """
    Manual arbitrage calculator — check if a set of American odds presents
    an arbitrage opportunity.

    Accepts 2 or 3 outcomes (for 3-way markets like soccer moneyline).

    All calculations use decimal odds internally; never on American odds.

    NOTE: Results are mathematical comparisons only — not guaranteed profit.
    Verify availability and limits with each sportsbook before wagering.
    """
    from market_engine.arbitrage import arbitrage_check

    opp = arbitrage_check(
        odds_a=body.odds_a,
        odds_b=body.odds_b,
        odds_c=body.odds_c,
        event_id=body.event_id,
        market=body.market,
        outcome_a=body.outcome_a,
        book_a=body.book_a,
        outcome_b=body.outcome_b,
        book_b=body.book_b,
        outcome_c=body.outcome_c,
        book_c=body.book_c,
        bankroll=body.bankroll,
    )

    if opp is None:
        return wrap_data({
            "arbitrage_exists": False,
            "message": "No mathematical arbitrage opportunity found. Combined implied probability >= 100%.",
            "combined_implied": round(
                (1.0 / __import__("market_engine").american_to_decimal(body.odds_a) +
                 1.0 / __import__("market_engine").american_to_decimal(body.odds_b) +
                 (1.0 / __import__("market_engine").american_to_decimal(body.odds_c) if body.odds_c else 0)),
                4
            ),
            "disclaimer": "Mathematical comparison only — not guaranteed profit.",
        }, source="calculation")

    from market_engine.arbitrage import _format_opp
    result = _format_opp(opp)
    result["arbitrage_exists"] = True

    return wrap_data(result, source="calculation")


# ══════════════════════════════════════════════════════════════
#  5. Arbitrage Scanner (Auto)
# ══════════════════════════════════════════════════════════════


@router.get("/arbitrage/scan")
async def arbitrage_scan(
    league: str = Query("MLB", description="League ID to scan (MLB, NFL, NBA, NHL)"),
    user: User = Depends(get_current_user),
):
    """
    Auto-scan active events for mathematical arbitrage opportunities.

    Scans:
      - Moneyline: best home vs best away prices across books
      - Totals: over/under at exact same line from different books

    NEVER compares incompatible lines (e.g. Over 7.5 ≠ Under 8.5).

    All results are labeled as mathematical market comparisons,
    not guaranteed profit.
    """
    from market_engine.arbitrage import scan_arbitrage, format_arbitrage_response

    # Get active events
    sgo = await _get_sgo_integration()
    async with sgo:
        events = await sgo.get_events(league_id=league)

    if not events:
        return wrap_data(format_arbitrage_response("", [], league), source="sportsgameodds")

    # Scan each event
    all_opportunities = []
    cache = await _get_market_cache()
    async with cache:
        for event in events[:10]:  # Limit to 10 events to avoid rate limits
            eid = event.id
            try:
                data = await cache.get_event_data(eid)
                if not data:
                    continue

                opps = scan_arbitrage(
                    eid,
                    odds=data.get("odds"),
                    props=data.get("props"),
                )
                all_opportunities.extend(opps)
            except Exception as e:
                logger.warning(f"Failed to scan event {eid}: {e}")
                continue

    response = format_arbitrage_response(
        "",  # multiple events
        all_opportunities,
        league,
    )
    response["events_scanned"] = min(len(events), 10)

    return wrap_data(response, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  6. Parlay Calculator
# ══════════════════════════════════════════════════════════════


@router.post("/parlay/calculate")
async def parlay_calculate(
    body: ParlayCalculateRequest,
    user: User = Depends(get_current_user),
):
    """
    Calculate parlay odds and payout from a list of legs.

    Each leg must include:
      - event_id: str
      - odds: int (American odds, e.g. -110, +150)
      - market: str (optional, e.g. "moneyline", "total")
      - selection: str (optional, e.g. "over", "home")
      - book: str or bookmaker: str (optional)

    Supports 2, 3, 4, 5+ legs.
    Cross-game parlays: fully supported.
    Same-game parlays: labeled with SGP availability warning.
    """
    from market_engine.parlay import build_parlay_dict, validate_parlay_legs

    # Convert Pydantic models to dicts
    legs_dicts = []
    for leg in body.legs:
        legs_dicts.append({
            "event_id": leg.event_id,
            "market": leg.market,
            "selection": leg.selection,
            "book": leg.book or leg.bookmaker,
            "bookmaker": leg.bookmaker or leg.book,
            "odds": leg.odds,
        })

    # Validate
    validation = validate_parlay_legs(legs_dicts)
    if not validation["valid"]:
        raise HTTPException(422, detail={
            "message": "Invalid parlay legs",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        })

    # Calculate
    result = build_parlay_dict(legs_dicts, body.stake)

    # Add validation warnings if any
    if validation["warnings"]:
        result["warnings"] = validation["warnings"]

    return wrap_data(result, source="calculation")


@router.post("/parlay/validate")
async def parlay_validate(
    body: ParlayCalculateRequest,
    user: User = Depends(get_current_user),
):
    """
    Validate parlay legs without calculating.

    Returns validation errors and warnings before the user commits to calculation.
    """
    from market_engine.parlay import validate_parlay_legs

    legs_dicts = [
        {
            "event_id": leg.event_id,
            "market": leg.market,
            "selection": leg.selection,
            "book": leg.book or leg.bookmaker,
            "bookmaker": leg.bookmaker or leg.book,
            "odds": leg.odds,
        }
        for leg in body.legs
    ]

    validation = validate_parlay_legs(legs_dicts)
    return wrap_data(validation, source="validation")


# ══════════════════════════════════════════════════════════════
#  7. API Usage Stats
# ══════════════════════════════════════════════════════════════


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
):
    """
    Get SGO API usage statistics and rate limit status.

    Returns:
      - SGO provider stats (requests, errors, retries)
      - Cache statistics (hits, misses)
      - Request history
    """
    try:
        sgo = await _get_sgo_integration()
        async with sgo:
            sgo_usage = await sgo.get_usage()

        cache = await _get_market_cache()
        async with cache:
            cache_usage = await cache.get_usage()

        return wrap_data({
            "provider": "SportsGameOdds",
            "sgo_usage": sgo_usage if sgo_usage else {"status": "unavailable"},
            "cache_stats": {
                "requests": cache.stats.requests if cache else 0,
                "hits": cache.stats.cache_hits if cache else 0,
                "misses": cache.stats.cache_misses if cache else 0,
                "objects_consumed": cache.stats.objects_consumed if cache else 0,
                "last_request": (
                    cache.stats.last_request_at.isoformat()
                    if cache and cache.stats.last_request_at else None
                ),
            },
        }, source="sportsgameodds")
    except Exception as e:
        logger.warning(f"Usage stats unavailable: {e}")
        return wrap_data({
            "provider": "SportsGameOdds",
            "status": "unavailable",
            "message": "Could not fetch usage stats at this time.",
        }, source="cached")