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


def _extract_sgo_player(raw: dict) -> dict:
    """Extract normalized SGO player dict from raw response."""
    pid = raw.get("playerID") or raw.get("id") or ""
    if not pid:
        return None
    names = raw.get("names", {})
    name = (names.get("display") or names.get("full") or names.get("name")
            or raw.get("name") or "")
    return {
        "playerID": str(pid),
        "name": name,
        "team": str(raw.get("teamID") or raw.get("team") or ""),
        "position": raw.get("position") or "",
    }


async def _fetch_sgo_players(sport: str) -> list[dict]:
    """Fetch SGO player pool — events first, then league fallback."""
    players = []
    from providers.integration import SGOIntegration
    async with SGOIntegration() as sgo:
        # Method 1: events with embedded/team players
        try:
            sgo_events = await sgo._provider.get_events(league_id=sport)
            for ev in sgo_events:
                embedded = ev.get("players") or ev.get("roster") or []
                for raw in embedded:
                    p = _extract_sgo_player(raw)
                    if p:
                        players.append(p)
                if not embedded:
                    for team_field in ["homeTeamID", "awayTeamID"]:
                        tid = ev.get(team_field)
                        if not tid:
                            teams_obj = ev.get("teams", {})
                            side = teams_obj.get(team_field.replace("TeamID", ""), {})
                            tid = side.get("teamID") if isinstance(side, dict) else None
                        if tid:
                            try:
                                tp = await sgo._provider._request("GET",
                                    f"/players?teamID={tid}&limit=50")
                                if isinstance(tp, list):
                                    for raw in tp:
                                        p = _extract_sgo_player(raw)
                                        if p:
                                            players.append(p)
                            except Exception:
                                pass
        except Exception as e:
            logger.warning(f"SGO event player fetch failed: {e}")

        # Method 2: league-level players as fallback
        if len(players) < 100:
            try:
                more = await sgo._provider.get_players(league_id=sport)
                for raw in more:
                    p = _extract_sgo_player(raw)
                    if p:
                        players.append(p)
            except Exception as e:
                logger.warning(f"SGO league player fetch failed: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for p in players:
        if p["playerID"] not in seen:
            seen.add(p["playerID"])
            unique.append(p)
    return unique


@router.post("/slates/upload")
async def upload_slate(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    content = (await file.read()).decode("utf-8", errors="replace")
    filename = file.filename or "unnamed.csv"
    platform = "fanduel" if "fan" in filename.lower() else "draftkings"

    try:
        if platform == "fanduel":
            slate_obj, players = parse_fanduel_csv(content, slate_name=filename.replace(".csv", ""))
        else:
            slate_obj, players = parse_draftkings_csv(content, slate_name=filename.replace(".csv", ""))
    except Exception as e:
        raise HTTPException(400, f"CSV parse error: {e}")

    if not players:
        raise HTTPException(400, "Zero players found in CSV")
    if slate_obj.sport not in ("MLB", "NFL", "NBA", "NHL"):
        raise HTTPException(400, f"Unsupported sport: {slate_obj.sport}")

    db_slate = SlateDB(
        platform=platform, sport=slate_obj.sport,
        external_slate_id=slate_obj.slate_id, slate_name=slate_obj.slate_name,
        start_time=slate_obj.start_time, uploaded_by=admin.id, status="DRAFT",
        data_source="native", player_count=len(players),
        matched_count=0, review_count=0, unmatched_count=len(players),
    )
    db.add(db_slate)
    await db.flush()

    for p in players:
        db.add(PlayerDB(
            slate_id=db_slate.id, provider_player_id=p.player_id,
            player_name=p.player_name, team=p.team, opponent=p.opponent,
            position=p.position, eligible_positions=p.eligible_positions,
            salary=p.salary, game_info=p.game_info,
            mapping_confidence=0.0, mapping_status="UNMATCHED",
        ))

    await db.commit()
    await db.refresh(db_slate)
    return wrap_data({
        "slate_id": db_slate.id, "platform": platform, "sport": slate_obj.sport,
        "slate_name": db_slate.slate_name, "player_count": len(players),
        "status": "DRAFT",
    })


@router.post("/slates/{slate_id}/reconcile")
async def reconcile_slate(
    slate_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")

    result = await db.execute(select(PlayerDB).where(PlayerDB.slate_id == slate_id))
    db_players = result.scalars().all()

    sgo_players = await _fetch_sgo_players(slate.sport)
    logger.info(f"Reconcile: {len(db_players)} DK vs {len(sgo_players)} SGO")

    matched, review, unmatched = 0, 0, 0
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
    slate.reconciliation_report = {
        "matched": matched, "review": review, "unmatched": unmatched,
        "total": len(db_players),
        "sgo_pool_size": len(sgo_players),
    }
    await db.commit()
    return wrap_data(slate.reconciliation_report)


@router.post("/slates/{slate_id}/publish")
async def publish_slate(
    slate_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SlateDB).where(SlateDB.id == slate_id))
    slate = result.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")
    slate.status = "PUBLISHED"
    slate.published_at = datetime.now(timezone.utc)
    await db.commit()
    return wrap_data({"slate_id": slate_id, "status": "PUBLISHED"})


@router.get("/slates")
async def list_slates(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SlateDB).order_by(SlateDB.uploaded_at.desc()))
    slates = result.scalars().all()
    return wrap_data([{
        "id": s.id, "platform": s.platform, "sport": s.sport,
        "slate_name": s.slate_name, "player_count": s.player_count,
        "matched": s.matched_count, "review": s.review_count,
        "unmatched": s.unmatched_count, "status": s.status,
        "uploaded_at": str(s.uploaded_at) if s.uploaded_at else None,
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