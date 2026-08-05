"""create_mission_control_tables

Revision ID: 6da32956dfb8
Revises: 703b0229f207
Create Date: 2026-08-04
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "6da32956dfb8"
down_revision: Union[str, Sequence[str], None] = "703b0229f207"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("mission_control_widgets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("widget_id", sa.String, unique=True, index=True),
        sa.Column("widget_type", sa.String),
        sa.Column("title", sa.String),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("subscription_required", sa.String, server_default="free"),
        sa.Column("is_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("mission_control_preferences",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True),
        sa.Column("favorite_sport", sa.String, server_default="nba"),
        sa.Column("favorite_platform", sa.String, server_default="draftkings"),
        sa.Column("favorite_contest_type", sa.String, nullable=True),
        sa.Column("widget_layout", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("hidden_widgets", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("default_view", sa.String, server_default="briefing"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("mission_control_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("snapshot_id", sa.String, unique=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("widget_state", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("briefing_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for t in ["mission_control_snapshots", "mission_control_preferences", "mission_control_widgets"]:
        op.drop_table(t)