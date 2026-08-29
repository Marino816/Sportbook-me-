"""SB ME SGO Data API — Rookie-tier compatible, extracts all data from /v2/events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain import User
from api.auth import get_current_user, require_admin
from api.utils import wrap_data
from providers.event_parser import (
    ParsedEventMarkets,
    parse_event_odds,
    extract_bookmaker_odds_table,
    build_player_props_list,
)
from providers.sbevent import SBEvent
from providers.sgo_rookie import NESTED_EVENT_TTL_SECONDS, normalize_league_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sgo", tags=["SGO Data"])


# ── Redis helpers ────────────────────────────────────────────

def _rget(key: str):
    from providers.redis_client import get_redis_client
    r = get_redis_client()
    if r is None:
        return None
    try:
        v = r.get(key)
        return json.loads(v) if v else None
    except Exception:
        return None


def _rset(key: str, data, ttl: int = NESTED_EVENT_TTL_SECONDS):
    from providers.redis_client import get_redis_client
    r = get_redis_client()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(data, default=str).encode())
    except Exception:
        pass


# ── Helpers ──────────────────────────────────────────────────
def _canonical_event_provider():
    """The official SDK is the sole source for the canonical event feed."""
    from providers.sdk_provider import SdkSgoProvider
    return SdkSgoProvider()


def _clear_obsolete_event_model_keys(league: str) -> None:
    """Remove only legacy normalized-event keys; never flush the Redis store."""
    from providers.redis_client import get_redis_client
    redis = get_redis_client()
    if redis is None:
        return
    try:
        normalized_league = normalize_league_id(league)
        redis.delete(
            f"sgo_cache:events:{normalized_league}",
            f"sgo_cache:raw_events:{normalized_league}",
        )
    except Exception as exc:
        logger.warning("Unable to remove obsolete SGO event keys: %s", exc)


async def _get_sgo():
    """Legacy integration retained only for non-canonical auxiliary routes."""
    from providers.integration import SGOIntegration
    return SGOIntegration()


async def _get_raw_events(league: str):
    """Fetch raw SGO events with full nested odds/players/teams."""
    sgo = await _get_sgo()
    async with sgo:
        return await sgo.get_raw_events(league.upper())


# ── Helpers ──────────────────────────────────────────────────

def _val(obj, attr, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _safe_str(val, default=""):
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return str(val.get("name", val.get("state", val.get("display", str(val)))))
    return str(val)


def _player_to_dict(player) -> dict:
    return {
        "player_id": _val(player, "player_id", _val(player, "id", "")),
        "name": _val(player, "name", _val(player, "player_name", "")),
        "team": _val(player, "team", ""),
        "position": _val(player, "position", ""),
        "league": _val(player, "league", ""),
        "sport": _val(player, "sport", ""),
    }


def _event_summary(event, include_odds: bool = False) -> dict:
    """Build a frontend-ready event summary, optionally with parsed odds."""
    # Team info
    teams = _val(event, "teams")
    home = {}
    away = {}
    if isinstance(teams, dict):
        home_raw = teams.get("home", {})
        away_raw = teams.get("away", {})
        home = {
            "name": home_raw.get("names", {}).get("long", "") if isinstance(home_raw, dict) else "",
            "abbreviation": home_raw.get("names", {}).get("short", "") if isinstance(home_raw, dict) else "",
            "team_id": home_raw.get("teamID", "") if isinstance(home_raw, dict) else "",
        }
        away = {
            "name": away_raw.get("names", {}).get("long", "") if isinstance(away_raw, dict) else "",
            "abbreviation": away_raw.get("names", {}).get("short", "") if isinstance(away_raw, dict) else "",
            "team_id": away_raw.get("teamID", "") if isinstance(away_raw, dict) else "",
        }

    # Status
    status_raw = _val(event, "status")
    if isinstance(status_raw, dict):
        if status_raw.get("live"):
            display = "LIVE"
        elif status_raw.get("completed") or status_raw.get("finalized"):
            display = "FINAL"
        else:
            display = "SCHEDULED"
    else:
        display = _safe_str(status_raw, "SCHEDULED")

    # Start time
    start_time = None
    if isinstance(status_raw, dict):
        sa = status_raw.get("startsAt")
        if sa:
            start_time = sa

    # Scores
    home_score = None
    away_score = None
    results = _val(event, "results")
    if isinstance(results, dict):
        game = results.get("game", {})
        if isinstance(game, dict):
            home_score = game.get("home")
            away_score = game.get("away")

    # Period
    period = None
    if isinstance(status_raw, dict):
        if status_raw.get("live"):
            cpid = status_raw.get("currentPeriodID", "")
            period = cpid

    result = {
        "event_id": _val(event, "eventID", ""),
        "home_team": home,
        "away_team": away,
        "start_time": start_time,
        "status": display,
        "home_score": home_score,
        "away_score": away_score,
        "period": period,
    }

    if include_odds:
        raw_odds = _val(event, "odds")
        raw_players = _val(event, "players")
        if isinstance(raw_odds, dict):
            parsed = parse_event_odds(
                result["event_id"],
                raw_odds,
                raw_players if isinstance(raw_players, dict) else None,
            )
            table = extract_bookmaker_odds_table(parsed)
            result["books"] = [
                {"bookmaker": k, **v} for k, v in table.items()
            ]
            result["book_count"] = len(result["books"])
            result["moneylines_count"] = len(parsed.moneylines)
            result["spreads_count"] = len(parsed.spreads)
            result["totals_count"] = len(parsed.totals)

    return result


# ── Canonical SBEvent → JSON ──────────────────────────────────

def _sb_event_to_dict(evt: SBEvent) -> dict:
    """ONE canonical JSON format shared by all pages."""
    markets = []
    for m in evt.markets:
        books = [{
            "bookmaker": b.bookmaker, "available": b.available,
            "moneyline": b.moneyline, "spread": b.spread,
            "over_under": b.over_under, "is_main_line": b.is_main_line,
            "last_updated": b.last_updated,
            "opening_odds": b.opening_odds,
            "opening_spread": b.opening_spread,
            "opening_over_under": b.opening_over_under,
            "open_moneyline": b.opening_odds,
            "close_odds": b.close_odds,
            "close_moneyline": b.close_odds,
            "close_spread": b.close_spread,
            "close_over_under": b.close_over_under,
            "book_odds": b.moneyline,
        } for b in m.books]
        markets.append({
            "odd_id": m.odd_id, "market_name": m.market_name,
            "bet_type": m.bet_type, "side": m.side,
            "player_id": m.player_id, "player_name": m.player_name,
            "stat_entity_id": m.stat_entity_id, "stat_id": m.stat_id,
            "period_id": m.period_id,
            "is_main_line": bool(m.is_main_line or any(b.is_main_line for b in m.books)),
            "fair_odds": m.fair_odds, "fair_spread": m.fair_spread,
            "fair_over_under": m.fair_over_under,
            "book_odds": m.book_odds, "book_spread": m.book_spread,
            "book_over_under": m.book_over_under, "books": books,
        })
    payload = {
        "id": evt.id, "sport": evt.sport, "league": evt.league,
        "start_time": evt.start_time, "status": evt.status,
        "status_display": evt.status_display, "venue": evt.venue,
        "home_team": {"name": evt.home_team.name, "abbreviation": evt.home_team.abbreviation, "team_id": evt.home_team.team_id},
        "away_team": {"name": evt.away_team.name, "abbreviation": evt.away_team.abbreviation, "team_id": evt.away_team.team_id},
        "home_score": evt.home_score, "away_score": evt.away_score, "period": evt.period,
        "players": [{"player_id": p.player_id, "name": p.name, "team_id": p.team_id, "position": p.position} for p in evt.players],
        "markets": markets, "bookmakers": evt.bookmakers,
        "results": evt.results,
    }
    try:
        from providers.nested_events import derive_game_environment
        payload["sbme_environment"] = derive_game_environment(payload)
    except Exception:
        payload["sbme_environment"] = None
    return payload


# ── Routes ───────────────────────────────────────────────────

@router.get("/events")
async def get_events(
    league: str = Query(..., description="League ID (MLB, NFL, NBA, etc.)"),
    user: User = Depends(get_current_user),
):
    """Canonical SDK Event → SBEvent JSON array for every SGO consumer."""
    normalized_league = normalize_league_id(league)
    cache_key = f"sgo:v2:sbevents:{normalized_league}"
    cached = _rget(cache_key)
    if isinstance(cached, list) and cached:
        return wrap_data(cached, source="cached")

    try:
        # Do not enter SGOIntegration here: it initializes the legacy raw-event
        # provider. This route is intentionally SDK → SBEvent → JSON only.
        sb_events = await _canonical_event_provider().get_sb_events(normalized_league)
    except Exception as exc:
        logger.error("Official SGO SDK event fetch failed for %s: %s", normalized_league, exc)
        # Never replace a previously valid canonical cache entry with an error.
        return wrap_data([], source="sportsgameodds")

    if not sb_events:
        # An empty upstream response is not cacheable and cannot overwrite LKG data.
        return wrap_data([], source="sportsgameodds")

    events_list = [_sb_event_to_dict(event) for event in sb_events]
    _clear_obsolete_event_model_keys(normalized_league)
    _rset(cache_key, events_list, ttl=NESTED_EVENT_TTL_SECONDS)
    return wrap_data(events_list, source="sportsgameodds")


@router.get("/events/{event_id}/odds")
async def get_event_odds(event_id: str, user: User = Depends(get_current_user)):
    """Moneyline/spread/total per bookmaker from the nested /v2/events cache."""
    from providers.nested_events import extract_nested_odds_payload, find_cached_event

    evt = find_cached_event(event_id)
    if not evt:
        return wrap_data({"event_id": event_id, "books": [], "message": "Event not found"}, source="cached")
    payload = extract_nested_odds_payload(evt)
    return wrap_data(payload, source="sgo_nested_cache")


@router.get("/events/{event_id}/props")
async def get_event_props(event_id: str, user: User = Depends(get_current_user)):
    """Player and team props from nested event.markets — not /props/players/{id}."""
    from providers.nested_events import find_cached_event, sbevent_player_props, sbevent_team_props

    evt = find_cached_event(event_id)
    if not evt:
        return wrap_data({
            "event_id": event_id, "players": [], "prop_count": 0,
            "team_props": [], "message": "Event not found",
        }, source="cached")
    props = sbevent_player_props(evt)
    team_props = sbevent_team_props(evt)
    return wrap_data({
        "event_id": event_id,
        "players": props,
        "props": props,
        "prop_count": len(props),
        "team_props": team_props,
        "source": "nested_v2_events",
    }, source="sgo_nested_cache")


@router.get("/bookmakers")
async def get_bookmakers(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    """Available bookmakers from the canonical nested event cache."""
    from providers.nested_events import load_cached_or_fetch_events

    events = await load_cached_or_fetch_events(normalize_league_id(league))
    bookmakers: set[str] = set()
    for e in events:
        if not isinstance(e, dict):
            continue
        for name in e.get("bookmakers") or []:
            if name:
                bookmakers.add(str(name))
        for m in e.get("markets") or []:
            if not isinstance(m, dict):
                continue
            for b in m.get("books") or []:
                if isinstance(b, dict) and b.get("bookmaker"):
                    bookmakers.add(str(b["bookmaker"]))
    sorted_bm = sorted(bookmakers)
    return wrap_data({"bookmakers": sorted_bm, "count": len(sorted_bm)}, source="sgo_nested_cache")


@router.get("/sports")
async def get_sports(user: User = Depends(get_current_user)):
    try:
        sgo = await _get_sgo()
        async with sgo:
            sports = await sgo.get_sports()
    except Exception as e:
        logger.error(f"Failed to fetch sports: {e}")
        return wrap_data({"sports": [], "count": 0, "status": "unavailable"}, source="cached")

    sports_list = [{
        "sport_id": s.get("sportID", "") if isinstance(s, dict) else getattr(s, "sport_id", ""),
        "name": s.get("name", "") if isinstance(s, dict) else getattr(s, "name", ""),
    } for s in sports]
    return wrap_data({"sports": sports_list, "count": len(sports_list)}, source="sportsgameodds")


@router.get("/teams")
async def get_teams(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    try:
        sgo = await _get_sgo()
        async with sgo:
            teams = await sgo.get_teams(league=normalize_league_id(league))
    except Exception as e:
        logger.error(f"Failed to fetch teams for league={league}: {e}")
        return wrap_data({"teams": [], "count": 0, "status": "unavailable"}, source="cached")

    teams_list = [{
        "team_id": t.get("teamID", "") if isinstance(t, dict) else getattr(t, "team_id", ""),
        "name": t.get("names", {}).get("long", "") if isinstance(t, dict) \
                else getattr(t, "name", ""),
        "abbreviation": t.get("names", {}).get("short", "") if isinstance(t, dict) \
                         else getattr(t, "abbreviation", ""),
    } for t in teams]
    return wrap_data({"teams": teams_list, "league": normalize_league_id(league), "count": len(teams_list)},
                     source="sportsgameodds")


@router.get("/players")
async def get_players(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    try:
        sgo = await _get_sgo()
        async with sgo:
            players = await sgo.get_players(league_id=normalize_league_id(league))
    except Exception as e:
        logger.error(f"Failed to fetch players: {e}")
        return wrap_data({"players": [], "count": 0, "status": "unavailable"}, source="cached")

    players_list = []
    for p in players:
        if isinstance(p, dict):
            pid = p.get("playerID", "")
            names = p.get("names", {}) or {}
            players_list.append({
                "player_id": pid,
                "name": names.get("long", names.get("short", pid)),
                "team": p.get("team", ""),
                "position": p.get("position", ""),
                "league": normalize_league_id(league),
            })
        else:
            players_list.append({
                "player_id": getattr(p, "player_id", getattr(p, "id", "")),
                "name": getattr(p, "name", getattr(p, "player_name", "")),
                "team": getattr(p, "team", ""),
                "position": getattr(p, "position", ""),
                "league": normalize_league_id(league),
            })
    return wrap_data({"players": players_list, "count": len(players_list)}, source="sportsgameodds")


@router.get("/leagues")
async def get_leagues(user: User = Depends(get_current_user)):
    """Leagues available to this Rookie key from GET /v2/leagues/."""
    try:
        leagues = await _canonical_event_provider().get_leagues()
    except Exception as exc:
        logger.warning("SGO leagues fetch failed: %s", exc)
        from providers.sgo_rookie import catalog_fallback
        leagues = catalog_fallback()
    return wrap_data({
        "leagues": leagues,
        "count": len(leagues),
        "soccer": [row for row in leagues if (row.get("sportID") or "").upper() == "SOCCER"],
    }, source="sportsgameodds_v2_leagues")


@router.get("/events/{event_id}/fair-odds")
async def get_fair_odds(event_id: str, user: User = Depends(get_current_user)):
    """Fair odds from nested event.markets — not a dedicated /fair-odds/{id} fetch."""
    from providers.nested_events import extract_nested_fair_odds, find_cached_event

    evt = find_cached_event(event_id)
    if not evt:
        return wrap_data({"event_id": event_id, "markets": [], "message": "Event not found"}, source="cached")
    markets = extract_nested_fair_odds(evt)
    return wrap_data({
        "event_id": event_id,
        "source": "nested_v2_events",
        "markets": markets,
        "count": len(markets),
    }, source="sgo_nested_cache")


@router.get("/events/{event_id}/consensus")
async def get_consensus(event_id: str, user: User = Depends(get_current_user)):
    """Book consensus from nested bookOdds — not a dedicated /consensus/{id} fetch."""
    from providers.nested_events import extract_nested_consensus, find_cached_event

    evt = find_cached_event(event_id)
    if not evt:
        return wrap_data({"event_id": event_id, "message": "Event not found"}, source="cached")
    return wrap_data(extract_nested_consensus(evt), source="sgo_nested_cache")


@router.get("/platforms")
async def get_platforms(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    """55-platform catalog vs currently observed nested SGO bookmaker IDs."""
    from providers.nested_events import load_cached_events
    from providers.sgo_platforms import classify_observed_books
    from providers.sgo_rookie import normalize_league_id

    events = load_cached_events(normalize_league_id(league))
    observed: set[str] = set()
    for e in events:
        if not isinstance(e, dict):
            continue
        for name in e.get("bookmakers") or []:
            if name:
                observed.add(str(name))
        for m in e.get("markets") or []:
            if not isinstance(m, dict):
                continue
            for b in m.get("books") or []:
                if isinstance(b, dict) and b.get("bookmaker"):
                    observed.add(str(b["bookmaker"]))
    payload = classify_observed_books(observed)
    payload["league"] = normalize_league_id(league)
    payload["observed_bookmakers"] = sorted(observed)
    return wrap_data(payload, source="sgo_nested_cache")


@router.get("/usage")
async def get_usage(admin: User = Depends(require_admin)):
    """Admin-only GET /v2/account/usage — never returns email, keyID, or customerID."""
    try:
        usage = await _canonical_event_provider().get_usage()
    except Exception as exc:
        logger.warning("SGO account usage fetch failed: %s", exc)
        usage = {"available": False, "tier": None, "reason": type(exc).__name__}
    return wrap_data(usage, source="sportsgameodds_v2_account_usage")