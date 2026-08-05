"""
Mission Control database models.

Tables:
  - mission_control_preferences — user widget layout + favorites
  - mission_control_widgets     — registered widget definitions
  - mission_control_snapshots   — periodic dashboard state snapshots
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from datetime import datetime, timezone
from models.database import Base


class MCPreference(Base):
    __tablename__ = "mission_control_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    favorite_sport = Column(String, default="nba")
    favorite_platform = Column(String, default="draftkings")
    favorite_contest_type = Column(String, nullable=True)
    widget_layout = Column(JSON, default=list)
    hidden_widgets = Column(JSON, default=list)
    default_view = Column(String, default="briefing")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MCWidget(Base):
    __tablename__ = "mission_control_widgets"
    id = Column(Integer, primary_key=True, index=True)
    widget_id = Column(String, unique=True, index=True)
    widget_type = Column(String)
    title = Column(String)
    description = Column(String, nullable=True)
    subscription_required = Column(String, default="free")
    is_enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MCSnapshot(Base):
    __tablename__ = "mission_control_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    widget_state = Column(JSON, default=dict)
    briefing_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))