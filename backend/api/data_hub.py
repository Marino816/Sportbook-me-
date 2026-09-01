"""SB ME Data Hub + Sims + Top Stacks customer API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data
from dfs.canonical import build_canonical_pool
from dfs.simulation import simulate_pool, simulate_lineups, SAFE_SIM_LIMIT
from dfs.stacks import build_top_stacks

router = APIRouter(tags=["SB-Me Data Hub"])


@router.get("/data-hub/slate")
async def data_hub_slate(
    slate_id: int,
    platform: str = "draftkings",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canonical SB DFS player pool for a published slate (Data Hub / Optimizer)."""
    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    if not pool:
        return wrap_data({"players": [], "metadata": metadata}, source="native")
    return wrap_data({"players": pool, "metadata": metadata}, source="native")


@router.get("/data-hub/ownership")
async def data_hub_ownership(
    slate_id: int,
    platform: str = "draftkings",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SB ME Projected Ownership + Leverage for a slate."""
    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    players = [
        {
            "id": p.get("id"),
            "name": p.get("name", ""),
            "position": p.get("roster_position") or p.get("position", ""),
            "team": p.get("team", ""),
            "salary": p.get("salary", 0),
            "projected_fp": p.get("projected_fp", 0),
            "sbme_ownership_pct": p.get("sbme_ownership_pct"),
            "leverage": p.get("leverage"),
        }
        for p in pool
    ]
    return wrap_data({"players": players, "metadata": metadata.get("ownership", {})}, source="native")


class SimsRequest(BaseModel):
    slate_id: int
    platform: str = "draftkings"
    n_sims: int = Field(default=2000, ge=1, le=SAFE_SIM_LIMIT)
    lineups: Optional[List[dict]] = None  # optional built lineups to simulate
    seed: Optional[int] = 42


@router.post("/sims/run")
async def run_sims(
    body: SimsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run SB ME simulations over a slate pool and (optionally) built lineups."""
    pool, metadata = await build_canonical_pool(db, body.slate_id, platform=body.platform, with_ownership=True)
    if not pool:
        raise HTTPException(404, "Slate not found or not published")

    sport = (metadata.get("sport") or "MLB").upper()
    pool_sims = simulate_pool(pool, sport=sport, n_sims=body.n_sims, seed=body.seed)

    lineup_sims = None
    if body.lineups:
        lineup_sims = simulate_lineups(body.lineups, pool, sport=sport, n_sims=body.n_sims, seed=body.seed)

    return wrap_data({
        "players": pool_sims["players"],
        "lineups": lineup_sims["lineups"] if lineup_sims else None,
        "metadata": {**pool_sims["metadata"], "slate_id": body.slate_id},
    }, source="native")


@router.get("/optimal-pct")
@router.get("/data-hub/optimal-pct")
async def optimal_pct(
    slate_id: int,
    platform: str = "draftkings",
    sport: str = "MLB",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Customer: Optimal% simulation status + cached result (background-computed).

    Returns status (NOT_RUN/QUEUED/RUNNING/COMPLETE/FAILED/LOCKED) and, when
    COMPLETE AND the slate is still unlocked, the per-player optimal_pct.
    Never runs the simulation synchronously.

    Phase 2D: after the slate locks (now >= start_time), the cached result
    is NOT served as current actionable Optimal%.  Status returns LOCKED.
    """
    import dfs.optimal_cache as ocache
    from dfs.optimal_lock import is_slate_locked, slate_lock_status
    from dfs.db import DFSSlate
    from sqlalchemy import select

    # ── Lock-time eligibility check ──
    stmt = select(DFSSlate).where(DFSSlate.id == slate_id)
    r = await db.execute(stmt)
    slate = r.scalar_one_or_none()
    if slate is None:
        return wrap_data({"slate_id": slate_id, "status": "UNKNOWN"}, source="native")

    # Cache keys are platform-lower + sport-upper (worker stores slate.platform / slate.sport).
    plat = (platform or slate.platform or "draftkings").lower()
    sp = (sport or slate.sport or "MLB").upper()

    lock_status = slate_lock_status(slate.start_time)
    if is_slate_locked(slate.start_time):
        return wrap_data({
            "slate_id": slate_id,
            "platform": plat,
            "sport": sp,
            "status": "LOCKED",
            "lock_status": lock_status.value,
            "note": "Optimal% is not available for locked/in-progress slates",
        }, source="native")

    status = ocache.get_status(plat, sp, slate_id)
    if status == ocache.STATUS_NOT_RUN:
        slate_plat = (slate.platform or plat).lower()
        slate_sp = (slate.sport or sp).upper()
        if slate_plat != plat or slate_sp != sp:
            alt = ocache.get_status(slate_plat, slate_sp, slate_id)
            if alt != ocache.STATUS_NOT_RUN:
                plat, sp, status = slate_plat, slate_sp, alt

    result = None
    if status == ocache.STATUS_COMPLETE:
        result = ocache.get_result(plat, sp, slate_id)

    return wrap_data({
        "slate_id": slate_id,
        "platform": plat,
        "sport": sp,
        "status": status,
        "lock_status": lock_status.value,
        "result": result,
    }, source="native")


@router.get("/top-stacks")
async def top_stacks(
    slate_id: int,
    platform: str = "draftkings",
    with_sims: bool = False,
    n_sims: int = 2000,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SB ME Top Stacks for a slate, with optional optimal-stack simulation."""
    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    if not pool:
        raise HTTPException(404, "Slate not found or not published")

    sport = (metadata.get("sport") or "MLB").upper()
    sim_metrics = None
    if with_sims:
        sim_metrics = simulate_pool(pool, sport=sport, n_sims=n_sims)

    result = build_top_stacks(pool, sport=sport, platform=platform, sim_metrics=sim_metrics)
    return wrap_data({"stacks": result["stacks"], "metadata": result["metadata"]}, source="native")
