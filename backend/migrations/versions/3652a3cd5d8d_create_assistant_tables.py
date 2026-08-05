"""create_assistant_tables

Revision ID: 3652a3cd5d8d
Revises: 6da32956dfb8
Create Date: 2026-08-04
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "3652a3cd5d8d"
down_revision: Union[str, Sequence[str], None] = "6da32956dfb8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, cols in [
        ("assistant_conversations", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("conversation_id", sa.String, unique=True, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("strategy_mode", sa.String, server_default="balanced"),
            sa.Column("sport", sa.String, server_default="nba"),
            sa.Column("platform", sa.String, server_default="draftkings"),
            sa.Column("slate_id", sa.Integer, nullable=True),
            sa.Column("message_count", sa.Integer, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("assistant_messages", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("conversation_id", sa.String, sa.ForeignKey("assistant_conversations.conversation_id"), index=True),
            sa.Column("role", sa.String),
            sa.Column("content", sa.String),
            sa.Column("intent", sa.String, nullable=True),
            sa.Column("modules_consulted", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("tool_calls", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("evidence", sa.JSON, nullable=True),
            sa.Column("confidence", sa.Float, nullable=True),
            sa.Column("data_freshness", sa.String, nullable=True),
            sa.Column("strategy_mode", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("assistant_preferences", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True),
            sa.Column("default_sport", sa.String, server_default="nba"),
            sa.Column("default_platform", sa.String, server_default="draftkings"),
            sa.Column("preferred_strategy", sa.String, server_default="balanced"),
            sa.Column("favorite_teams", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("favorite_players", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("locked_players", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("excluded_players", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("contest_type", sa.String, server_default="gpp"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
    ]:
        op.create_table(name, *cols)


def downgrade() -> None:
    for t in ["assistant_preferences", "assistant_messages", "assistant_conversations"]:
        op.drop_table(t)