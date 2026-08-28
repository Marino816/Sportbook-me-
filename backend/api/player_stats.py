"""
Historical player game-log endpoint — Last-5 / Last-10 fantasy scoring.

Uses SGO finalized events with include=results to retrieve per-game
player performance statistics, then scores them through the historical
scoring service (NOT the projection approximation).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from api.auth import get_current_user
from api.utils import wrap_data
from models.domain import User
from scoring import build_game_log, ScoringPlatform

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["Player Stats"])

HISTORICAL_WINDOW_DAYS = 30
MAX_HISTORICAL_EVENTS = 20


async def resolve_sgo_player_id(
    db: AsyncSession,
    player_id: str,
    *,
    sport: str = "MLB",
    name: str = "",
    team: str = "",
    slate_id: Optional[int] = None,
) -> tuple[Optional[str], str]:
    """Resolve a customer-supplied id/name to a confirmed SGO playerID.

    Precedence:
      1. Supplied id is a confirmed SGO playerID (sport-suffix shape)
      2. DFS row lookup → sbme_player_id only if that field is a confirmed SGO id
      3. Exact folded name + equivalent-team match against cached nested events
      4. available:false

    provider_player_id (DK/FD/Blue Collar site id) is never sent to SGO.
    Exact identity only — no fuzzy name mapping.
    """
    from dfs.db import DFSPlayer
    from providers.nested_events import (
        looks_like_sgo_player_id,
        load_cached_events,
        resolve_sgo_id_from_events,
    )

    raw = (player_id or "").strip()
    events = load_cached_events(sport)

    if looks_like_sgo_player_id(raw):
        return raw, ""

    if raw:
        q = select(DFSPlayer).where(
            or_(DFSPlayer.sbme_player_id == raw, DFSPlayer.provider_player_id == raw)
        )
        if slate_id:
            q = q.where(DFSPlayer.slate_id == slate_id)
        row = (await db.execute(q)).scalars().first()
        if row is not None:
            sbme = str(row.sbme_player_id or "").strip()
            if looks_like_sgo_player_id(sbme):
                return sbme, ""
            name = name or (row.player_name or "")
            team = team or (row.team or "")

    # Name+team only — do not pass DFS/provider IDs into SGO identity matching.
    resolved = resolve_sgo_id_from_events(events, player_id="", name=name, team=team)
    if resolved:
        return resolved, ""
    return None, (
        "No reconciled SportsGameOdds player ID for this player. "
        "Last-N history is unavailable until the DFS player is matched."
    )


@router.get("/{player_id}/last-n")
async def get_player_game_log(
    player_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    n: int = Query(default=5, ge=1, le=20),
    platform: str = Query(default="draftkings"),
    sport: str = Query(default="MLB"),
    name: str = Query(default=""),
    team: str = Query(default=""),
    slate_id: Optional[int] = Query(default=None),
):
    """Retrieve a player's last-N completed games with fantasy scores.

    Accepts a confirmed SGO player ID, a reconciled sbme_player_id that
    stores the SGO identity, or a DFS/provider id used only as a lookup key
    for name+team reconciliation. DK/FD/Blue Collar site IDs are never sent
    to SportsGameOdds. Unmatched players return available=false (not an error).

    Scoring follows official DraftKings MLB DFS rules using finalized SGO
    results (include=results). FanDuel historical scoring is disabled.
    """
    platform_lower = platform.lower()
    if platform_lower not in ("draftkings", "dk"):
        raise HTTPException(
            status_code=400,
            detail="FanDuel historical scoring is disabled until its current "
                   "official 2026 MLB DFS scoring rules are independently verified. "
                   "Use platform=draftkings.",
        )
    scoring_platform = ScoringPlatform.DRAFTKINGS

    payload = await compute_last_n(
        db,
        player_id,
        n=n,
        platform=platform_lower,
        sport=sport.upper(),
        name=name,
        team=team,
        slate_id=slate_id,
        scoring_platform=scoring_platform,
    )
    return wrap_data(payload, source="sgo_historical")


async def compute_last_n(
    db: AsyncSession,
    player_id: str,
    *,
    n: int = 5,
    platform: str = "draftkings",
    sport: str = "MLB",
    name: str = "",
    team: str = "",
    slate_id: Optional[int] = None,
    scoring_platform: ScoringPlatform = ScoringPlatform.DRAFTKINGS,
) -> dict:
    """Shared Last-N payload used by the customer route and SB ME AI tools."""
    sgo_id, reason = await resolve_sgo_player_id(
        db, player_id, sport=sport.upper(), name=name, team=team, slate_id=slate_id,
    )
    if not sgo_id:
        return {
            "available": False,
            "reason": reason,
            "player_id": player_id,
            "games": [],
        }

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=HISTORICAL_WINDOW_DAYS)

    extra = {
        "include": "results",
        "finalized": "true",
        "startsAfter": start.strftime("%Y-%m-%d"),
        "startsBefore": end.strftime("%Y-%m-%d"),
        "limit": str(MAX_HISTORICAL_EVENTS),
        "oddsAvailable": "false",
    }

    try:
        from providers.sportsgameodds import SportsGameOddsProvider
        async with SportsGameOddsProvider() as provider:
            sgo_events_all = await provider.get_events(
                league_id=sport.upper(),
                extra_params=extra,
            )
    except Exception as e:
        logger.error("SGO historical fetch failed for player %s: %s", sgo_id, e)
        return {
            "available": False,
            "reason": "SportsGameOdds historical results are unavailable right now.",
            "player_id": sgo_id,
            "games": [],
        }

    finalized = []
    for ev in sgo_events_all or []:
        if not isinstance(ev, dict):
            continue
        status = ev.get("status") if isinstance(ev.get("status"), dict) else {}
        if status.get("finalized") is False:
            continue
        if not (ev.get("results") or {}).get("game"):
            continue
        finalized.append(ev)

    game_log = await build_game_log(
        finalized,
        sgo_id,
        platform=scoring_platform,
        n=n,
    )

    if game_log is None:
        return {
            "available": False,
            "reason": (
                f"No completed games with box-score results were found for this "
                f"player in the last {HISTORICAL_WINDOW_DAYS} days."
            ),
            "player_id": sgo_id,
            "games": [],
        }

    games_json = []
    for g in game_log.games:
        games_json.append({
            "date": g.date,
            "event_id": g.event_id,
            "opponent": g.opponent,
            "home_away": g.home_away,
            "result": g.home_away,
            "fantasy_points": g.result.fantasy_points,
            "scoring_mode": g.result.scoring_mode.value,
            "is_exact": g.result.is_exact,
            "missing_fields": g.result.missing_fields,
            "calculated_from": g.result.calculated_from,
            "raw_stats": _serialize_raw(g.result.raw_stats),
            "stats": _serialize_raw(g.result.raw_stats),
        })

    return {
        "available": True,
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
    }


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
