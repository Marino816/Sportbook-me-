from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.models.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    is_pro = Column(Boolean, default=False)
    stripe_customer_id = Column(String, nullable=True)
    active_subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    subscription = relationship("Subscription", foreign_keys=[active_subscription_id])

class Slate(Base):
    """A collection of games on a specific day for DFS."""
    __tablename__ = "slates"
    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String) # 'NBA', 'MLB'
    site = Column(String) # 'DraftKings', 'FanDuel'
    date = Column(DateTime)
    is_main_slate = Column(Boolean, default=True)

class Player(Base):
    """Canonical player entity."""
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String)
    name = Column(String)
    team = Column(String)
    active = Column(Boolean, default=True)

class GameLog(Base):
    """Historical performance records for ML training."""
    __tablename__ = "game_logs"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    date = Column(DateTime)
    fantasy_points = Column(Float)
    minutes = Column(Float, nullable=True)
    stats_json = Column(JSON) # Store raw stats for flexible feature engineering

class Projection(Base):
    """ML and baseline projections for a player on a given slate."""
    __tablename__ = "projections"
    id = Column(Integer, primary_key=True, index=True)
    slate_id = Column(Integer, ForeignKey("slates.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    salary = Column(Integer)
    roster_position = Column(String) # e.g. "PG/SG"
    projected_fp = Column(Float)
    ceiling = Column(Float)
    floor = Column(Float)
    ownership = Column(Float)
    leverage = Column(Float)
    value = Column(Float)
    is_locked = Column(Boolean, default=False)

    player = relationship("Player")
    slate = relationship("Slate")

class Lineup(Base):
    """Saved optimized lineups."""
    __tablename__ = "lineups"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    slate_id = Column(Integer, ForeignKey("slates.id"))
    projected_score = Column(Float)
    total_salary = Column(Integer)
    players_json = Column(JSON) # e.g. [{"id": 12, "pos": "PG"}, ...]
    actual_score = Column(Float, nullable=True) # For ROI calculation
    won_amount = Column(Float, default=0.0)
    entry_fee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Subscription(Base):
    """SaaS billing and plan tracking."""
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    plan_name = Column(String) # 'Starter', 'Pro Arena', 'Elite Stack'
    status = Column(String) # 'active', 'trialing', 'canceled', 'past_due'
    mrr_value = Column(Float, default=49.99)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Matchup(Base):
    """Real-world sports matches for the Betting Lobby."""
    __tablename__ = "matchups"
    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String)
    league = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    game_time = Column(DateTime)
    status = Column(String, default="scheduled") # 'scheduled', 'live', 'finished'
    score_json = Column(JSON, nullable=True) # e.g. {"home": 28, "away": 24, "period": "Q4"}
    odds_json = Column(JSON, nullable=True) # e.g. {"spread": -1.5, "total": 54.5, "ml": -145}

class SystemStatus(Base):
    """Platform health and data source monitoring."""
    __tablename__ = "system_status"
    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String, unique=True) # 'DFS_PROJECTIONS', 'SPORTS_ODDS', 'NBA_API'
    is_healthy = Column(Boolean, default=True)
    last_sync_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_sync_result = Column(String) # 'Success', 'Timeout', 'Rate-Limited', etc.
    data_source_mode = Column(String, default="live") # 'live', 'cached', 'demo'

class StripeEvent(Base):
    """Event ledger for Stripe webhooks to ensure idempotency."""
    __tablename__ = "stripe_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
