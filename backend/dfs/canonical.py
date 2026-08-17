"""
Canonical SB DFS Slate / Player Model.

The single source of truth for the authenticated analytics product. Combines:

    DFS contest salary/roster data (authoritative for construction)
  + SportsGameOdds market/prop intelligence (authoritative for market data)
  + SB ME projection engine (modeled projections)

into a unified "Canonical SB DFS Player" consumed by the Data Hub, Optimizer,
Sims, and Top Stacks. Pages must NOT independently reconstruct player
identity, team, opponent, position, or salary — they read from this model.

Ceiling/floor are modeled as symmetric sport-appropriate variance around the
SB projection (MLB: hitters ±~35%, pitchers ±~25%). These are MODELED values,
not provider data.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.domain import User  # noqa: F401 (type ref)
from dfs.db import DFSSlate, DFSPlayer
from projection.native import compute_projections, projections_to_pool
from projection.sgo_intelligence import build_sgo_intelligence
from dfs.ownership import compute_ownership_and_leverage

logger = logging.getLogger(__name__)

CANONICAL_MODEL_VERSION = "canonical-dfs-v1"

# Sport-appropriate ceiling/floor variance factors (model assumption).
CEILING_FACTOR = {"MLB": 1.35, "NFL": 1.4, "NBA": 1.3, "NHL": 1.35}
FLOOR_FACTOR = {"MLB": 0.65, "NFL": 0.6, "NBA": 0.7, "NHL": 0.65}


def _apply_ceiling_floor(pool: list[dict], sport: str) -> None:
    """Attach modeled ceiling/floor to each player."""
    cf = CEILING_FACTOR.get(sport, 1.3)
    ff = FLOOR_FACTOR.get(sport, 0.7)
    for p in pool:
        fp = float(p.get("projected_fp") or 0)
        if fp > 0:
            p["ceiling"] = round(fp * cf, 1)
            p["floor"] = round(fp * ff, 1)
        else:
            p["ceiling"] = None
            p["floor"] = None


async def build_canonical_pool(
    db: AsyncSession,
    slate_id: int,
    platform: str = "draftkings",
    with_ownership: bool = True,
) -> tuple[list[dict], dict]:
    """
    Build the canonical SB DFS player pool for a published slate.

    Returns (pool, metadata). Each pool dict carries:
      id, name, position, roster_position, salary, team, opponent,
      eligible_positions, projected_fp, projection_source,
      projection_confidence, value, sbme_ownership_pct, leverage,
      ceiling, floor, mapping_status
    """
    slate_result = await db.execute(
        select(DFSSlate).where(DFSSlate.id == slate_id, DFSSlate.status == "PUBLISHED")
    )
    slate = slate_result.scalars().first()
    if not slate:
        return [], {"error": f"Slate {slate_id} not found or not published"}

    sport = slate.sport.upper()
    platform = (platform or slate.platform).lower()

    players_result = await db.execute(select(DFSPlayer).where(DFSPlayer.slate_id == slate.id))
    native_players = players_result.scalars().all()

    projections_list = []
    for np in native_players:
        projections_list.append({
            "id": np.sbme_player_id or np.provider_player_id,
            "name": np.player_name,
            "team": np.team,
            "position": np.position,
            "salary": np.salary,
            "eligible_positions": np.eligible_positions or [np.position],
            "projected_fp": 0.0,
            "opponent": np.opponent or "",
            "mapping_status": np.mapping_status,
        })

    if len(projections_list) < 10:
        return [], {"error": "Slate has insufficient players", "player_count": len(projections_list)}

    # Real projections from SGO intelligence (DATE-SAFE: restrict SGO events
    # to the slate's own game date so a stale salary slate is never enriched
    # with current/upcoming SGO market data).
    slate_date = slate.start_time.date().isoformat() if slate.start_time else None
    try:
        sgo_intel = await build_sgo_intelligence(sport, projections_list, event_date=slate_date)
        projs = compute_projections(sport, projections_list, sgo_intelligence=sgo_intel)
        projected_count = sum(1 for p in projs if p.projection_source != "UNAVAILABLE")
        pool = projections_to_pool(projs)
        logger.info(f"Canonical pool: {projected_count}/{len(pool)} projected (slate date {slate_date})")
    except Exception as e:
        logger.warning(f"Projection engine unavailable in canonical pool: {e}")
        pool = projections_to_pool(
            compute_projections(sport, projections_list, sgo_intelligence={})
        )

    # 0.01 fallback for unprojected players so rosters still fill
    for pl in pool:
        if (pl.get("projected_fp") or 0) <= 0:
            pl["projected_fp"] = 0.01
            pl["projection_source"] = pl.get("projection_source") or "UNAVAILABLE"

    # Value = projection / (salary / 1000)
    for pl in pool:
        sal = float(pl.get("salary") or 0)
        fp = float(pl.get("projected_fp") or 0)
        pl["value"] = round((fp / (sal / 1000.0)), 2) if sal > 0 else 0.0

    # Ownership + leverage
    if with_ownership:
        pool, ownership_meta = compute_ownership_and_leverage(pool, platform=platform, sport=sport)
    else:
        ownership_meta = {"model": "disabled"}

    # Ceiling / floor
    _apply_ceiling_floor(pool, sport)

    metadata = {
        "model": CANONICAL_MODEL_VERSION,
        "slate_id": slate.id,
        "platform": platform,
        "sport": sport,
        "slate_name": slate.slate_name,
        "start_time": slate.start_time.isoformat() if slate.start_time else None,
        "player_count": len(pool),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projection_source": "SGO_FANTASY_MARKET | PROP_BASED | UNAVAILABLE",
        "ownership": ownership_meta,
    }

    return pool, metadata
