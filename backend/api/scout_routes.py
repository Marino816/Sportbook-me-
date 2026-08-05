"""
SB-Me Scout API endpoints — Mission Control + Admin Monitoring.

Endpoints:
  GET  /api/scout/events          — event feed (paginated)
  GET  /api/scout/events/{id}     — single event detail
  GET  /api/scout/providers       — provider health status
  GET  /api/scout/freshness       — data freshness report
  POST /api/scout/refresh         — trigger manual refresh
  GET  /api/scout/alerts          — user alert config (subscription-gated)
  POST /api/scout/alerts          — create alert
"""

import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data
from ai.projection_service import log_audit_record

from scout.models import ScoutEvent, ScoutProvider, ScoutAlert
from scout.event_detector import EventDetector
from scout.freshness import FreshnessTracker, RefreshPipeline
from scout.providers.base import list_provider_statuses, list_providers

router = APIRouter(prefix="/scout", tags=["SB-Me Scout"])


# ── Event Feed ───────────────────────────────────────────────

@router.get("/events")
async def get_events(
    sport: str = "nba",
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the structured event feed for Mission Control."""
    start = time.time()
    query = select(ScoutEvent)

    if event_type:
        query = query.where(ScoutEvent.event_type == event_type)
    if severity:
        query = query.where(ScoutEvent.severity == severity)
    if sport:
        query = query.where(ScoutEvent.sport == sport)

    query = query.order_by(ScoutEvent.timestamp.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()

    total_result = await db.execute(select(func.count(ScoutEvent.id)))
    total = total_result.scalar()

    await log_audit_record(
        db=db, user_id=user.id,
        endpoint="/api/scout/events", action="scout_events",
        request_body={"sport": sport, "limit": limit},
        response_body={"count": len(events)},
        model_version=None, latency_ms=(time.time() - start) * 1000,
        success=True,
    )

    return wrap_data({
        "events": [{
            "event_id": e.event_id,
            "event_type": e.event_type,
            "sport": e.sport,
            "severity": e.severity,
            "source": e.source,
            "title": e.title,
            "description": e.description,
            "affected_entities": e.affected_entities,
            "refresh_required": e.refresh_required,
            "refresh_completed": e.refresh_completed,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        } for e in events],
        "total": total,
        "offset": offset,
        "limit": limit,
    }, source="scout_engine")


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return detail for a single Scout event."""
    result = await db.execute(
        select(ScoutEvent).where(ScoutEvent.event_id == event_id)
    )
    event = result.scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return wrap_data({
        "event_id": event.event_id,
        "event_type": event.event_type,
        "sport": event.sport,
        "league": event.league,
        "severity": event.severity,
        "source": event.source,
        "title": event.title,
        "description": event.description,
        "affected_entities": event.affected_entities,
        "refresh_required": event.refresh_required,
        "refresh_completed": event.refresh_completed,
        "metadata": event.metadata_json,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
    }, source="scout_engine")


# ── Provider Health ──────────────────────────────────────────

@router.get("/providers")
async def get_provider_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return health status for all data providers."""
    statuses = list_provider_statuses()
    provider_list = list_providers()

    return wrap_data({
        "providers": [{
            "name": s.provider_name,
            "category": s.category.value,
            "freshness": s.freshness.value,
            "healthy": s.is_healthy,
            "last_sync": s.last_sync.isoformat() if s.last_sync else None,
        } for s in statuses],
        "total": len(statuses),
        "registered": provider_list,
    }, source="scout_engine")


# ── Freshness ────────────────────────────────────────────────

@router.get("/freshness")
async def get_freshness(
    user: User = Depends(get_current_user),
):
    """Return data freshness report for all providers."""
    report = FreshnessTracker.get_freshness_report()
    return wrap_data(report, source="scout_engine")


# ── Manual Refresh ───────────────────────────────────────────

@router.post("/refresh")
async def trigger_refresh(
    sport: str = "nba",
    slate_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger a projection refresh. Creates a Scout event."""
    detector = EventDetector(db)
    event = await detector._create_event(
        event_type="manual_refresh",
        severity="info",
        source="admin_ui",
        title=f"Manual refresh triggered for {sport}",
        sport=sport,
        refresh_required=True,
    )

    result = await RefreshPipeline.refresh_slate(
        slate_id or 0, reason="manual_refresh"
    )
    return wrap_data({
        "event": event.event_id,
        "refresh": result,
    }, source="scout_engine")


# ── Alerts (subscription-gated) ──────────────────────────────

@router.get("/alerts")
async def get_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's alert configurations."""
    if not user.is_pro:
        raise HTTPException(status_code=403, detail="Alerts require Pro Arena or higher.")

    result = await db.execute(
        select(ScoutAlert).where(ScoutAlert.user_id == user.id, ScoutAlert.is_active == True)
    )
    alerts = result.scalars().all()
    return wrap_data([{
        "id": a.id,
        "alert_type": a.alert_type,
        "sport": a.sport,
        "severity_min": a.severity_min,
        "is_active": a.is_active,
        "last_triggered": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        "trigger_count": a.trigger_count,
    } for a in alerts], source="scout_engine")


@router.post("/alerts")
async def create_alert(
    alert_type: str,
    sport: Optional[str] = "nba",
    entity_id: Optional[int] = None,
    severity_min: str = "warning",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert configuration."""
    if not user.is_pro:
        raise HTTPException(status_code=403, detail="Alerts require Pro Arena or higher.")

    alert = ScoutAlert(
        user_id=user.id,
        alert_type=alert_type,
        sport=sport,
        entity_id=entity_id,
        severity_min=severity_min,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return wrap_data({"id": alert.id, "status": "created"}, source="scout_engine")