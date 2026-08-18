"""Customer-facing DFS slate API — published slates for optimizer/mobile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db
from api.auth import get_current_user
from models.domain import User
from dfs.db import DFSSlate as SlateDB, DFSPlayer as PlayerDB
from api.utils import wrap_data

router = APIRouter(prefix="/dfs", tags=["DFS Slates"])


@router.get("/slates")
async def list_published_slates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    platform: str = None,
    sport: str = None,
):
    """Customer: list published slates, optionally filtered."""
    q = select(SlateDB).where(SlateDB.status == "PUBLISHED")
    if platform:
        q = q.where(SlateDB.platform == platform.lower())
    if sport:
        q = q.where(SlateDB.sport == sport.upper())
    q = q.order_by(SlateDB.start_time.asc())

    result = await db.execute(q)
    slates = result.scalars().all()

    # Compute per-slate game count from distinct game_info values
    game_counts: dict[int, int] = {}
    if slates:
        from sqlalchemy import func
        slate_ids = [s.id for s in slates]
        gc_rows = await db.execute(
            select(PlayerDB.slate_id, func.count(func.distinct(PlayerDB.game_info)))
            .where(PlayerDB.slate_id.in_(slate_ids))
            .group_by(PlayerDB.slate_id)
        )
        game_counts = {row[0]: row[1] for row in gc_rows}

    def _is_current(s_start) -> bool:
        from dfs.freshness import is_current_slate

        return is_current_slate(s_start) if s_start else False

    return wrap_data([{
        "id": s.id,
        "platform": s.platform,
        "sport": s.sport,
        "slate_name": s.slate_name,
        "start_time": str(s.start_time) if s.start_time else None,
        "slate_date": s.start_time.date().isoformat() if s.start_time else None,
        "is_current": _is_current(s.start_time),
        "game_count": game_counts.get(s.id, 0),
        "player_count": s.player_count,
        "status": s.status,
        "data_source": s.data_source,
    } for s in slates])


@router.get("/slates/{slate_id}")
async def get_slate(
    slate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Customer: get slate with player pool."""
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id, SlateDB.status == "PUBLISHED"))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found or not published")

    result = await db.execute(select(PlayerDB).where(PlayerDB.slate_id == slate_id))
    players = result.scalars().all()

    return wrap_data({
        "id": slate.id,
        "platform": slate.platform,
        "sport": slate.sport,
        "slate_name": slate.slate_name,
        "start_time": str(slate.start_time) if slate.start_time else None,
        "player_count": len(players),
        "data_source": slate.data_source,
        "players": [{
            "player_id": p.sbme_player_id or p.provider_player_id,
            "name": p.player_name,
            "team": p.team,
            "opponent": p.opponent,
            "position": p.position,
            "eligible_positions": p.eligible_positions,
            "salary": p.salary,
            "game_info": p.game_info,
            "mapping_status": p.mapping_status,
        } for p in players],
    })