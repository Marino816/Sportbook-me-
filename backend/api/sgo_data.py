"""SB ME SGO Data API — Rookie-tier compatible, extracts all data from /v2/events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data
from providers.event_parser import (
    ParsedEventMarkets,
    parse_event_odds,
    extract_bookmaker_odds_table,
    build_player_props_list,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sgo", tags=["SGO Data"])


async def _get_sgo():
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


# ── Routes ───────────────────────────────────────────────────

@router.get("/events")
async def get_events(
    league: str = Query(..., description="League ID (MLB, NFL, NBA, etc.)"),
    user: User = Depends(get_current_user),
):
    """Live/upcoming events with game context and parsed odds."""
    try:
        sgo = await _get_sgo()
        async with sgo:
            events = await sgo.get_events(league_id=league.upper())
    except Exception as e:
        logger.error(f"Failed to fetch events for league={league}: {e}")
        return wrap_data({"events": [], "league": league.upper(), "count": 0,
                          "status": "unavailable", "message": "SportsGameOdds data is currently unavailable."},
                         source="cached")

    if not events:
        return wrap_data({"events": [], "league": league.upper(), "count": 0,
                          "message": f"No events found for {league.upper()}"},
                         source="sportsgameodds")

    events_list = [_event_summary(e, include_odds=True) for e in events]
    return wrap_data({"events": events_list, "league": league.upper(), "count": len(events_list)},
                     source="sportsgameodds")


@router.get("/events/{event_id}/odds")
async def get_event_odds(event_id: str, user: User = Depends(get_current_user)):
    """Moneyline/spread/total per bookmaker, extracted from cached event."""
    try:
        events = await _get_raw_events("MLB")
    except Exception as e:
        logger.warning(f"Failed to fetch events for odds: {e}")
        return wrap_data({"event_id": event_id, "books": [], "status": "unavailable"},
                         source="cached")

    for e in events:
        eid = _val(e, "eventID", "") or _val(e, "id", "")
        if eid == event_id:
            raw_odds = _val(e, "odds")
            raw_players = _val(e, "players")
            if isinstance(raw_odds, dict):
                parsed = parse_event_odds(event_id, raw_odds,
                                          raw_players if isinstance(raw_players, dict) else None)
                table = extract_bookmaker_odds_table(parsed)
                books = [{"bookmaker": k, **v} for k, v in table.items()]
                return wrap_data({
                    "event_id": event_id,
                    "books": books,
                    "book_count": len(books),
                }, source="sportsgameodds")

    return wrap_data({"event_id": event_id, "books": [], "message": "Event not found"}, source="cached")


@router.get("/events/{event_id}/props")
async def get_event_props(event_id: str, user: User = Depends(get_current_user)):
    """Player props extracted from cached event.odds."""
    try:
        events = await _get_raw_events("MLB")
    except Exception as e:
        logger.warning(f"Failed to fetch events for props: {e}")
        return wrap_data({"event_id": event_id, "players": [], "prop_count": 0, "status": "unavailable"},
                         source="cached")

    for e in events:
        eid = _val(e, "eventID", "") or _val(e, "id", "")
        if eid == event_id:
            raw_odds = _val(e, "odds")
            raw_players = _val(e, "players")
            if isinstance(raw_odds, dict):
                parsed = parse_event_odds(event_id, raw_odds,
                                          raw_players if isinstance(raw_players, dict) else None)
                props = build_player_props_list(parsed,
                                                raw_players if isinstance(raw_players, dict) else {})
                return wrap_data({
                    "event_id": event_id,
                    "players": props,
                    "prop_count": len(props),
                }, source="sportsgameodds")

    return wrap_data({"event_id": event_id, "players": [], "prop_count": 0,
                       "message": "Event not found"}, source="cached")


@router.get("/bookmakers")
async def get_bookmakers(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    """Available bookmakers from live SGO events."""
    try:
        events = await _get_raw_events(league.upper())
    except Exception as e:
        logger.warning(f"Failed to fetch events for bookmaker scan: {e}")
        return wrap_data({"bookmakers": [], "count": 0, "status": "unavailable"}, source="cached")

    bookmakers: set[str] = set()
    for e in events[:8]:
        raw_odds = _val(e, "odds")
        if isinstance(raw_odds, dict):
            for odd_data in raw_odds.values():
                if not isinstance(odd_data, dict):
                    continue
                by_bm = odd_data.get("byBookmaker", {})
                if isinstance(by_bm, dict):
                    for bk_id, bk_data in by_bm.items():
                        if isinstance(bk_data, dict) and bk_data.get("available", False):
                            bookmakers.add(bk_id)

    sorted_bm = sorted(bookmakers)
    return wrap_data({"bookmakers": sorted_bm, "count": len(sorted_bm)}, source="sportsgameodds")


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
            teams = await sgo.get_teams(league=league.upper())
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
    return wrap_data({"teams": teams_list, "league": league.upper(), "count": len(teams_list)},
                     source="sportsgameodds")


@router.get("/players")
async def get_players(
    league: str = Query("MLB"),
    user: User = Depends(get_current_user),
):
    try:
        sgo = await _get_sgo()
        async with sgo:
            players = await sgo.get_players(league_id=league.upper())
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
                "league": league.upper(),
            })
        else:
            players_list.append({
                "player_id": getattr(p, "player_id", getattr(p, "id", "")),
                "name": getattr(p, "name", getattr(p, "player_name", "")),
                "team": getattr(p, "team", ""),
                "position": getattr(p, "position", ""),
                "league": league.upper(),
            })
    return wrap_data({"players": players_list, "count": len(players_list)}, source="sportsgameodds")


# Stub routes for endpoints that don't exist on Rookie tier
@router.get("/events/{event_id}/fair-odds")
async def get_fair_odds(event_id: str, user: User = Depends(get_current_user)):
    return wrap_data({
        "event_id": event_id, "status": "unavailable",
        "message": "Fair odds available within event.odds[oddID].fairOdds"
    }, source="sportsgameodds")


@router.get("/events/{event_id}/consensus")
async def get_consensus(event_id: str, user: User = Depends(get_current_user)):
    return wrap_data({
        "event_id": event_id, "status": "unavailable",
        "message": "Use /events/{id}/odds for per-bookmaker comparison"
    }, source="sportsgameodds")


@router.get("/usage")
async def get_usage(user: User = Depends(get_current_user)):
    return wrap_data({
        "message": "Rookie tier — see /v2/account/usage directly",
        "tier": "rookie"
    }, source="sportsgameodds")