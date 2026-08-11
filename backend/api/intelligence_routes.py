"""SB ME Intelligence API — normalized market context for authenticated users."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from api.auth import get_current_user
from models.domain import User
from api.utils import wrap_data
from intelligence.engine import (
    PlayerIntelligence, GameIntelligence, SignalComputer,
    GameEnvironmentSignal, PlayerSignal, DataSourceStatus, DFSDataMode,
    american_to_implied_probability, probability_edge,
)
from intelligence.engine import SPORT_ENV_THRESHOLDS

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/slate/{slate_id}")
async def get_slate_intelligence(
    slate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return normalized SB ME intelligence for a slate.

    Combines SportsDataIO DFS data (salaries, projections) with
    SportsGameOdds market context (fantasyScore, props, game totals).

    Provider statuses are separated:
      dfs_data_mode = TRIAL_SCRAMBLED | LIVE_PRODUCTION | UNAVAILABLE
      market_context_status = FRESH | STALE | UNAVAILABLE
    """
    # This is a stub — production implementation loads real data
    # from SportsGameOdds cache + SportsDataIO projections.
    return wrap_data({
        "slate_id": slate_id,
        "provider": {
            "dfs": "SportsDataIO",
            "dfs_data_mode": DFSDataMode.TRIAL_SCRAMBLED.value,
            "market": "SportsGameOdds",
            "market_context_status": DataSourceStatus.UNAVAILABLE.value,
        },
        "environment_config": {
            sport: thresholds for sport, thresholds in SPORT_ENV_THRESHOLDS.items()
        },
        "games": [],
        "players": [],
        "warnings": ["SGO integration pending production data load"],
    })


@router.get("/health")
async def intelligence_health():
    """Provider status summary."""
    return {
        "odds_math": {
            "american_to_implied_examples": {
                "+150": american_to_implied_probability(150),
                "-200": american_to_implied_probability(-200),
                "+100": american_to_implied_probability(100),
            },
            "probability_edge_example": probability_edge(-110, -105),
        },
        "sport_configs": list(SPORT_ENV_THRESHOLDS.keys()),
    }