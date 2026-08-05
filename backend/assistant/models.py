"""
Assistant database models.

Tables:
  - assistant_conversations — per-user conversation sessions
  - assistant_messages       — individual messages in a conversation
  - assistant_preferences    — user-level assistant settings
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from datetime import datetime, timezone
from models.database import Base


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    strategy_mode = Column(String, default="balanced")
    sport = Column(String, default="nba")
    platform = Column(String, default="draftkings")
    slate_id = Column(Integer, nullable=True)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("assistant_conversations.conversation_id"), index=True)
    role = Column(String)  # user, assistant
    content = Column(String)
    intent = Column(String, nullable=True)
    modules_consulted = Column(JSON, default=list)
    tool_calls = Column(JSON, default=list)
    evidence = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    data_freshness = Column(String, nullable=True)
    strategy_mode = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AssistantPreference(Base):
    __tablename__ = "assistant_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    default_sport = Column(String, default="nba")
    default_platform = Column(String, default="draftkings")
    preferred_strategy = Column(String, default="balanced")
    favorite_teams = Column(JSON, default=list)
    favorite_players = Column(JSON, default=list)
    locked_players = Column(JSON, default=list)
    excluded_players = Column(JSON, default=list)
    contest_type = Column(String, default="gpp")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))