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
from projection.native import compute_projections, projections_to_pool, apply_projection_policy
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

    bc_meta = {}
    report = slate.reconciliation_report if isinstance(slate.reconciliation_report, dict) else {}
    raw_meta = report.get("bc_player_meta") if report else None
    if isinstance(raw_meta, dict):
        bc_meta = raw_meta

    projections_list = []
    for np in native_players:
        provider_id = np.provider_player_id or ""
        player_bc = bc_meta.get(provider_id) or bc_meta.get(str(provider_id)) or {}
        projections_list.append({
            "id": np.sbme_player_id or np.provider_player_id,
            "name": np.player_name,
            "team": np.team,
            "position": np.position,
            "salary": np.salary,
            "fppg": np.fppg,
            "eligible_positions": np.eligible_positions or [np.position],
            "projected_fp": 0.0,
            "opponent": np.opponent or "",
            "mapping_status": np.mapping_status,
            "bc_value": (player_bc.get("value") if isinstance(player_bc, dict) else None),
            "bc_beta_proj": (player_bc.get("beta_proj") if isinstance(player_bc, dict) else None),
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
        pool = apply_projection_policy(projections_to_pool(projs))
        from projection.native import count_projected_players
        projected_count = count_projected_players(pool)
        logger.info(f"Canonical pool: {projected_count}/{len(pool)} projected (slate date {slate_date})")
    except Exception as e:
        logger.warning(f"Projection engine unavailable in canonical pool: {e}")
        pool = apply_projection_policy(projections_to_pool(
            compute_projections(sport, projections_list, sgo_intelligence={})
        ))

    by_id = {str(p.get("id")): p for p in projections_list}
    for pl in pool:
        src = by_id.get(str(pl.get("id")))
        if src:
            if pl.get("bc_value") is None:
                pl["bc_value"] = src.get("bc_value")
            if pl.get("bc_beta_proj") is None:
                pl["bc_beta_proj"] = src.get("bc_beta_proj")

    # Unprojected players keep projected_fp = 0.0 — no fabricated 0.01 fallback.
    # The router-level >=10-projected gate is the sole projection-sufficiency check.
    # Players with projected_fp <= 0 are filtered out by CP-SAT _build_maps();
    # this is correct: only legitimately projected players are optimizer-eligible.
    # If the solver cannot construct valid rosters from the real-projection pool,
    # it returns empty — an honest signal, not a fabricated-workaround signal.

    # Value = SB projection / (salary / 1000). Distinct from Blue Collar "value".
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
        "projection_source": "SGO_FANTASY_MARKET | PROP_BASED | BC_PROJ_FALLBACK | UNAVAILABLE",
        "ownership": ownership_meta,
    }

    return pool, metadata
