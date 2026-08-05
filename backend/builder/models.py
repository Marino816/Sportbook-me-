"""
Builder database models for SB-Me Builder.

Tables:
  - builder_runs            — optimization run metadata
  - builder_lineups         — individual lineups
  - builder_portfolios      — multi-lineup portfolio summaries
  - builder_exposure_rules  — per-run exposure constraints
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, JSON,
)
from datetime import datetime, timezone
from models.database import Base


class BuilderRun(Base):
    __tablename__ = "builder_runs"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    slate_id = Column(Integer)
    sport = Column(String, default="nba")
    platform = Column(String, default="draftkings")
    contest_type = Column(String, nullable=True)
    strategy_profile = Column(String, default="balanced")
    lineup_count = Column(Integer, default=1)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    locked_player_ids = Column(JSON, default=list)
    excluded_player_ids = Column(JSON, default=list)
    exposure_rules = Column(JSON, default=dict)
    stack_rules = Column(JSON, default=dict)
    uniqueness_count = Column(Integer, default=2)
    randomness = Column(Float, default=0.0)
    generated_count = Column(Integer, default=0)
    solver_status = Column(String, default="pending")
    runtime_ms = Column(Float, nullable=True)
    portfolio_metrics = Column(JSON, nullable=True)
    scout_event_ids = Column(JSON, default=list)
    model_name = Column(String)
    model_version = Column(String)
    projection_timestamp = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BuilderLineup(Base):
    __tablename__ = "builder_lineups"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey("builder_runs.run_id"), index=True)
    lineup_index = Column(Integer)
    projected_score = Column(Float)
    ceiling_score = Column(Float, nullable=True)
    total_salary = Column(Integer)
    remaining_salary = Column(Integer, nullable=True)
    ownership_estimate = Column(Float, nullable=True)
    leverage_estimate = Column(Float, nullable=True)
    correlation_summary = Column(String, nullable=True)
    edge_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    players_json = Column(JSON)
    strategy_profile = Column(String)
    explanation = Column(JSON, default=dict)
    is_stale = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BuilderPortfolio(Base):
    __tablename__ = "builder_portfolios"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, unique=True, index=True)
    run_id = Column(String, ForeignKey("builder_runs.run_id"))
    lineup_count = Column(Integer)
    avg_projection = Column(Float)
    avg_ceiling = Column(Float, nullable=True)
    avg_salary = Column(Float)
    avg_ownership = Column(Float, nullable=True)
    avg_leverage = Column(Float, nullable=True)
    exposure_json = Column(JSON, default=dict)
    diversity_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BuilderExposureRule(Base):
    __tablename__ = "builder_exposure_rules"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey("builder_runs.run_id"), index=True)
    entity_type = Column(String)  # "player", "team", "game"
    entity_id = Column(Integer)
    entity_name = Column(String, nullable=True)
    min_exposure = Column(Float, default=0.0)
    max_exposure = Column(Float, default=1.0)
    actual_exposure = Column(Float, nullable=True)
    is_satisfied = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))