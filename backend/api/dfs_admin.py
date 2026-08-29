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
from dfs.reconciliation import reconcile_db_players, merge_reconciliation_report
from dfs.import_service import import_slate_file, ImportResult
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

    # Canonical import + validation (shared DK/FD path)
    result = await import_slate_file(content, platform, filename)
    if not result.validation.passed:
        raise HTTPException(400, {
            "detail": "Slate validation failed",
            "errors": result.validation.errors,
            "warnings": result.validation.warnings,
        })
    if not result.players:
        raise HTTPException(400, "Zero players found in CSV")

    slate_obj = result.slate_obj
    players = result.players
    if slate_obj is None:
        raise HTTPException(400, "Slate parsing produced no metadata")

    # CURRENT slates are published. UPCOMING weekly (NFL/NCAAF) slates are
    # also published so weekend contests are selectable before game day.
    # STALE slates stay DRAFT.
    freshness = result.fresh_status
    from dfs.freshness import is_auto_publishable
    start_for_pub = slate_obj.start_time if slate_obj else None
    initial_status = (
        "PUBLISHED"
        if is_auto_publishable(start_for_pub, result.sport)
        else "DRAFT"
    )

    db_slate = SlateDB(
        platform=platform, sport=slate_obj.sport,
        external_slate_id=slate_obj.slate_id, slate_name=slate_obj.slate_name,
        start_time=slate_obj.start_time, uploaded_by=admin.id, status=initial_status,
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

    # ── Auto-reconcile: match DK players against SGO player pool ──
    reconciliation = None
    try:
        sgo_players = await _fetch_sgo_players(slate_obj.sport)
        result = await db.execute(select(PlayerDB).where(PlayerDB.slate_id == db_slate.id))
        db_players = result.scalars().all()
        stats = reconcile_db_players(db_players, sgo_players)
        if db_slate.status != "PUBLISHED":
            db_slate.status = "REVIEW" if stats["review"] > 0 else "DRAFT"
        db_slate.matched_count = stats["matched"]
        db_slate.review_count = stats["review"]
        db_slate.unmatched_count = stats["unmatched"]
        db_slate.reconciliation_report = merge_reconciliation_report(
            db_slate.reconciliation_report, stats
        )
        await db.commit()
        await db.refresh(db_slate)
        reconciliation = dict(db_slate.reconciliation_report)
    except Exception as e:
        logger.warning("Auto-reconcile failed (non-fatal): %s", e)
        reconciliation = {"status": "SKIPPED", "reason": str(e)}

    return wrap_data({
        "slate_id": db_slate.id, "platform": platform, "sport": slate_obj.sport,
        "slate_name": db_slate.slate_name, "player_count": len(players),
        "game_count": result.game_count, "slate_date": result.slate_date,
        "status": initial_status, "freshness": freshness,
        "warnings": result.validation.warnings,
        "reconciliation": reconciliation,
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

    stats = reconcile_db_players(db_players, sgo_players)
    slate.matched_count = stats["matched"]
    slate.review_count = stats["review"]
    slate.unmatched_count = stats["unmatched"]
    # Never downgrade PUBLISHED during reconciliation
    if slate.status != "PUBLISHED":
        slate.status = "REVIEW" if stats["review"] > 0 else "DRAFT"
    slate.reconciliation_report = merge_reconciliation_report(
        slate.reconciliation_report, stats
    )
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