"""add_ai_chat_logs

Revision ID: b2e2f1c0
Revises: a1b2c3d4_market_snapshots
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "b2e2f1c0"
down_revision = "a1b2c3d4_market_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_chat_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("conversation_id", sa.String(), nullable=True, index=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), default=0),
        sa.Column("completion_tokens", sa.Integer(), default=0),
        sa.Column("total_tokens", sa.Integer(), default=0),
        sa.Column("cost_estimate", sa.Float(), default=0.0),
        sa.Column("tools_invoked", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), default=0.0),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("ai_chat_logs")
