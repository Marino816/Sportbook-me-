"""
SB ME SGO Data API — public SGO data routes for the website.

Endpoints:
  GET /api/sgo/sports                    → available sports
  GET /api/sgo/events?league=MLB         → live/upcoming events
  GET /api/sgo/events/{event_id}          → single event detail + scores
  GET /api/sgo/events/{event_id}/odds     → moneyline/spread/total per book
  GET /api/sgo/events/{event_id}/props    → player props
  GET /api/sgo/events/{event_id}/fair-odds → fair/implied odds
  GET /api/sgo/events/{event_id}/consensus → book consensus
  GET /api/sgo/teams?league=MLB           → teams list
  GET /api/sgo/players?league=MLB&team=LAD → players
  GET /api/sgo/players/{player_id}/stats   → player stats
  GET /api/sgo/teams/{team_id}/stats      → team stats
  GET /api/sgo/bookmakers                 → available bookmakers
  GET /api/sgo/usage                      → SGO API usage stats

All routes require authentication (get_current_user).
All responses use wrap_data() format.
All SGO calls go through SGOIntegration + cache — never expose raw API keys.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sgo", tags=["SGO Data"])


# ══════════════════════════════════════════════════════════════
#  Helper: get SGO integration instance
# ══════════════════════════════════════════════════════════════


async def _get_sgo():
    """Create a cached SGO integration instance."""
    from providers.integration import SGOIntegration
    return SGOIntegration()


def _val(obj, attr, default=None):
    """Safely access attribute or dict key."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _event_to_dict(event) -> dict:
    """Convert a NormalizedEvent (or dict from cache) to API response format."""
    home_team_name = _val(event, "home_team", "") or ""
    away_team_name = _val(event, "away_team", "") or ""

    # Build team objects with name + abbreviation
    home_abbr = ""
    away_abbr = ""

    # Try to extract abbreviation from raw event's nested teams data
    raw_teams = _val(event, "_raw_teams", None)
    if raw_teams:
        home_obj = raw_teams.get("home") or raw_teams.get("homeTeam") or {}
        away_obj = raw_teams.get("away") or raw_teams.get("awayTeam") or {}
        if isinstance(home_obj, dict):
            home_abbr = home_obj.get("abbreviation", "") or home_obj.get("abbr", "") or ""
        if isinstance(away_obj, dict):
            away_abbr = away_obj.get("abbreviation", "") or away_obj.get("abbr", "") or ""

    # Derive abbreviation from team name if not available
    if not home_abbr and home_team_name:
        home_abbr = _derive_abbr(home_team_name)
    if not away_abbr and away_team_name:
        away_abbr = _derive_abbr(away_team_name)

    start_time = _val(event, "start_time", None)
    if start_time and hasattr(start_time, "isoformat"):
        start_time = start_time.isoformat()
    elif start_time and isinstance(start_time, dict):
        start_time = start_time.get("isoformat", start_time.get("$date", str(start_time)))
    elif start_time:
        start_time = str(start_time) if not isinstance(start_time, str) else start_time

    return {
        "event_id": getattr(event, "id", ""),
        "sport": getattr(event, "sport", ""),
        "league": getattr(event, "league", ""),
        "home_team": {
            "name": home_team_name,
            "abbreviation": home_abbr,
        },
        "away_team": {
            "name": away_team_name,
            "abbreviation": away_abbr,
        },
        "start_time": start_time,
        "status": _safe_str(getattr(event, "status", "SCHEDULED"), "SCHEDULED"),
        "home_score": getattr(event, "home_score", None),
        "away_score": getattr(event, "away_score", None),
        "period": _extract_period(event),
    }


def _derive_abbr(name: str) -> str:
    """Derive a 3-letter abbreviation from a team name."""
    if not name:
        return ""
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0][:3].upper()
    if len(parts) >= 3:
        # City + mascot → first letter of city + first 2 of mascot
        return (parts[0][0] + parts[-1][:2]).upper()
    return (parts[0][0] + parts[-1][:2]).upper()


def _safe_str(val, default=""):
    """Ensure a value is a string, extracting from dict if needed."""
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return str(val.get("name", val.get("state", val.get("display", str(val)))))
    return str(val)


def _extract_period(event) -> Optional[str]:
    """Extract period information (inning/quarter/period) from event context."""
    # Try raw event period fields
    raw = getattr(event, "_raw", None)
    if isinstance(raw, dict):
        for key in ("period", "currentPeriod", "inning", "quarter", "half"):
            val = raw.get(key)
            if val:
                if isinstance(val, (int, float)):
                    num = int(val)
                    sport_val = _safe_str(getattr(event, "sport", ""))
                    return _period_label(sport_val, num)
                return str(val)

    # Try direct period attribute
    period = getattr(event, "period", None)
    if period and not isinstance(period, dict):
        return str(period)

    # If LIVE, try to infer from scores
    status_val = getattr(event, "status", "")
    status_str = _safe_str(status_val)
    if status_str.upper() == "LIVE" or (isinstance(status_val, dict) and status_val.get("state") == "live"):
        return "Live"
    return None


def _period_label(sport: str, period_num: int) -> str:
    """Convert numeric period to sport-appropriate label."""
    sport_upper = (sport or "").upper()
    if sport_upper in ("MLB",):
        suffixes = {1: "1st", 2: "2nd", 3: "3rd"}
        return f"{suffixes.get(period_num, f'{period_num}th')} Inning"
    if sport_upper in ("NFL", "NCAAF"):
        return f"Q{period_num}" if period_num <= 4 else f"OT{period_num - 4}"
    if sport_upper in ("NBA", "NCAAB"):
        return f"Q{period_num}" if period_num <= 4 else f"OT{period_num - 4}"
    if sport_upper in ("NHL",):
        return f"P{period_num}" if period_num <= 3 else f"OT{period_num - 3}"
    return f"Period {period_num}"


def _team_to_dict(team) -> dict:
    """Convert a NormalizedTeam to API response dict."""
    return {
        "team_id": getattr(team, "id", ""),
        "name": getattr(team, "name", ""),
        "abbreviation": getattr(team, "abbreviation", ""),
        "league": getattr(team, "league", ""),
        "sport": getattr(team, "sport", ""),
    }


def _player_to_dict(player) -> dict:
    """Convert a NormalizedPlayer to API response dict."""
    return {
        "player_id": getattr(player, "id", ""),
        "name": getattr(player, "name", ""),
        "team": getattr(player, "team", ""),
        "position": getattr(player, "position", ""),
        "league": getattr(player, "league", ""),
        "sport": getattr(player, "sport", ""),
    }


def _sport_to_dict(sport_raw: dict) -> dict:
    """Normalize a raw sport entry from SGO."""
    return {
        "sport_id": sport_raw.get("sportID") or sport_raw.get("id") or sport_raw.get("sport_id", ""),
        "name": sport_raw.get("name", ""),
        "display_name": sport_raw.get("displayName", sport_raw.get("display_name", "")),
        "leagues": sport_raw.get("leagues", []),
    }


# ══════════════════════════════════════════════════════════════
#  1. Sports
# ══════════════════════════════════════════════════════════════


@router.get("/sports")
async def get_sports(
    user: User = Depends(get_current_user),
):
    """
    List available sports from SportsGameOdds.

    Returns a list of sport objects with IDs, names, and available leagues.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            sports = await sgo.get_sports()
    except Exception as e:
        logger.error(f"Failed to fetch sports: {e}")
        return wrap_data({
            "sports": [],
            "count": 0,
            "status": "unavailable",
            "message": "SportsGameOdds data is currently unavailable.",
        }, source="cached")

    sports_list = [_sport_to_dict(s) for s in (sports or [])]
    return wrap_data({
        "sports": sports_list,
        "count": len(sports_list),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  2. Events
# ══════════════════════════════════════════════════════════════


@router.get("/events")
async def get_events(
    league: str = Query(..., description="League ID (MLB, NFL, NBA, NHL, etc.)"),
    user: User = Depends(get_current_user),
):
    """
    List live and upcoming events for a league.

    Each event includes game context: teams, start time, status, scores, period.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            events = await sgo.get_events(league_id=league.upper())
    except Exception as e:
        logger.error(f"Failed to fetch events for league={league}: {e}")
        return wrap_data({
            "events": [],
            "league": league.upper(),
            "count": 0,
            "status": "unavailable",
            "message": "SportsGameOdds data is currently unavailable.",
        }, source="cached")

    if not events:
        return wrap_data({
            "events": [],
            "league": league.upper(),
            "count": 0,
            "message": f"No events found for {league.upper()}",
        }, source="sportsgameodds")

    events_list = [_event_to_dict(e) for e in events]
    return wrap_data({
        "events": events_list,
        "league": league.upper(),
        "count": len(events_list),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  3. Single Event Detail
# ══════════════════════════════════════════════════════════════


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get full detail for a single event, including scores.

    Returns: event context, scores, and period information.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            # Fetch event detail (raw) + scores
            from providers.sportsgameodds import SportsGameOddsProvider
            # Use the provider directly for raw event detail
            async with SportsGameOddsProvider() as provider:
                raw_event = await provider.get_event(event_id)

            # Get scores
            scores = await sgo.get_scores(event_id)

            # Get events for this league to find the normalized event
            if raw_event:
                from providers.normalizer import SportsGameOddsNormalizer
                event = SportsGameOddsNormalizer.normalize_event(raw_event)
            else:
                raise ValueError("Event not found")
    except Exception as e:
        logger.warning(f"Failed to fetch event detail for {event_id}: {e}")
        return wrap_data({
            "event_id": event_id,
            "status": "unavailable",
            "message": "Could not fetch event detail at this time.",
        }, source="cached")

    result = _event_to_dict(event)

    # Merge scores
    if scores and isinstance(scores, dict):
        result["home_score"] = scores.get("homeScore") or scores.get("home_score") or result.get("home_score")
        result["away_score"] = scores.get("awayScore") or scores.get("away_score") or result.get("away_score")
        result["period"] = (
            scores.get("period")
            or scores.get("currentPeriod")
            or scores.get("inning")
            or result.get("period")
        )

    result["scores_raw"] = scores

    return wrap_data(result, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  4. Event Odds
# ══════════════════════════════════════════════════════════════


@router.get("/events/{event_id}/odds")
async def get_event_odds(
    event_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get moneyline, spread, and total odds for an event, per bookmaker.

    Books are sorted by bookmaker_rank (DraftKings, FanDuel, BetMGM first).
    Includes consensus lines where available.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            odds = await sgo.get_odds(event_id)
    except Exception as e:
        logger.warning(f"Failed to fetch odds for {event_id}: {e}")
        return wrap_data({
            "event_id": event_id,
            "books": [],
            "status": "unavailable",
            "message": "Could not fetch odds at this time.",
        }, source="cached")

    if not odds:
        return wrap_data({
            "event_id": event_id,
            "books": [],
            "book_count": 0,
            "message": "No odds available for this event.",
        }, source="sportsgameodds")

    # Sort books by bookmaker rank
    from market_engine import bookmaker_rank
    sorted_books = sorted(odds.books, key=lambda b: bookmaker_rank(b.bookmaker))

    books_list = []
    for b in sorted_books:
        books_list.append({
            "bookmaker": b.bookmaker,
            "moneyline_home": b.moneyline_home,
            "moneyline_away": b.moneyline_away,
            "spread_home": b.spread_home,
            "spread_away": b.spread_away,
            "total_over": b.total_over,
            "total_under": b.total_under,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        })

    result = {
        "event_id": event_id,
        "books": books_list,
        "book_count": len(books_list),
    }

    # Add consensus if available
    if odds.consensus:
        result["consensus"] = {
            "bookmaker": odds.consensus.bookmaker,
            "moneyline_home": odds.consensus.moneyline_home,
            "moneyline_away": odds.consensus.moneyline_away,
            "spread_home": odds.consensus.spread_home,
            "spread_away": odds.consensus.spread_away,
            "total_over": odds.consensus.total_over,
            "total_under": odds.consensus.total_under,
        }

    # Add fair odds if available
    if odds.fair_moneyline_home is not None or odds.fair_total is not None:
        result["fair_odds"] = {
            "moneyline_home": odds.fair_moneyline_home,
            "moneyline_away": odds.fair_moneyline_away,
            "total": odds.fair_total,
        }

    return wrap_data(result, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  5. Player Props
# ══════════════════════════════════════════════════════════════


@router.get("/events/{event_id}/props")
async def get_event_props(
    event_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get player props for an event, grouped by player with named markets.

    Each prop shows the line, over price, under price, and bookmaker.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            props = await sgo.get_player_props(event_id)
    except Exception as e:
        logger.warning(f"Failed to fetch props for {event_id}: {e}")
        return wrap_data({
            "event_id": event_id,
            "players": {},
            "prop_count": 0,
            "status": "unavailable",
            "message": "Could not fetch player props at this time.",
        }, source="cached")

    if not props:
        return wrap_data({
            "event_id": event_id,
            "players": {},
            "prop_count": 0,
            "message": "No player props available for this event.",
        }, source="sportsgameodds")

    # Group by player_id
    players: dict[str, dict] = {}
    for prop in props:
        pid = getattr(prop, "player_id", "")
        if not pid:
            pid = "unknown"
        if pid not in players:
            players[pid] = {
                "player_id": pid,
                "markets": {},
            }
        market = getattr(prop, "market", "") or "unknown"
        if market not in players[pid]["markets"]:
            players[pid]["markets"][market] = {
                "market": market,
                "lines": [],
            }
        players[pid]["markets"][market]["lines"].append({
            "bookmaker": getattr(prop, "bookmaker", ""),
            "line": getattr(prop, "line", None),
            "over_price": getattr(prop, "over_price", None),
            "under_price": getattr(prop, "under_price", None),
        })

    # Convert to sorted list
    player_list = []
    for pid, data in players.items():
        # Sort market lines by bookmaker rank
        from market_engine import bookmaker_rank
        market_list = []
        for market_name, market_data in data["markets"].items():
            market_data["lines"] = sorted(
                market_data["lines"],
                key=lambda l: bookmaker_rank(l["bookmaker"]),
            )
            market_list.append(market_data)
        data["markets"] = sorted(market_list, key=lambda m: m["market"])
        player_list.append(data)

    player_list.sort(key=lambda p: p["player_id"])

    return wrap_data({
        "event_id": event_id,
        "players": player_list,
        "player_count": len(player_list),
        "prop_count": len(props),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  6. Fair Odds
# ══════════════════════════════════════════════════════════════


@router.get("/events/{event_id}/fair-odds")
async def get_fair_odds(
    event_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get fair/implied odds for an event (vig-free probability estimates).

    Returns moneyline, spread, and total fair values where available.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            fair_odds = await sgo.get_fair_odds(event_id)
    except Exception as e:
        logger.warning(f"Failed to fetch fair odds for {event_id}: {e}")
        return wrap_data({
            "event_id": event_id,
            "status": "unavailable",
            "message": "Could not fetch fair odds at this time.",
        }, source="cached")

    if not fair_odds:
        return wrap_data({
            "event_id": event_id,
            "message": "No fair odds available for this event.",
        }, source="sportsgameodds")

    return wrap_data({
        "event_id": event_id,
        "fair_odds": fair_odds,
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  7. Consensus
# ══════════════════════════════════════════════════════════════


@router.get("/events/{event_id}/consensus")
async def get_consensus(
    event_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get book consensus lines — the aggregated market line across all
    bookmakers for moneyline, spread, and total markets.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            consensus = await sgo.get_consensus(event_id)
    except Exception as e:
        logger.warning(f"Failed to fetch consensus for {event_id}: {e}")
        return wrap_data({
            "event_id": event_id,
            "status": "unavailable",
            "message": "Could not fetch consensus at this time.",
        }, source="cached")

    if not consensus:
        return wrap_data({
            "event_id": event_id,
            "message": "No consensus data available for this event.",
        }, source="sportsgameodds")

    return wrap_data({
        "event_id": event_id,
        "consensus": consensus,
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  8. Teams
# ══════════════════════════════════════════════════════════════


@router.get("/teams")
async def get_teams(
    league: str = Query("MLB", description="League ID (MLB, NFL, NBA, NHL, etc.)"),
    user: User = Depends(get_current_user),
):
    """
    List teams for a league.

    Returns team objects with IDs, names, abbreviations, league, and sport.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            teams = await sgo.get_teams(league=league.upper())
    except Exception as e:
        logger.error(f"Failed to fetch teams for league={league}: {e}")
        return wrap_data({
            "teams": [],
            "league": league.upper(),
            "count": 0,
            "status": "unavailable",
            "message": "SportsGameOdds data is currently unavailable.",
        }, source="cached")

    if not teams:
        return wrap_data({
            "teams": [],
            "league": league.upper(),
            "count": 0,
            "message": f"No teams found for {league.upper()}",
        }, source="sportsgameodds")

    teams_list = [_team_to_dict(t) for t in teams]
    return wrap_data({
        "teams": teams_list,
        "league": league.upper(),
        "count": len(teams_list),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  9. Players
# ══════════════════════════════════════════════════════════════


@router.get("/players")
async def get_players(
    league: str = Query("MLB", description="League ID (MLB, NFL, NBA, NHL, etc.)"),
    team: str = Query("", description="Team ID or abbreviation to filter by"),
    user: User = Depends(get_current_user),
):
    """
    List players for a league, optionally filtered by team.

    Returns player objects with IDs, names, teams, positions, league, and sport.
    """
    team_filter = team.strip() if team else None
    try:
        sgo = await _get_sgo()
        async with sgo:
            players = await sgo.get_players(league_id=league.upper(), team=team_filter)
    except Exception as e:
        logger.error(f"Failed to fetch players for league={league}, team={team}: {e}")
        return wrap_data({
            "players": [],
            "league": league.upper(),
            "team": team,
            "count": 0,
            "status": "unavailable",
            "message": "SportsGameOdds data is currently unavailable.",
        }, source="cached")

    if not players:
        return wrap_data({
            "players": [],
            "league": league.upper(),
            "team": team,
            "count": 0,
            "message": f"No players found for {league.upper()}" + (f", team={team}" if team else ""),
        }, source="sportsgameodds")

    players_list = [_player_to_dict(p) for p in players]
    return wrap_data({
        "players": players_list,
        "league": league.upper(),
        "team": team,
        "count": len(players_list),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  10. Player Stats
# ══════════════════════════════════════════════════════════════


@router.get("/players/{player_id}/stats")
async def get_player_stats(
    player_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get player statistics from SportsGameOdds.

    Returns stats for the current season (or latest available).
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            stats = await sgo.get_player_stats(player_id)
    except Exception as e:
        logger.warning(f"Failed to fetch stats for player {player_id}: {e}")
        return wrap_data({
            "player_id": player_id,
            "status": "unavailable",
            "message": "Could not fetch player stats at this time.",
        }, source="cached")

    if not stats:
        return wrap_data({
            "player_id": player_id,
            "message": "No stats available for this player.",
        }, source="sportsgameodds")

    return wrap_data({
        "player_id": player_id,
        "stats": stats,
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  11. Team Stats
# ══════════════════════════════════════════════════════════════


@router.get("/teams/{team_id}/stats")
async def get_team_stats(
    team_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get team statistics from SportsGameOdds.

    Returns stats for the current season (or latest available).
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            stats = await sgo.get_team_stats(team_id)
    except Exception as e:
        logger.warning(f"Failed to fetch stats for team {team_id}: {e}")
        return wrap_data({
            "team_id": team_id,
            "status": "unavailable",
            "message": "Could not fetch team stats at this time.",
        }, source="cached")

    if not stats:
        return wrap_data({
            "team_id": team_id,
            "message": "No stats available for this team.",
        }, source="sportsgameodds")

    return wrap_data({
        "team_id": team_id,
        "stats": stats,
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  12. Bookmakers
# ══════════════════════════════════════════════════════════════


@router.get("/bookmakers")
async def get_bookmakers(
    league: str = Query("MLB", description="League to scan for active bookmakers"),
    user: User = Depends(get_current_user),
):
    """
    List available bookmakers from active events.

    Scans active events for a league and extracts all unique bookmakers
    found across event odds. Results are deduplicated and sorted by priority.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            events = await sgo.get_events(league_id=league.upper())
    except Exception as e:
        logger.error(f"Failed to fetch events for bookmaker scan: {e}")
        return wrap_data({
            "bookmakers": [],
            "league": league.upper(),
            "count": 0,
            "status": "unavailable",
            "message": "SportsGameOdds data is currently unavailable.",
        }, source="cached")

    if not events:
        return wrap_data({
            "bookmakers": [],
            "league": league.upper(),
            "count": 0,
            "message": f"No active events for {league.upper()} — cannot list bookmakers.",
        }, source="sportsgameodds")

    # Collect unique bookmakers from the first few events
    from market_engine import bookmaker_rank, normalize_bookmaker, BOOKMAKER_PRIORITY

    bookmakers_set: set[str] = set()
    events_to_check = events[:8]  # Check up to 8 events

    sgo2 = await _get_sgo()
    async with sgo2:
        for event in events_to_check:
            eid = getattr(event, "id", "")
            if not eid:
                continue
            try:
                odds = await sgo2.get_odds(eid)
                if odds and odds.books:
                    for b in odds.books:
                        name = b.bookmaker or ""
                        if name:
                            bookmakers_set.add(normalize_bookmaker(name))
            except Exception:
                continue

    # Sort by priority
    bookmakers_list = sorted(bookmakers_set, key=lambda b: bookmaker_rank(b))

    return wrap_data({
        "bookmakers": bookmakers_list,
        "league": league.upper(),
        "count": len(bookmakers_list),
        "events_scanned": len(events_to_check),
    }, source="sportsgameodds")


# ══════════════════════════════════════════════════════════════
#  13. Usage Stats
# ══════════════════════════════════════════════════════════════


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
):
    """
    Get SportsGameOdds API usage statistics.

    Returns objects consumed, remaining quota, and rate-limit status
    as reported by the SGO API.
    """
    try:
        sgo = await _get_sgo()
        async with sgo:
            usage = await sgo.get_usage()
    except Exception as e:
        logger.warning(f"Failed to fetch SGO usage stats: {e}")
        return wrap_data({
            "provider": "SportsGameOdds",
            "status": "unavailable",
            "message": "Could not fetch usage stats at this time.",
        }, source="cached")

    if not usage:
        return wrap_data({
            "provider": "SportsGameOdds",
            "status": "unavailable",
            "message": "Usage stats not available from provider.",
        }, source="sportsgameodds")

    return wrap_data({
        "provider": "SportsGameOdds",
        "usage": usage,
    }, source="sportsgameodds")