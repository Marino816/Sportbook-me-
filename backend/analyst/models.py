"""
Analyst database models for SB-Me Analyst.

Tables:
  - analyst_insights  — structured analysis output
  - analyst_factors   — decomposition of insight components
  - analyst_risks     — identified risk factors per insight
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, JSON,
)
from datetime import datetime, timezone
from models.database import Base


class AnalystInsight(Base):
    __tablename__ = "analyst_insights"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String, unique=True, index=True)
    insight_type = Column(String, index=True)
    sport = Column(String, default="nba")
    league = Column(String, default="NBA")
    entity_id = Column(Integer, nullable=True)
    entity_type = Column(String, nullable=True)
    event_id = Column(Integer, nullable=True)
    slate_id = Column(Integer, nullable=True)
    platform = Column(String, default="draftkings")
    headline = Column(String)
    summary = Column(String)
    verified_facts = Column(JSON, default=list)
    projection_factors = Column(JSON, default=list)
    market_factors = Column(JSON, default=list)
    injury_factors = Column(JSON, default=list)
    matchup_factors = Column(JSON, default=list)
    risk_factors = Column(JSON, default=list)
    edge_score = Column(Float, nullable=True)
    confidence_score = Column(Float)
    confidence_components = Column(JSON, default=dict)
    source_event_ids = Column(JSON, default=list)
    model_name = Column(String)
    model_version = Column(String)
    data_timestamp = Column(DateTime(timezone=True))
    stale_data_flag = Column(Boolean, default=False)
    missing_data_flags = Column(JSON, default=list)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AnalystFactor(Base):
    __tablename__ = "analyst_factors"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String, ForeignKey("analyst_insights.insight_id"), index=True)
    factor_type = Column(String)           # projection, matchup, injury, market, risk, edge
    factor_name = Column(String)
    factor_value = Column(Float, nullable=True)
    factor_label = Column(String, nullable=True)
    weight = Column(Float, default=1.0)
    direction = Column(String, default="neutral")  # positive, negative, neutral
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AnalystRisk(Base):
    __tablename__ = "analyst_risks"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String, ForeignKey("analyst_insights.insight_id"), index=True)
    risk_type = Column(String)              # blowout, minutes, injury, etc.
    risk_label = Column(String)
    severity = Column(Float)                # 0.0 - 1.0
    description = Column(String, nullable=True)
    is_mitigated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))