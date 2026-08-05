"""
SB-Me Mission Control API endpoints.

Endpoints:
  GET  /api/mission-control
  GET  /api/mission-control/widgets
  GET  /api/mission-control/briefing
  GET  /api/mission-control/alerts
  GET  /api/mission-control/system-health
  GET  /api/mission-control/activity
  POST /api/mission-control/preferences
  GET  /api/mission-control/preferences
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data

from mission_control.engine import (
    WIDGETS, widget_payload, briefing, AlertPriority, HealthAggregator,
)

router = APIRouter(prefix="/mission-control", tags=["SB-Me Mission Control"])

GATING = {
    "free": {"widgets": ["daily_briefing","builder_status","data_freshness","slate_overview","subscription_status","recent_activity"]},
    "pro_arena": {"widgets": "all"},
    "elite_stack": {"widgets": "all"},
}

def _tier(user: User) -> str:
    if not user.is_pro: return "free"
    try:
        s = getattr(user, "subscription", None)
        if s and getattr(s, "plan_name", "") == "Elite Stack": return "elite_stack"
    except: pass
    return "pro_arena"

def _allowed(widget_id: str, tier: str) -> bool:
    allowed = GATING[tier]["widgets"]
    if allowed == "all": return True
    return widget_id in allowed


# ── Preference Schemas ───────────────────────────────────────
class PreferenceUpdate(BaseModel):
    favorite_sport: Optional[str] = None
    favorite_platform: Optional[str] = None
    widget_layout: Optional[List[str]] = None
    hidden_widgets: Optional[List[str]] = None


# ── Endpoints ────────────────────────────────────────────────

@router.get("")
async def mission_control(user: User = Depends(get_current_user)):
    tier = _tier(user)
    widgets = {}
    for wid, wdef in WIDGETS.items():
        if _allowed(wid, tier) and wdef.get("is_enabled", True):
            widgets[wid] = widget_payload(wid, tier)
    return wrap_data({"widgets": widgets, "widget_count": len(widgets), "tier": tier}, source="mission_control")


@router.get("/widgets")
async def get_widgets(user: User = Depends(get_current_user)):
    tier = _tier(user)
    return wrap_data({"widgets": [
        {"widget_id": w["widget_id"], "title": w["title"], "type": w["widget_type"],
         "subscription_required": w["subscription_required"],
         "accessible": _allowed(w["widget_id"], tier)}
        for w in WIDGETS.values()
    ]}, source="mission_control")


@router.get("/briefing")
async def get_briefing(user: User = Depends(get_current_user)):
    tier = _tier(user)
    return wrap_data(briefing(tier), source="mission_control")


@router.get("/alerts")
async def get_alerts(user: User = Depends(get_current_user)):
    tier = _tier(user)
    alerts = [
        {"severity": "high", "event_type": "odds_movement", "title": "Odds: LAL -4.5 → -6.5", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"severity": "info", "event_type": "lineup_confirmation", "title": "DAL starting lineup confirmed", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]
    if tier == "free":
        alerts = [a for a in alerts if a["severity"] in ("critical",)]
    return wrap_data({"alerts": AlertPriority.order(alerts), "total": len(alerts)}, source="mission_control")


@router.get("/system-health")
async def system_health(user: User = Depends(get_current_user)):
    return wrap_data(HealthAggregator.aggregate(), source="mission_control")


@router.get("/activity")
async def recent_activity(user: User = Depends(get_current_user)):
    return wrap_data({"items": [
        {"action": "Builder run", "detail": "1 lineup, balanced", "time": datetime.now(timezone.utc).isoformat()},
        {"action": "Coach review", "detail": "5 contests", "time": datetime.now(timezone.utc).isoformat()},
    ]}, source="mission_control")


@router.post("/preferences")
async def save_preferences(body: PreferenceUpdate, user: User = Depends(get_current_user)):
    return wrap_data({"status": "saved", "preferences": body.model_dump(exclude_none=True)}, source="mission_control")


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    tier = _tier(user)
    return wrap_data({
        "favorite_sport": "nba", "favorite_platform": "draftkings",
        "widget_layout": ["daily_briefing", "scout_alerts", "analyst_insights", "builder_status"],
        "hidden_widgets": [],
        "tier": tier,
    }, source="mission_control")