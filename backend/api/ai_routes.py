"""
AI Engine API endpoints — Phase 7A.

Endpoints:
  GET  /api/ai/model-status        — active model versions
  GET  /api/ai/projections         — generate projections for a slate
  GET  /api/ai/players/{id}/explanation — explain a specific projection
"""

import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from models.domain import User
from models.ai_models import AIModel, AIModelVersion, AIPrediction, AIExplanation
from models.ai_schemas import (
    ProjectionRequest, ProjectionResponse,
    PlayerExplanationRequest, ModelStatusResponse,
)
from api.auth import get_current_user
from api.utils import wrap_data
from ai.projection_service import ProjectionService, log_audit_record
from ai.sport_adapter import UnsupportedSportError
from ai.nba_adapter import registered_sports

router = APIRouter(prefix="/ai", tags=["AI Engine"])


# ── Subscription gating ──────────────────────────────────────

FEATURE_GATING = {
    "free": {
        "max_projections_per_day": 5,
        "full_explanations": False,
        "advanced_metrics": False,
    },
    "pro_arena": {
        "max_projections_per_day": 500,
        "full_explanations": True,
        "advanced_metrics": True,
    },
    "elite_stack": {
        "max_projections_per_day": 10000,
        "full_explanations": True,
        "advanced_metrics": True,
    },
}

# In-memory rate tracker (per-session — production needs Redis)
_rate_tracker: dict = {}


def _get_tier(user: User) -> str:
    if not user.is_pro or not user.active_subscription_id:
        return "free"
    # Avoid lazy loading: check by subscription ID presence and is_pro
    # Elite users have is_pro=True (set during webhook sync)
    # Plan name check must be done via eager load or direct query in calling context
    try:
        sub = getattr(user, "subscription", None)
        if sub and getattr(sub, "plan_name", "") == "Elite Stack":
            return "elite_stack"
    except Exception:
        pass
    return "pro_arena"


def _check_rate(user: User) -> tuple[bool, int, int]:
    tier = _get_tier(user)
    limits = FEATURE_GATING[tier]
    key = f"ai:{user.id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    count = _rate_tracker.get(key, 0)
    return count < limits["max_projections_per_day"], count, limits["max_projections_per_day"]


# ── Endpoints ────────────────────────────────────────────────

@router.get("/model-status")
async def model_status(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """Return active model versions and supported sports."""
    start = time.time()

    result = await db.execute(
        select(AIModelVersion).where(AIModelVersion.is_active == True)
    )
    versions = result.scalars().all()

    response = {
        "models": [{
            "model": "nba_baseline_v1",
            "version": "7a.0.1",
            "sport": "nba",
            "type": "projection",
            "deployed_at": "2026-08-04",
        }],
        "active_count": 1,
        "data_freshness": {"last_sync": datetime.now(timezone.utc).isoformat(), "stale": False},
        "supported_sports": registered_sports(),
    }

    await log_audit_record(
        db=db, user_id=user.id if user else None,
        endpoint="/api/ai/model-status", action="model_status",
        request_body={}, response_body=response,
        model_version=None, latency_ms=(time.time() - start) * 1000,
        success=True,
    )
    return wrap_data(response, source="ai_engine")


@router.get("/projections")
async def get_projections(
    slate_id: int,
    platform: str = "draftkings",
    sport: str = "nba",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate AI projections for a slate. Subscription-gated."""
    start = time.time()

    # Rate limiting
    allowed, count, limit = _check_rate(user)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Daily projection limit ({limit}) reached. Upgrade for more.")

    try:
        service = ProjectionService(db, sport=sport, platform=platform)
        projections = await service.generate_for_slate(slate_id)
    except UnsupportedSportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Increment rate counter
    key = f"ai:{user.id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    _rate_tracker[key] = _rate_tracker.get(key, 0) + 1

    response = {
        "slate_id": slate_id,
        "platform": platform,
        "sport": sport,
        "model_version": "7a.0.1",
        "projections": projections,
        "rate_limit": {"used": _rate_tracker[key], "limit": limit},
    }

    await log_audit_record(
        db=db, user_id=user.id,
        endpoint="/api/ai/projections", action="projections",
        request_body={"slate_id": slate_id, "platform": platform, "sport": sport},
        response_body={"count": len(projections)},
        model_version="7a.0.1", latency_ms=(time.time() - start) * 1000,
        success=True,
    )
    return wrap_data(response, source="ai_engine")


@router.get("/players/{player_id}/explanation")
async def get_player_explanation(
    player_id: int,
    slate_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get an AI explanation for a specific player's projection. Pro+ only."""
    start = time.time()
    tier = _get_tier(user)

    if not FEATURE_GATING[tier]["full_explanations"]:
        raise HTTPException(status_code=403, detail="Full explanations require Pro Arena or higher.")

    # Check for existing AI prediction
    result = await db.execute(
        select(AIPrediction).where(
            AIPrediction.entity_id == player_id,
            AIPrediction.slate_id == slate_id,
        ).order_by(AIPrediction.created_at.desc()).limit(1)
    )
    prediction = result.scalars().first()

    if not prediction:
        # Generate on-the-fly
        try:
            service = ProjectionService(db, sport="nba", platform="draftkings")
            projections = await service.generate_for_slate(slate_id)
            match = [p for p in projections if p["entity_id"] == player_id]
            if not match:
                raise HTTPException(status_code=404, detail="No projection found for this player on this slate.")
            proj = match[0]
        except UnsupportedSportError as e:
            raise HTTPException(status_code=400, detail=str(e))
        response = {
            "player_id": player_id,
            "explanation": proj["explanation"],
            "confidence": proj["confidence_score"],
            "model_version": "7a.0.1",
        }
    else:
        response = {
            "player_id": player_id,
            "explanation": f"Median: {prediction.median_projection:.1f}, Floor: {prediction.floor_projection:.1f}, Ceiling: {prediction.ceiling_projection:.1f}",
            "confidence": prediction.confidence_score,
            "model_version": prediction.model_version,
        }

    await log_audit_record(
        db=db, user_id=user.id,
        endpoint="/api/ai/players/explanation", action="explanation",
        request_body={"player_id": player_id, "slate_id": slate_id},
        response_body={"player_id": player_id},
        model_version="7a.0.1", latency_ms=(time.time() - start) * 1000,
        success=True,
    )
    return wrap_data(response, source="ai_engine")
