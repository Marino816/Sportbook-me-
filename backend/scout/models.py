"""
Scout database models.

Tables:
  - scout_providers  — registered data provider configurations
  - scout_events     — detected events with metadata
  - scout_alerts     — user alert configurations
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, JSON, Enum as SAEnum,
)
from datetime import datetime, timezone
from models.database import Base
import enum


class ScoutEventSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ScoutEventType(str, enum.Enum):
    INJURY_UPDATE = "injury_update"
    LINEUP_CONFIRMATION = "lineup_confirmation"
    STARTING_CHANGE = "starting_change"
    WEATHER_CHANGE = "weather_change"
    ODDS_MOVEMENT = "odds_movement"
    SALARY_CHANGE = "salary_change"
    GAME_POSTPONEMENT = "game_postponement"
    PROJECTION_INVALIDATION = "projection_invalidation"
    MANUAL_REFRESH = "manual_refresh"


class ScoutProvider(Base):
    """Registered data provider configuration."""
    __tablename__ = "scout_providers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String)              # injury, lineups, odds, etc.
    sport = Column(String, default="nba")
    is_enabled = Column(Boolean, default=True)
    is_healthy = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True), nullable=True)
    last_sync_result = Column(String, nullable=True)
    last_error = Column(String, nullable=True)
    error_count = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    data_source_mode = Column(String, default="demo")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ScoutEvent(Base):
    """Detected data-change events."""
    __tablename__ = "scout_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    sport = Column(String, default="nba")
    league = Column(String, default="NBA")
    severity = Column(String, default="info")
    source = Column(String)
    title = Column(String)
    description = Column(String, nullable=True)
    affected_entities = Column(JSON, default=list)  # [{"type":"player","id":123},...]
    refresh_required = Column(Boolean, default=False)
    refresh_completed = Column(Boolean, default=False)
    metadata_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScoutAlert(Base):
    """User alert configuration."""
    __tablename__ = "scout_alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    alert_type = Column(String)            # event type filter
    sport = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)  # specific player/team
    severity_min = Column(String, default="warning")
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
