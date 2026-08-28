"""
SB-Me Analyst API endpoints.

Endpoints:
  GET  /api/analyst/player/{id}?slate_id=
  GET  /api/analyst/game/{id}
  GET  /api/analyst/slate/{id}
  GET  /api/analyst/projection-change/{entity_id}
  GET  /api/analyst/top-edges?slate_id=
  GET  /api/analyst/risks?entity_id=&entity_type=
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data
from ai.projection_service import log_audit_record

from analyst.engine import (
    MatchupEngine, RiskEngine, EdgeEngine,
    ProjectionChangeAnalyzer, ConfidenceDecomposer,
)
from analyst.models import AnalystInsight
from analyst.schemas import (
    PlayerInsightResponse, GameInsightResponse,
    SlateInsightResponse, ProjectionChangeResponse, TopEdgesResponse,
)

router = APIRouter(prefix="/analyst", tags=["SB-Me Analyst"])


# ── Gating ───────────────────────────────────────────────────

ANALYST_GATING = {
    "free": {"max_daily": 10, "full_analysis": False, "edge_score": False, "risk_detail": False},
    "pro_arena": {"max_daily": 200, "full_analysis": True, "edge_score": True, "risk_detail": True},
    "elite_stack": {"max_daily": 2000, "full_analysis": True, "edge_score": True, "risk_detail": True},
}

_rate_tracker: dict = {}


def _get_tier(user: User) -> str:
    if not user.is_pro:
        return "free"
    try:
        sub = getattr(user, "subscription", None)
        if sub and getattr(sub, "plan_name", "") == "Elite Stack":
            return "elite_stack"
    except Exception:
        pass
    return "pro_arena"


def _check_rate(user: User) -> tuple:
    tier = _get_tier(user)
    limits = ANALYST_GATING[tier]
    key = f"analyst:{user.id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    count = _rate_tracker.get(key, 0)
    return count < limits["max_daily"], count, limits["max_daily"], tier


# ── Endpoints ────────────────────────────────────────────────

def _unavailable_player_payload(player_id: int) -> dict:
    return {
        "insight_id": f"player:{player_id}:unavailable",
        "entity_id": player_id,
        "entity_type": "player",
        "sport": "mlb",
        "league": "MLB",
        "headline": "Analyst insight unavailable",
        "summary": (
            "Live player analysis is not populated with demo data. "
            "Use Data Hub and Last-5 history for current SB ME intelligence."
        ),
        "verified_facts": [],
        "projection_factors": [],
        "market_factors": [],
        "injury_factors": [],
        "matchup_factors": [],
        "risk_factors": [],
        "edge_score": None,
        "confidence_score": 0.0,
        "confidence_components": {},
        "source_event_ids": [],
        "model_name": "analyst_v1",
        "model_version": "7c.0.1",
        "data_timestamp": datetime.now(timezone.utc),
        "stale_data_flag": True,
        "missing_data_flags": ["live_player_record"],
        "available": False,
    }


# ── Endpoints ────────────────────────────────────────────────

@router.get("/player/{player_id}")
async def player_analysis(
    player_id: int,
    slate_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = time.time()
    allowed, count, limit, tier = _check_rate(user)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Daily limit ({limit}) reached.")

    _rate_tracker[f"analyst:{user.id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"] = count + 1

    insight_id = f"player:{player_id}:{uuid.uuid4().hex[:8]}"
    response = _unavailable_player_payload(player_id)
    response["insight_id"] = insight_id

    await log_audit_record(db=db, user_id=user.id, endpoint="/analyst/player", action="player_analysis",
        request_body={"player_id": player_id}, response_body={"insight_id": insight_id},
        model_version="7c.0.1", latency_ms=(time.time()-start)*1000, success=True)
    return wrap_data(response, source="analyst_engine")


@router.get("/game/{game_id}")
async def game_analysis(game_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    insight_id = f"game:{game_id}:{uuid.uuid4().hex[:8]}"
    return wrap_data({
        "insight_id": insight_id, "entity_id": game_id, "entity_type": "game",
        "sport": "nba", "league": "NBA",
        "headline": f"Game {game_id} Analysis",
        "summary": "Live game analysis is not populated with demo data.",
        "verified_facts": [f"Game ID: {game_id}"],
        "projection_factors": [], "market_factors": [], "injury_factors": [], "matchup_factors": [],
        "risk_factors": [], "edge_score": None,
        "confidence_score": 0.5, "confidence_components": {},
        "source_event_ids": [], "model_name": "analyst_v1", "model_version": "7c.0.1",
        "data_timestamp": datetime.now(timezone.utc), "stale_data_flag": False, "missing_data_flags": [],
        "home_team": None, "away_team": None, "spread": None, "total": None,
    }, source="analyst_engine")


@router.get("/slate/{slate_id}")
async def slate_analysis(slate_id: int, user: User = Depends(get_current_user)):
    insight_id = f"slate:{slate_id}:{uuid.uuid4().hex[:8]}"
    return wrap_data({
        "insight_id": insight_id, "slate_id": slate_id,
        "sport": "nba", "league": "NBA",
        "headline": f"Slate {slate_id} Summary",
        "summary": "Slate-level analysis is not populated with demo data.",
        "top_players": [], "top_edges": [], "risk_summary": [],
        "confidence_score": 0.6, "model_version": "7c.0.1",
        "data_timestamp": datetime.now(timezone.utc),
    }, source="analyst_engine")


@router.get("/projection-change/{entity_id}")
async def projection_change(entity_id: int, user: User = Depends(get_current_user)):
    result = ProjectionChangeAnalyzer.analyze(
        entity_id=entity_id, entity_type="player",
        current_projection=0.0, previous_projection=None,
    )
    return wrap_data({"insight_id": f"projchange:{entity_id}:{uuid.uuid4().hex[:8]}",
        **result, "model_version": "7c.0.1", "data_timestamp": datetime.now(timezone.utc)}, source="analyst_engine")


@router.get("/top-edges")
async def top_edges(slate_id: int, user: User = Depends(get_current_user)):
    tier = _get_tier(user)
    if not ANALYST_GATING[tier]["edge_score"]:
        raise HTTPException(status_code=403, detail="Edge scores require Pro Arena or higher.")
    return wrap_data({
        "slate_id": slate_id, "sport": "mlb", "edges": [],
        "available": False,
        "message": "Top edges require live canonical-pool analysis; demo NBA edges are not served.",
        "generated_at": datetime.now(timezone.utc), "model_version": "7c.0.1",
    }, source="analyst_engine")


@router.get("/risks")
async def get_risks(entity_id: int, entity_type: str = "player", user: User = Depends(get_current_user)):
    tier = _get_tier(user)
    if not ANALYST_GATING[tier]["risk_detail"]:
        raise HTTPException(status_code=403, detail="Risk details require Pro Arena or higher.")
    return wrap_data({
        "entity_id": entity_id, "entity_type": entity_type,
        "risks": [], "aggregate_score": 0.0,
        "available": False,
        "message": "Live risk detail is not populated with demo player records.",
        "model_version": "7c.0.1",
    }, source="analyst_engine")