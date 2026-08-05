"""create_scout_tables

Revision ID: f7f78e663688
Revises: d5835ac224eb
Create Date: 2026-08-04

Creates Scout service tables:
  scout_providers, scout_events, scout_alerts
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7f78e663688"
down_revision: Union[str, Sequence[str], None] = "d5835ac224eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scout_providers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, unique=True, index=True),
        sa.Column("category", sa.String),
        sa.Column("sport", sa.String, server_default="nba"),
        sa.Column("is_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_healthy", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_result", sa.String, nullable=True),
        sa.Column("last_error", sa.String, nullable=True),
        sa.Column("error_count", sa.Integer, server_default="0"),
        sa.Column("total_requests", sa.Integer, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float, nullable=True),
        sa.Column("data_source_mode", sa.String, server_default="demo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "scout_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("event_id", sa.String, unique=True, index=True),
        sa.Column("event_type", sa.String),
        sa.Column("sport", sa.String, server_default="nba"),
        sa.Column("league", sa.String, server_default="NBA"),
        sa.Column("severity", sa.String, server_default="info"),
        sa.Column("source", sa.String),
        sa.Column("title", sa.String),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("affected_entities", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("refresh_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("refresh_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "scout_alerts",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("alert_type", sa.String),
        sa.Column("sport", sa.String, nullable=True),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("severity_min", sa.String, server_default="warning"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("scout_alerts")
    op.drop_table("scout_events")
    op.drop_table("scout_providers")
