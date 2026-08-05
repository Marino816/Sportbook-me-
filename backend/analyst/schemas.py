"""
Typed schemas for SB-Me Analyst responses.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    risk_type: str
    label: str
    severity: float  # 0.0 - 1.0
    description: Optional[str] = None


class ConfidenceComponents(BaseModel):
    data_quality: float = 0.0
    sample_size: float = 0.0
    market_alignment: float = 0.0
    injury_clarity: float = 0.0
    recency: float = 0.0


class PlayerInsightResponse(BaseModel):
    insight_id: str
    entity_id: int
    entity_type: str = "player"
    sport: str
    league: str
    headline: str
    summary: str
    verified_facts: List[str] = []
    projection_factors: List[dict] = []
    market_factors: List[dict] = []
    injury_factors: List[dict] = []
    matchup_factors: List[dict] = []
    risk_factors: List[RiskFactor] = []
    edge_score: Optional[float] = None
    confidence_score: float
    confidence_components: ConfidenceComponents
    source_event_ids: List[str] = []
    model_name: str
    model_version: str
    data_timestamp: datetime
    stale_data_flag: bool = False
    missing_data_flags: List[str] = []


class GameInsightResponse(PlayerInsightResponse):
    entity_type: str = "game"
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    spread: Optional[float] = None
    total: Optional[float] = None


class SlateInsightResponse(BaseModel):
    insight_id: str
    slate_id: int
    sport: str
    league: str
    headline: str
    summary: str
    top_players: List[dict] = []
    top_edges: List[dict] = []
    risk_summary: List[RiskFactor] = []
    confidence_score: float
    model_version: str
    data_timestamp: datetime


class ProjectionChangeResponse(BaseModel):
    insight_id: str
    entity_id: int
    entity_type: str
    previous_projection: float
    current_projection: float
    absolute_change: float
    percentage_change: float
    triggering_events: List[str] = []
    adjustment_factors: List[str] = []
    confidence_change: float
    optimizer_refresh_recommended: bool = False
    model_version: str
    data_timestamp: datetime


class TopEdgesResponse(BaseModel):
    slate_id: int
    sport: str
    edges: List[dict]
    generated_at: datetime
    model_version: str