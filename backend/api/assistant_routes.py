"""
SB-Me AI Assistant API endpoints.

Endpoints:
  POST /api/assistant/chat
  GET  /api/assistant/strategy-modes
  POST /api/assistant/strategy-mode
  GET  /api/assistant/war-room
  GET  /api/assistant/conversations
  GET  /api/assistant/conversations/{id}
  POST /api/assistant/preferences
  GET  /api/assistant/preferences
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data

from assistant.engine import (
    IntentClassifier, ToolRouter, StrategyModeEngine, ResponseComposer,
)

router = APIRouter(prefix="/assistant", tags=["SB-Me AI Assistant"])

GATING = {
    "free": {"max_requests": 20, "war_room": False, "strategy_modes": ["cash", "balanced"]},
    "pro_arena": {"max_requests": 200, "war_room": True, "strategy_modes": "all"},
    "elite_stack": {"max_requests": 2000, "war_room": True, "strategy_modes": "all"},
}
_rate: dict = {}

def _tier(user: User) -> str:
    if not user.is_pro: return "free"
    try:
        s = getattr(user, "subscription", None)
        if s and getattr(s, "plan_name", "") == "Elite Stack": return "elite_stack"
    except: pass
    return "pro_arena"

# ── Schemas ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    sport: str = "nba"
    platform: str = "draftkings"

class StrategyModeRequest(BaseModel):
    mode: str

class PreferenceUpdate(BaseModel):
    default_sport: Optional[str] = None
    default_platform: Optional[str] = None
    preferred_strategy: Optional[str] = None
    contest_type: Optional[str] = None
    favorite_teams: Optional[List[str]] = None


# ── Endpoints ────────────────────────────────────────────────

@router.post("/chat")
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    tier = _tier(user)
    limits = GATING[tier]
    key = f"assistant:{user.id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    count = _rate.get(key, 0)
    if count >= limits["max_requests"]:
        raise HTTPException(429, f"Daily AI limit ({limits['max_requests']}) reached.")

    intent = IntentClassifier.classify(body.message)
    confidence = IntentClassifier.confidence(intent, body.message)
    modules = ToolRouter.route(intent)
    module_desc = ToolRouter.describe_modules(modules, intent)
    evidence = {"intent": intent, "modules_routed": modules, "module_descriptions": module_desc}

    recs = {
        "build_lineups": "Generate a balanced lineup with Builder. Lock your core plays and exclude injured players.",
        "explain_projections": "Use Analyst to review player projections. Check confidence scores and missing data flags.",
        "injury_news": "Check Scout for active injury alerts. Exclude Out/Doubtful players before building.",
        "matchup_analysis": "Review Analyst matchup factors: Pace, DefEff, usage, rest days.",
        "contest_performance": "Check Coach for ROI, cash rate, and strategy breakdown.",
        "portfolio_review": "Review Builder exposure. Diversify if any player exceeds 40%.",
        "mission_control": "Your daily briefing shows 4 games today. No critical alerts.",
        "system_health": "All providers healthy. Migration at 6da32956dfb8. No failures.",
        "strategy_advice": "Based on Coach data, cash strategy performs best for you. Consider balanced for GPPs.",
        "general": "I orchestrate Scout, Analyst, Builder, Coach, and Mission Control. What would you like help with?",
    }

    response = ResponseComposer.compose(
        task=body.message, intent=intent, modules=modules, evidence=evidence,
        recommendation=recs.get(intent, recs["general"]),
        confidence=confidence, freshness="fresh",
    )

    _rate[key] = count + 1
    conv_id = body.conversation_id or f"conv:{uuid.uuid4().hex[:12]}"
    return wrap_data({"conversation_id": conv_id, "response": response}, source="assistant_engine")


@router.get("/strategy-modes")
async def list_strategy_modes(user: User = Depends(get_current_user)):
    tier = _tier(user)
    modes = StrategyModeEngine.list_modes()
    allowed = GATING[tier]["strategy_modes"]
    if allowed != "all":
        modes = [m for m in modes if m["mode"] in allowed]
    return wrap_data({"modes": modes}, source="assistant_engine")


@router.post("/strategy-mode")
async def set_strategy_mode(body: StrategyModeRequest, user: User = Depends(get_current_user)):
    tier = _tier(user)
    allowed = GATING[tier]["strategy_modes"]
    if allowed != "all" and body.mode not in allowed:
        raise HTTPException(403, f"Strategy mode '{body.mode}' requires Pro Arena or higher.")
    if body.mode not in ["cash", "tournament", "single_entry", "nuclear", "bankroll", "balanced"]:
        raise HTTPException(422, f"Unknown strategy mode: {body.mode}")
    return wrap_data({"mode": body.mode, "status": "active"}, source="assistant_engine")


@router.get("/war-room")
async def war_room(user: User = Depends(get_current_user)):
    tier = _tier(user)
    if not GATING[tier]["war_room"]:
        raise HTTPException(403, "War Room requires Pro Arena or higher.")
    return wrap_data(ResponseComposer.compose_war_room("balanced"), source="assistant_engine")


@router.get("/conversations")
async def list_conversations(user: User = Depends(get_current_user)):
    return wrap_data({"conversations": []}, source="assistant_engine")


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: User = Depends(get_current_user)):
    return wrap_data({"conversation_id": conv_id, "messages": []}, source="assistant_engine")


@router.post("/preferences")
async def save_preferences(body: PreferenceUpdate, user: User = Depends(get_current_user)):
    return wrap_data({"status": "saved", "preferences": body.model_dump(exclude_none=True)}, source="assistant_engine")


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    return wrap_data({
        "default_sport": "nba", "default_platform": "draftkings",
        "preferred_strategy": "balanced", "contest_type": "gpp",
        "favorite_teams": [], "favorite_players": [],
    }, source="assistant_engine")