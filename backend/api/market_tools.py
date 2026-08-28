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
    event_id: str = Query("", description="Optional SGO event ID"),
    league: str = Query("MLB", description="Rookie league ID (MLB, EPL, UEFA_CHAMPIONS_LEAGUE, …)"),
    slate_id: Optional[int] = Query(None, description="Ignored — DFS slate IDs are not SGO event IDs"),
    user: User = Depends(get_current_user),
):
    """Live odds from the canonical nested /v2/events cache.

    Accepts optional event_id. When omitted, returns the league game list
    (mobile Market Tools). slate_id is accepted only so old clients do not 422;
    it is not used as an SGO identifier.
    """
    from providers.sgo_rookie import normalize_league_id
    from providers.nested_events import (
        derive_game_environment,
        find_cached_event,
        find_event_by_id,
        load_cached_or_fetch_events,
        sbevent_to_game_row,
    )

    league_u = normalize_league_id(league)
    events = await load_cached_or_fetch_events(league_u)

    if event_id:
        evt = find_event_by_id(events, event_id) or find_cached_event(event_id)
        if not evt:
            raise HTTPException(404, f"No nested market data found for event {event_id}")
        row = sbevent_to_game_row(evt)
        return wrap_data({
            "event_id": event_id,
            "league": league_u,
            "games": [row],
            "count": 1,
            "sbme_environment": derive_game_environment(evt),
            **row,
        }, source="sgo_nested_cache")

    games = [sbevent_to_game_row(e) for e in events if isinstance(e, dict)]
    return wrap_data({
        "league": league_u,
        "games": games,
        "count": len(games),
        "note": "Canonical nested SportsGameOdds /v2/events. slate_id is not an event identifier.",
    }, source="sgo_nested_cache")


# ══════════════════════════════════════════════════════════════
#  2. Odds Comparison
# ══════════════════════════════════════════════════════════════


@router.get("/compare")
async def compare_odds(
    event_id: str = Query(..., description="SGO event ID"),
    market_type: str = Query("all", description="Filter: moneyline, spread, total, all"),
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    """Side-by-side bookmaker lines from nested event.markets — no dedicated /odds URL."""
    from providers.sgo_rookie import normalize_league_id
    from providers.nested_events import (
        derive_game_environment,
        find_cached_event,
        find_event_by_id,
        load_cached_or_fetch_events,
        sbevent_player_props,
        sbevent_team_props,
        sbevent_to_compare_books,
    )

    events = await load_cached_or_fetch_events(normalize_league_id(league))
    evt = find_event_by_id(events, event_id) or find_cached_event(event_id)
    if not evt:
        raise HTTPException(404, f"No nested market data found for event {event_id}")

    home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
    away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
    books = sbevent_to_compare_books(evt)
    return wrap_data({
        "event_id": event_id,
        "home_team": home.get("abbreviation") or home.get("name"),
        "away_team": away.get("abbreviation") or away.get("name"),
        "bookmakers": books,
        "books": books,
        "player_props": sbevent_player_props(evt) if market_type in ("all", "props") else [],
        "team_props": sbevent_team_props(evt) if market_type in ("all", "team_prop", "team_props") else [],
        "sbme_environment": derive_game_environment(evt),
        "market_type": market_type,
    }, source="sgo_nested_cache")


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
    """
    Player props from nested event.markets (hits / HR / K research lines).

    Betting O/U thresholds are research signals — not fantasy-point projections.
    """
    from providers.sgo_rookie import normalize_league_id
    from providers.nested_events import (
        find_cached_event,
        find_event_by_id,
        load_cached_or_fetch_events,
        sbevent_player_props,
        sbevent_team_props,
    )

    league = normalize_league_id(sport)
    events = await load_cached_or_fetch_events(league)
    if event_id:
        evt = find_event_by_id(events, event_id) or find_cached_event(event_id)
        events = [evt] if evt else []
    props = []
    team_props = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        props.extend(sbevent_player_props(evt, player_id=player_id))
        if not player_id:
            team_props.extend(sbevent_team_props(evt))

    if not props and not team_props:
        return wrap_data({
            "event_id": event_id or None,
            "sport": league,
            "player_count": 0,
            "players": [],
            "props": [],
            "team_props": [],
            "available": False,
            "note": "No nested player-prop or team-prop markets in the cached /v2/events payload.",
        }, source="sgo_nested_cache")

    return wrap_data({
        "event_id": event_id or None,
        "sport": league,
        "player_count": len({p.get("player_id") for p in props}),
        "players": props,
        "props": props,
        "team_props": team_props,
        "available": True,
        "note": "SGO betting O/U thresholds from nested events. Not fantasy-point projections.",
    }, source="sgo_nested_cache")


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
    from market_engine.arbitrage import arbitrage_check, format_arbitrage_response
    from providers.nested_events import load_cached_or_fetch_events, sbevent_to_compare_books
    from providers.sgo_rookie import normalize_league_id

    league_u = normalize_league_id(league)
    events = await load_cached_or_fetch_events(league_u)
    if not events:
        return wrap_data(format_arbitrage_response("", [], league_u), source="sgo_nested_cache")

    all_opportunities = []
    scanned = 0
    for evt in events[:20]:
        if not isinstance(evt, dict):
            continue
        scanned += 1
        eid = str(evt.get("id") or "")
        books = sbevent_to_compare_books(evt)
        home_candidates = [(b.get("bookmaker_name"), b.get("moneyline_home")) for b in books if b.get("moneyline_home") is not None]
        away_candidates = [(b.get("bookmaker_name"), b.get("moneyline_away")) for b in books if b.get("moneyline_away") is not None]
        if not home_candidates or not away_candidates:
            continue
        # Best American price = highest decimal conversion handled inside arbitrage_check
        for book_a, odds_a in home_candidates:
            for book_b, odds_b in away_candidates:
                if book_a == book_b:
                    continue
                try:
                    opp = arbitrage_check(
                        odds_a=int(odds_a),
                        odds_b=int(odds_b),
                        event_id=eid,
                        market="moneyline",
                        outcome_a="home",
                        book_a=str(book_a or ""),
                        outcome_b="away",
                        book_b=str(book_b or ""),
                    )
                except Exception:
                    continue
                if opp is not None:
                    from market_engine.arbitrage import _format_opp
                    all_opportunities.append(_format_opp(opp) if not isinstance(opp, dict) else opp)

    response = format_arbitrage_response("", all_opportunities, league_u)
    response["events_scanned"] = scanned
    return wrap_data(response, source="sgo_nested_cache")


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
        from providers.sdk_provider import SdkSgoProvider
        sgo_usage = await SdkSgoProvider().get_usage()

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
        }, source="sportsgameodds_v2_account_usage")
    except Exception as e:
        logger.warning(f"Usage stats unavailable: {e}")
        return wrap_data({
            "provider": "SportsGameOdds",
            "status": "unavailable",
            "message": "Could not fetch usage stats at this time.",
        }, source="cached")