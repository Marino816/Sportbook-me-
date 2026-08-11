"""Admin DFS slate management API — upload, review, publish, archive."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from api.auth import get_current_user, require_admin
from models.domain import User
from dfs.db import DFSSlate as SlateDB, DFSPlayer as PlayerDB
from dfs.parsers import parse_draftkings_csv, parse_fanduel_csv
from dfs.reconciliation import reconcile_player
from dfs.models import DFSContestPlayer
from api.utils import wrap_data

router = APIRouter(prefix="/admin/dfs", tags=["Admin DFS"])
logger = logging.getLogger(__name__)


@router.post("/slates/upload")
async def upload_slate(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin uploads a DK or FD contest CSV file."""
    content = (await file.read()).decode("utf-8", errors="replace")
    filename = file.filename or "unnamed.csv"
    platform = "fanduel" if "fan" in filename.lower() or "fd" in filename.lower() else "draftkings"

    # Parse
    try:
        if platform == "draftkings":
            slate, players = parse_draftkings_csv(content, slate_name=filename.replace(".csv", ""))
        else:
            slate, players = parse_fanduel_csv(content, slate_name=filename.replace(".csv", ""))
    except Exception as e:
        raise HTTPException(400, f"CSV parse error: {e}")

    if not players:
        raise HTTPException(400, "CSV parsed successfully but zero players found")

    # Validate
    sport = slate.sport
    if sport not in ("MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "PGA", "UFC"):
        raise HTTPException(400, f"Unsupported sport: {sport}")

    # Persist slate
    db_slate = SlateDB(
        platform=platform,
        sport=sport,
        external_slate_id=slate.slate_id,
        slate_name=slate.slate_name,
        start_time=slate.start_time,
        uploaded_by=admin.id,
        status="DRAFT",
        data_source="native",
        player_count=len(players),
        matched_count=0,
        review_count=0,
        unmatched_count=len(players),
    )
    db.add(db_slate)
    await db.flush()

    # Persist players
    for p in players:
        db_player = PlayerDB(
            slate_id=db_slate.id,
            provider_player_id=p.player_id,
            player_name=p.player_name,
            team=p.team,
            opponent=p.opponent,
            position=p.position,
            eligible_positions=p.eligible_positions,
            salary=p.salary,
            game_info=p.game_info,
            mapping_confidence=0.0,
            mapping_status="UNMATCHED",
        )
        db.add(db_player)

    await db.commit()
    await db.refresh(db_slate)

    return wrap_data({
        "slate_id": db_slate.id,
        "platform": platform,
        "sport": sport,
        "slate_name": db_slate.slate_name,
        "player_count": len(players),
        "status": "DRAFT",
        "reconciliation_needed": True,
    })


@router.post("/slates/{slate_id}/reconcile")
async def reconcile_slate(
    slate_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Run SGO reconciliation on a slate's players."""
    # Load slate
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")

    # Load SGO players from provider cache
    sgo_players = []
    try:
        from providers.integration import SGOIntegration
        async with SGOIntegration() as sgo:
            sgo_raw = await sgo._provider.get_players(league_id=slate.sport)
            for raw in sgo_raw:
                pid = raw.get("playerID") or raw.get("id") or ""
                names = raw.get("names", {})
                name = (names.get("display") or names.get("full") or names.get("name")
                        or raw.get("name") or "")
                team = raw.get("teamID") or raw.get("team") or ""
                position = raw.get("position") or ""
                if pid:
                    sgo_players.append({
                        "playerID": str(pid),
                        "name": name,
                        "team": str(team),
                        "position": position,
                    })
    except Exception as e:
        logger.warning(f"SGO player load failed for reconciliation: {e}")
        sgo_players = []

    matched, review, unmatched = 0, 0, 0

    # Load slate players
    result = await db.execute(select(PlayerDB).where(PlayerDB.slate_id == slate_id))
    db_players = result.scalars().all()

    for dbp in db_players:
        dp = DFSContestPlayer(
            platform=slate.platform, player_id=dbp.provider_player_id,
            player_name=dbp.player_name, team=dbp.team, opponent=dbp.opponent or "",
            position=dbp.position, salary=dbp.salary, game_info=dbp.game_info or "",
        )
        sgo_id = reconcile_player(dp, sgo_players)
        if sgo_id and dp.sbme_confidence >= 0.95:
            dbp.mapping_status = "MATCHED"
            dbp.sbme_player_id = sgo_id
            dbp.mapping_confidence = dp.sbme_confidence
            matched += 1
        elif sgo_id and dp.sbme_confidence >= 0.85:
            dbp.mapping_status = "REVIEW_REQUIRED"
            dbp.sbme_player_id = sgo_id
            dbp.mapping_confidence = dp.sbme_confidence
            review += 1
        else:
            dbp.mapping_status = "UNMATCHED"
            unmatched += 1

    slate.matched_count = matched
    slate.review_count = review
    slate.unmatched_count = unmatched
    slate.status = "REVIEW" if review > 0 else "DRAFT"
    slate.reconciliation_report = {"matched": matched, "review": review, "unmatched": unmatched, "total": len(db_players)}

    await db.commit()
    return wrap_data(slate.reconciliation_report)


@router.post("/slates/{slate_id}/publish")
async def publish_slate(
    slate_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Publish a slate for customer use."""
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")
    if slate.matched_count < 10:
        raise HTTPException(400, f"Only {slate.matched_count} matched — minimum 10 required for publish")
    slate.status = "PUBLISHED"
    slate.published_at = datetime.now(timezone.utc)
    await db.commit()
    return wrap_data({"slate_id": slate_id, "status": "PUBLISHED"})


@router.get("/slates")
async def list_slates(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin list all slates."""
    result = await db.execute(select(SlateDB).order_by(SlateDB.uploaded_at.desc()))
    slates = result.scalars().all()
    return wrap_data([{
        "id": s.id, "platform": s.platform, "sport": s.sport,
        "slate_name": s.slate_name, "player_count": s.player_count,
        "matched": s.matched_count, "review": s.review_count, "unmatched": s.unmatched_count,
        "status": s.status, "uploaded_at": str(s.uploaded_at) if s.uploaded_at else None,
        "published_at": str(s.published_at) if s.published_at else None,
    } for s in slates])


@router.delete("/slates/{slate_id}")
async def archive_slate(
    slate_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")
    slate.status = "ARCHIVED"
    await db.commit()
    return {"ok": True}