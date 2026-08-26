"""
AI Engine models for Sportsbook Me DFS AI.

Phase 7A tables:
  - ai_models
  - ai_model_versions
  - ai_predictions
  - ai_prediction_inputs
  - ai_explanations
  - ai_audit_logs
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, JSON,
)
from datetime import datetime, timezone
from models.database import Base


class AIModel(Base):
    __tablename__ = "ai_models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    sport = Column(String, index=True)          # "nba", "nfl", etc.
    model_type = Column(String)                  # "projection", "ownership", etc.
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIModelVersion(Base):
    __tablename__ = "ai_model_versions"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ai_models.id"))
    version = Column(String)                     # "1.0.0"
    parameters_json = Column(JSON, nullable=True) # training hyperparams
    training_data_range = Column(String, nullable=True)  # "2025-10-01..2026-04-01"
    metrics_json = Column(JSON, nullable=True)    # MAE, RMSE, etc.
    deployed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class AIPrediction(Base):
    __tablename__ = "ai_predictions"
    id = Column(Integer, primary_key=True, index=True)
    model_version_id = Column(Integer, ForeignKey("ai_model_versions.id"))
    entity_id = Column(Integer)                   # player_id, fighter_id
    entity_type = Column(String)                  # "player", "fighter"
    sport = Column(String)
    slate_id = Column(Integer, ForeignKey("slates.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("matchups.id"), nullable=True)
    platform = Column(String)                     # "draftkings", "fanduel"
    # Core projections
    median_projection = Column(Float)
    floor_projection = Column(Float)
    ceiling_projection = Column(Float)
    boom_probability = Column(Float, nullable=True)
    bust_probability = Column(Float, nullable=True)
    # DFS metrics
    salary = Column(Integer, nullable=True)
    value_score = Column(Float, nullable=True)
    matchup_score = Column(Float, nullable=True)
    ownership_projection = Column(Float, nullable=True)
    leverage_score = Column(Float, nullable=True)
    # Adjustments
    injury_adjustment = Column(Float, nullable=True)
    market_adjustment = Column(Float, nullable=True)
    # Metadata
    confidence_score = Column(Float)
    model_version = Column(String)                 # denormalized for fast lookup
    input_data_timestamp = Column(DateTime(timezone=True))
    missing_data_flags = Column(JSON, default=list)
    stale_data_flag = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIPredictionInput(Base):
    __tablename__ = "ai_prediction_inputs"
    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("ai_predictions.id"))
    input_type = Column(String)                   # "game_log", "injury_report", "odds"
    input_value = Column(JSON)                    # the actual data used
    source = Column(String)                       # "ball_dont_lie", "odds_api", "internal"
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIExplanation(Base):
    __tablename__ = "ai_explanations"
    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("ai_predictions.id"))
    explanation_text = Column(String)
    factors_json = Column(JSON, default=list)     # structured factors list
    model_version = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIAuditLog(Base):
    __tablename__ = "ai_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)                       # endpoint name
    endpoint = Column(String)
    input_hash = Column(String)                   # SHA256 of input (no raw data stored)
    response_hash = Column(String)
    model_version = Column(String, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    latency_ms = Column(Float)
    success = Column(Boolean, default=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIChatLog(Base):
    """Per-message usage/audit log for the customer SB ME AI chat.

    Records model, token usage, estimated cost, tools invoked, latency and
    outcome. NEVER stores API keys, provider credentials, or the system
    prompt.  Message text is intentionally NOT persisted here (only a
    usage record); conversation content belongs to assistant_messages.
    """
    __tablename__ = "ai_chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    conversation_id = Column(String, nullable=True, index=True)
    model = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)
    tools_invoked = Column(JSON, default=list)
    latency_ms = Column(Float, default=0.0)
    success = Column(Boolean, default=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
