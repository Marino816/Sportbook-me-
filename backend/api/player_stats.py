"""
Historical player game-log endpoint — Last-5 / Last-10 fantasy scoring.

Uses SGO finalized events with include=results to retrieve per-game
player performance statistics, then scores them through the historical
scoring service (NOT the projection approximation).
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from api.auth import get_current_user
from api.utils import wrap_data
from models.domain import User
from providers.integration import SGOIntegration
from providers.sportsgameodds import SportsGameOddsProvider
from scoring import build_game_log, ScoringPlatform

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["Player Stats"])

# How far back to look for completed games (days)
HISTORICAL_WINDOW_DAYS = 30
# Max events to fetch per query (one team plays ~daily)
MAX_HISTORICAL_EVENTS = 20


@router.get("/{player_id}/last-n")
async def get_player_game_log(
    player_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    n: int = Query(default=5, ge=1, le=20),
    platform: str = Query(default="draftkings"),
    sport: str = Query(default="MLB"),
):
    """Retrieve a player's last-N completed games with fantasy scores.

    *player_id* must be an SGO player ID (e.g. TRENT_GRISHAM_1_MLB).
    Scoring follows the official DraftKings MLB DFS rules using only
    directly available SGO fields.  Missing categories (runs scored,
    pitcher HBP) produce a historical_partial label, never a silent zero.

    FanDuel is disabled until its official 2026 rules are independently
    verified.
    """
    # ── Validate platform ──
    platform_lower = platform.lower()
    if platform_lower not in ("draftkings", "dk"):
        raise HTTPException(
            status_code=400,
            detail="FanDuel historical scoring is disabled until its current "
                   "official 2026 MLB DFS scoring rules are independently verified. "
                   "Use platform=draftkings.",
        )
    scoring_platform = ScoringPlatform.DRAFTKINGS

    # ── Compute date window ──
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=HISTORICAL_WINDOW_DAYS)

    extra = {
        "include": "results",
        "finalized": "true",
        "startsAfter": start.strftime("%Y-%m-%d"),
        "startsBefore": end.strftime("%Y-%m-%d"),
        "limit": str(MAX_HISTORICAL_EVENTS),
    }

    # ── Determine team from SGO player listing so we can filter ──
    try:
        async with SGOIntegration() as sgo:
            # Get player info to find teamID
            sgo_events_all = await sgo._provider.get_events(
                league_id=sport.upper(),
                extra_params=extra,
            )
    except Exception as e:
        logger.error(f"SGO fetch failed for player {player_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail="SportsGameOdds data unavailable — cannot retrieve "
                   "historical player statistics at this time.",
        )

    # ── Build game log ──
    game_log = await build_game_log(
        sgo_events_all,
        player_id,
        platform=scoring_platform,
        n=n,
    )

    if game_log is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player '{player_id}' not found in any completed games "
                   f"from the last {HISTORICAL_WINDOW_DAYS} days. "
                   f"Verify the SGO player ID and try a wider date range.",
        )

    # ── Serialize ──
    games_json = []
    for g in game_log.games:
        games_json.append({
            "date": g.date,
            "event_id": g.event_id,
            "opponent": g.opponent,
            "home_away": g.home_away,
            "fantasy_points": g.result.fantasy_points,
            "scoring_mode": g.result.scoring_mode.value,
            "is_exact": g.result.is_exact,
            "missing_fields": g.result.missing_fields,
            "calculated_from": g.result.calculated_from,
            "raw_stats": _serialize_raw(g.result.raw_stats),
        })

    return wrap_data({
        "player_id": game_log.player_id,
        "player_name": game_log.player_name,
        "platform": game_log.platform,
        "sport": game_log.sport,
        "player_role": game_log.player_role,
        "scoring_mode": game_log.scoring_mode,
        "n": game_log.n,
        "average_fp": game_log.average_fp,
        "min_fp": game_log.min_fp,
        "max_fp": game_log.max_fp,
        "average_is_exact": game_log.average_is_exact,
        "global_missing_fields": game_log.global_missing_fields,
        "games": games_json,
    }, source="sgo_historical")


def _serialize_raw(raw: dict) -> dict:
    """Convert raw_stats values to JSON-safe primitives."""
    out = {}
    for k, v in raw.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (int, float)):
            out[k] = v
        else:
            out[k] = str(v)
    return out