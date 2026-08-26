"""DFS Slate persistence models for SB ME native contest data layer."""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from models.database import Base


class DFSPlayer(Base):
    """Individual player in a DFS contest slate — native DK/FD data."""
    __tablename__ = "dfs_slate_players"

    id = Column(Integer, primary_key=True, index=True)
    slate_id = Column(Integer, ForeignKey("dfs_slates.id"), nullable=False, index=True)

    # Provider fields
    provider_player_id = Column(String, index=True)
    player_name = Column(String)
    team = Column(String)
    opponent = Column(String, nullable=True)
    position = Column(String)
    eligible_positions = Column(JSON, default=list)
    salary = Column(Integer, default=0)
    fppg = Column(Float, nullable=True)             # DK FPPG from Blue Collar DFS
    game_info = Column(String, nullable=True)

    # SB ME reconciliation
    sbme_player_id = Column(String, nullable=True)
    sbme_team_id = Column(String, nullable=True)
    mapping_confidence = Column(Float, default=0.0)
    mapping_status = Column(String, default="UNMATCHED")  # MATCHED | REVIEW_REQUIRED | UNMATCHED

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    slate = relationship("DFSSlate", back_populates="players")


class DFSSlate(Base):
    """DFS contest slate — uploaded by admin, published for customers."""
    __tablename__ = "dfs_slates"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True)            # "draftkings" | "fanduel"
    sport = Column(String, index=True)               # "MLB" | "NFL" | "NBA" | "NHL"
    external_slate_id = Column(String, nullable=True) # provider's slate ID
    slate_name = Column(String)
    start_time = Column(DateTime(timezone=True), nullable=True)

    # Admin workflow
    uploaded_by = Column(Integer, nullable=True)      # user_id
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="DRAFT")           # DRAFT | REVIEW | PUBLISHED | ARCHIVED
    version = Column(Integer, default=1)
    data_source = Column(String, default="native")     # "native" | "sportsdataio"

    # Counts
    player_count = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    unmatched_count = Column(Integer, default=0)

    # Reconciliation metadata
    reconciliation_report = Column(JSON, nullable=True)

    players = relationship("DFSPlayer", back_populates="slate", cascade="all, delete-orphan")