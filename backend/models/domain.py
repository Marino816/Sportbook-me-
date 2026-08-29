from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from models.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="user")  # "user" | "admin"
    is_pro = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_beta = Column(Boolean, default=False)  # Closed beta access flag
    stripe_customer_id = Column(String, nullable=True)
    active_subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    subscription = relationship("Subscription", foreign_keys=[active_subscription_id])
    oauth_identities = relationship("UserOAuthIdentity", back_populates="user")


class UserOAuthIdentity(Base):
    """Durable Google / Apple subject binding. One user may link both providers."""
    __tablename__ = "user_oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    provider_subject = Column(String, nullable=False)
    provider_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="oauth_identities")

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
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    source = Column(String, default="seed", nullable=True)  # "seed", "api", "model_v7"

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Subscription(Base):
    """SaaS billing and plan tracking."""
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    plan_name = Column(String) # 'Starter', 'Pro Arena', 'Elite Stack'
    status = Column(String) # 'active', 'trialing', 'canceled', 'past_due'
    mrr_value = Column(Float, default=49.99)
    current_period_end = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    last_sync_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_sync_result = Column(String) # 'Success', 'Timeout', 'Rate-Limited', etc.
    data_source_mode = Column(String, default="TRIAL_SCRAMBLED")

class LineupHistory(Base):
    """Persistent lineup history for user sessions."""
    __tablename__ = "lineup_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sport = Column(String)
    platform = Column(String)
    slate_id = Column(Integer)
    strategy = Column(String)
    lineup_count = Column(Integer, default=1)
    player_count = Column(Integer)
    total_salary = Column(Integer)
    projected_score = Column(Float)
    data_mode = Column(String, default="native")
    lineups_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class StripeEvent(Base):
    """Event ledger for Stripe webhooks to ensure idempotency."""
    __tablename__ = "stripe_events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RevenueLog(Base):
    """Revenue tracking from successful Stripe payments."""
    __tablename__ = "revenue_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Float)
    currency = Column(String, default="usd")
    stripe_invoice_id = Column(String, unique=True, index=True)
    status = Column(String, default="paid")
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
