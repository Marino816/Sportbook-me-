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


# ── Demo data helpers ────────────────────────────────────────

def _demo_player_data() -> dict:
    return {
        "id": 1, "name": "Luka Doncic", "team": "DAL", "salary": 11000,
        "projected_fp": 55.4, "avg_fp_last_5": 52.0, "pace": 102.5,
        "usage": 0.35, "rest_days": 2, "injury_status": "Healthy",
        "starting_status": "Confirmed", "games_played": 20,
        "minutes": 36, "recent_form": 55.0, "is_home": True,
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

    data = _demo_player_data()
    data["id"] = player_id

    matchup = MatchupEngine.analyze(data)
    risks = RiskEngine.assess(data)
    risk_score = RiskEngine.aggregate_risk_score(risks)
    confidence = ConfidenceDecomposer.decompose(
        data_quality=0.8, sample_size=data.get("games_played", 0),
        market_available=bool(data.get("salary")), injury_known=data.get("injury_status") == "Healthy",
        data_is_recent=True,
    )
    med = data.get("projected_fp", 0)
    edge, components = EdgeEngine.calculate(
        projection_score=med / 70.0 if med else 0.5,
        matchup_score=len(matchup["factors"]) / max(len(matchup["factors"]) + len(matchup["missing_factors"]), 1),
        market_alignment=0.7, ownership_leverage=0.5,
        data_quality=1.0 - len(matchup.get("missing_factors", [])) * 0.05,
        confidence=confidence["data_quality"], risk_count=len(risks),
    )

    insight_id = f"player:{player_id}:{uuid.uuid4().hex[:8]}"
    response = {
        "insight_id": insight_id, "entity_id": player_id, "entity_type": "player",
        "sport": "nba", "league": "NBA",
        "headline": f"{data['name']}: {EdgeEngine.tier(edge)} — {med:.1f} FP",
        "summary": f"Projected {med:.1f} FP. Matchup: {len(matchup['factors'])} factors available. {len(risks)} risks identified. Edge: {edge:.0f}/100.",
        "verified_facts": [f"Team: {data.get('team','')}", f"Salary: ${data.get('salary',0):,}", f"Status: {data.get('injury_status','')}",
                          f"Starting: {data.get('starting_status','')}"],
        "projection_factors": [{"factor": "projection", "value": med, "label": f"Projected: {med:.1f} FP"}],
        "market_factors": [{"factor": "salary", "value": data.get("salary"), "label": f"Salary: ${data.get('salary',0):,}"}] if data.get("salary") else [],
        "injury_factors": [{"factor": "injury", "value": data.get("injury_status"), "label": f"Status: {data.get('injury_status','')}"}],
        "matchup_factors": matchup["factors"],
        "risk_factors": risks,
        "edge_score": edge if ANALYST_GATING[tier]["edge_score"] else None,
        "confidence_score": confidence["data_quality"],
        "confidence_components": confidence,
        "source_event_ids": [],
        "model_name": "analyst_v1", "model_version": "7c.0.1",
        "data_timestamp": datetime.now(timezone.utc),
        "stale_data_flag": False, "missing_data_flags": matchup.get("missing_factors", []),
    }

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
        "summary": "Game analysis uses live data when available. Demo mode active.",
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
        "summary": "Slate-level analysis aggregates player projections. Demo mode active.",
        "top_players": [], "top_edges": [], "risk_summary": [],
        "confidence_score": 0.6, "model_version": "7c.0.1",
        "data_timestamp": datetime.now(timezone.utc),
    }, source="analyst_engine")


@router.get("/projection-change/{entity_id}")
async def projection_change(entity_id: int, user: User = Depends(get_current_user)):
    result = ProjectionChangeAnalyzer.analyze(
        entity_id=entity_id, entity_type="player",
        current_projection=55.4, previous_projection=52.1,
    )
    return wrap_data({"insight_id": f"projchange:{entity_id}:{uuid.uuid4().hex[:8]}",
        **result, "model_version": "7c.0.1", "data_timestamp": datetime.now(timezone.utc)}, source="analyst_engine")


@router.get("/top-edges")
async def top_edges(slate_id: int, user: User = Depends(get_current_user)):
    tier = _get_tier(user)
    if not ANALYST_GATING[tier]["edge_score"]:
        raise HTTPException(status_code=403, detail="Edge scores require Pro Arena or higher.")
    return wrap_data({
        "slate_id": slate_id, "sport": "nba", "edges": [
            {"entity_id": 1, "name": "Luka Doncic", "edge_score": 78.5, "tier": "Strong Edge"},
            {"entity_id": 2, "name": "Stephen Curry", "edge_score": 72.3, "tier": "Strong Edge"},
            {"entity_id": 3, "name": "Nikola Jokic", "edge_score": 85.1, "tier": "Elite Edge"},
        ],
        "generated_at": datetime.now(timezone.utc), "model_version": "7c.0.1",
    }, source="analyst_engine")


@router.get("/risks")
async def get_risks(entity_id: int, entity_type: str = "player", user: User = Depends(get_current_user)):
    tier = _get_tier(user)
    if not ANALYST_GATING[tier]["risk_detail"]:
        raise HTTPException(status_code=403, detail="Risk details require Pro Arena or higher.")
    data = _demo_player_data()
    data["id"] = entity_id
    risks = RiskEngine.assess(data)
    return wrap_data({
        "entity_id": entity_id, "entity_type": entity_type,
        "risks": risks, "aggregate_score": RiskEngine.aggregate_risk_score(risks),
        "model_version": "7c.0.1",
    }, source="analyst_engine")