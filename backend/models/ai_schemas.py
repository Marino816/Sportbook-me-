"""
Canonical projection schema for Sportsbook Me DFS AI.

Every projection goes through this contract regardless of sport or model.
Nullable fields reflect genuinely unavailable data — never fabricated.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectionResponse(BaseModel):
    """Canonical single-entity projection output."""

    # Identity
    entity_id: int
    entity_type: str  # "player" | "fighter"
    entity_name: str
    sport: str
    league: str

    # Event context
    event_id: Optional[int] = None
    slate_id: Optional[int] = None
    platform: str  # "draftkings" | "fanduel"

    # Timestamps
    projection_timestamp: datetime = Field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    model_name: str
    model_version: str
    input_data_timestamp: Optional[datetime] = None

    # Core projections
    median_projection: float
    floor_projection: float
    ceiling_projection: float
    boom_probability: Optional[float] = None
    bust_probability: Optional[float] = None

    # DFS metrics
    salary: Optional[int] = None
    value_score: Optional[float] = None
    matchup_score: Optional[float] = None
    ownership_projection: Optional[float] = None
    leverage_score: Optional[float] = None

    # Adjustments
    injury_adjustment: Optional[float] = None
    market_adjustment: Optional[float] = None

    # Metadata
    confidence_score: float
    explanation: str
    input_sources: List[str] = []
    missing_data_flags: List[str] = []
    stale_data_flag: bool = False


class ProjectionRequest(BaseModel):
    """Request to generate projections."""
    slate_id: int
    platform: str = "draftkings"


class PlayerExplanationRequest(BaseModel):
    """Request an explanation for a specific player."""
    player_id: int
    slate_id: int


class ModelStatusResponse(BaseModel):
    """Current active model versions."""
    models: List[dict]
    active_count: int
    data_freshness: dict  # {"last_sync": "...", "stale": bool}


class AIFeatureAccess(BaseModel):
    """User's current AI feature access tier."""
    tier: str  # "free", "pro_arena", "elite_stack"
    daily_requests_used: int
    daily_requests_limit: int
    features: List[str]  # enabled feature names
