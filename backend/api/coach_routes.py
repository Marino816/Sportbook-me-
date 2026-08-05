"""
SB-Me Coach API endpoints.

Endpoints:
  POST /api/coach/contests/import
  GET  /api/coach/contests/{id}
  GET  /api/coach/slates/{id}
  GET  /api/coach/performance
  GET  /api/coach/findings
  GET  /api/coach/recommendations
  GET  /api/coach/strategies
  GET  /api/coach/exposures
  POST /api/coach/review
  GET  /api/coach/sessions/{id}
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

from coach.engine import (
    ContestEvaluator, PerformanceAnalyzer, StrategyAnalyzer,
    RecommendationEngine, ConfidenceCalculator,
)

router = APIRouter(prefix="/coach", tags=["SB-Me Coach"])

# ── Gating ───────────────────────────────────────
GATING = {
    "free": {"max_reviews": 5, "full_performance": False},
    "pro_arena": {"max_reviews": 100, "full_performance": True},
    "elite_stack": {"max_reviews": 2000, "full_performance": True},
}
_rate: dict = {}

def _tier(user: User) -> str:
    if not user.is_pro: return "free"
    try:
        s = getattr(user, "subscription", None)
        if s and getattr(s, "plan_name", "") == "Elite Stack": return "elite_stack"
    except: pass
    return "pro_arena"

# ── Demo Contest Data ─────────────────────────────
DEMO_CONTESTS = [
    {"contest_id":"c1","user_id":1,"platform":"draftkings","sport":"nba","entry_fee":5.0,"entry_count":1000,"finishing_position":120,"payout":12.0,"final_lineup_score":285.5,"cash_line":272.0,"winning_score":340.0,"projected_score":270.0,"strategy_profile":"balanced","result_timestamp":datetime.now(timezone.utc)},
    {"contest_id":"c2","user_id":1,"platform":"draftkings","sport":"nba","entry_fee":5.0,"entry_count":500,"finishing_position":400,"payout":0.0,"final_lineup_score":250.0,"cash_line":275.0,"winning_score":330.0,"projected_score":265.0,"strategy_profile":"aggressive","result_timestamp":datetime.now(timezone.utc)},
    {"contest_id":"c3","user_id":1,"platform":"fanduel","sport":"nba","entry_fee":10.0,"entry_count":200,"finishing_position":45,"payout":35.0,"final_lineup_score":310.0,"cash_line":290.0,"winning_score":350.0,"projected_score":295.0,"strategy_profile":"cash","result_timestamp":datetime.now(timezone.utc)},
    {"contest_id":"c4","user_id":1,"platform":"draftkings","sport":"nba","entry_fee":1.0,"entry_count":5000,"finishing_position":250,"payout":8.0,"final_lineup_score":295.0,"cash_line":280.0,"winning_score":345.0,"projected_score":280.0,"strategy_profile":"large_gpp","result_timestamp":datetime.now(timezone.utc)},
    {"contest_id":"c5","user_id":1,"platform":"draftkings","sport":"nba","entry_fee":5.0,"entry_count":800,"finishing_position":600,"payout":0.0,"final_lineup_score":260.0,"cash_line":275.0,"winning_score":320.0,"projected_score":270.0,"strategy_profile":"aggressive","result_timestamp":datetime.now(timezone.utc)},
]

# ── Import Schema ────────────────────────────────
class ContestImport(BaseModel):
    contests: List[dict]
    platform: str = "draftkings"
    sport: str = "nba"

# ── Endpoints ────────────────────────────────────

@router.post("/contests/import")
async def import_contests(body: ContestImport, user: User = Depends(get_current_user)):
    imported = [{"contest_id": c.get("contest_id", ""), "status": "imported"} for c in body.contests[:50]]
    return wrap_data({"imported": len(imported), "contests": imported}, source="coach_engine")


@router.get("/contests/{contest_id}")
async def get_contest(contest_id: str, user: User = Depends(get_current_user)):
    c = next((x for x in DEMO_CONTESTS if x["contest_id"] == contest_id), None)
    if not c: raise HTTPException(404, "Contest not found")
    ev = ContestEvaluator.evaluate(c)
    return wrap_data({**c, "evaluation": ev}, source="coach_engine")


@router.get("/slates/{slate_id}")
async def slates_review(slate_id: int, user: User = Depends(get_current_user)):
    return wrap_data({"slate_id": slate_id, "contests": 3, "avg_projection_error": 5.2, "cash_rate": 66.7}, source="coach_engine")


@router.get("/performance")
async def get_performance(user: User = Depends(get_current_user)):
    tier = _tier(user)
    results = DEMO_CONTESTS
    roi = PerformanceAnalyzer.calculate_roi(results)
    cr = PerformanceAnalyzer.cash_rate(results)
    pa = PerformanceAnalyzer.projection_accuracy(results)
    resp = {"roi": roi, "cash_rate": cr, "projection_accuracy": pa}
    if not GATING[tier]["full_performance"]:
        resp["detail"] = "Upgrade to Pro Arena for full performance analysis."
    return wrap_data(resp, source="coach_engine")


@router.get("/findings")
async def get_findings(user: User = Depends(get_current_user)):
    tier = _tier(user)
    if not GATING[tier]["full_performance"]:
        raise HTTPException(403, "Full findings require Pro Arena or higher.")
    return wrap_data({
        "findings": [
            {"type": "strength", "category": "strategy", "headline": "Cash strategy well executed", "detail": "Cash entries have 66% cash rate. Continue prioritizing cash games.", "sample_size": 2, "confidence": 0.45},
            {"type": "weakness", "category": "strategy", "headline": "Aggressive strategy underperforms", "detail": "Aggressive entries cash only 0% in small sample. Review GPP approach.", "sample_size": 2, "confidence": 0.30},
        ], "sample_warning": "Small sample: 5 results. Increase to 20+ for reliable findings."
    }, source="coach_engine")


@router.get("/recommendations")
async def get_recommendations(user: User = Depends(get_current_user)):
    tier = _tier(user)
    metrics = PerformanceAnalyzer.calculate_roi(DEMO_CONTESTS)
    metrics["cash_rate"] = PerformanceAnalyzer.cash_rate(DEMO_CONTESTS)
    recs = RecommendationEngine.generate(metrics, [], DEMO_CONTESTS)
    if not GATING[tier]["full_performance"]:
        recs = recs[:2]
    return wrap_data({"recommendations": recs}, source="coach_engine")


@router.get("/strategies")
async def get_strategies(user: User = Depends(get_current_user)):
    tier = _tier(user)
    if not GATING[tier]["full_performance"]:
        raise HTTPException(403, "Strategy analysis requires Pro Arena or higher.")
    return wrap_data({"strategies": StrategyAnalyzer.analyze_by_strategy(DEMO_CONTESTS)}, source="coach_engine")


@router.get("/exposures")
async def get_exposures(user: User = Depends(get_current_user)):
    tier = _tier(user)
    if not GATING[tier]["full_performance"]:
        raise HTTPException(403, "Exposure analysis requires Pro Arena or higher.")
    return wrap_data(StrategyAnalyzer.exposure_analysis(DEMO_CONTESTS), source="coach_engine")


@router.post("/review")
async def create_review(user: User = Depends(get_current_user)):
    sid = f"session:{uuid.uuid4().hex[:12]}"
    return wrap_data({"session_id": sid, "session_type": "slate", "contest_count": 5, "created_at": datetime.now(timezone.utc).isoformat()}, source="coach_engine")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: User = Depends(get_current_user)):
    return wrap_data({"session_id": session_id, "status": "complete"}, source="coach_engine")