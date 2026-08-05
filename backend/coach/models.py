"""
Coach database models for SB-Me Coach.

Tables:
  - contest_results  — imported contest outcomes
  - lineup_results   — individual lineup performance
  - coach_sessions   — analysis session metadata
  - coach_metrics    — computed performance metrics
  - coach_findings   — structured findings per session
  - coach_recommendations — actionable recommendations
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from datetime import datetime, timezone
from models.database import Base


class ContestResult(Base):
    __tablename__ = "contest_results"
    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    platform = Column(String)
    sport = Column(String, default="nba")
    league = Column(String, default="NBA")
    slate_id = Column(Integer, nullable=True)
    contest_type = Column(String, nullable=True)
    contest_name = Column(String, nullable=True)
    entry_fee = Column(Float, nullable=True)
    entry_count = Column(Integer, nullable=True)
    finishing_position = Column(Integer, nullable=True)
    payout = Column(Float, nullable=True)
    submitted_lineup_id = Column(String, nullable=True)
    final_lineup_score = Column(Float, nullable=True)
    cash_line = Column(Float, nullable=True)
    winning_score = Column(Float, nullable=True)
    ownership_data_available = Column(Boolean, default=False)
    result_timestamp = Column(DateTime(timezone=True))
    data_source = Column(String, default="manual_import")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LineupResult(Base):
    __tablename__ = "lineup_results"
    id = Column(Integer, primary_key=True, index=True)
    lineup_id = Column(String, index=True)
    contest_id = Column(String, ForeignKey("contest_results.contest_id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    projected_score = Column(Float, nullable=True)
    projected_ceiling = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    projection_error = Column(Float, nullable=True)
    percentile_finish = Column(Float, nullable=True)
    salary_used = Column(Integer, nullable=True)
    ownership_sum = Column(Float, nullable=True)
    leverage_score = Column(Float, nullable=True)
    strategy_profile = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    stack_summary = Column(JSON, nullable=True)
    scout_events_after_lock = Column(JSON, default=list)
    stale_at_lock = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CoachSession(Base):
    __tablename__ = "coach_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_type = Column(String)  # contest, slate, daterange, sport, platform
    entity_ref = Column(String, nullable=True)  # slate_id, sport, platform, etc.
    contest_count = Column(Integer, default=0)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CoachMetric(Base):
    __tablename__ = "coach_metrics"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("coach_sessions.session_id"), index=True)
    metric_name = Column(String)
    metric_value = Column(Float, nullable=True)
    metric_label = Column(String, nullable=True)  # human-readable
    sample_size = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CoachFinding(Base):
    __tablename__ = "coach_findings"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("coach_sessions.session_id"), index=True)
    finding_type = Column(String)  # strength, weakness, tendency
    category = Column(String)      # strategy, sport, platform, exposure, etc.
    headline = Column(String)
    detail = Column(String)
    supporting_metric = Column(Float, nullable=True)
    sample_size = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    missing_data_warning = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CoachRecommendation(Base):
    __tablename__ = "coach_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("coach_sessions.session_id"), index=True)
    recommendation = Column(String)
    rationale = Column(String)
    linked_finding_id = Column(Integer, nullable=True)
    priority = Column(String, default="medium")  # high, medium, low
    confidence = Column(Float, default=0.0)
    sample_size = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))