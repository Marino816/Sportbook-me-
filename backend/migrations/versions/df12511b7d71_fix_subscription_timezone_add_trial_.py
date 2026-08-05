"""fix_subscription_timezone_add_trial_revenue

Revision ID: df12511b7d71
Revises: 7a35791ef604
Create Date: 2026-08-04

1. Fix subscriptions.current_period_end: TIMESTAMP → TIMESTAMPTZ
2. Add subscriptions.trial_end (TIMESTAMPTZ, nullable)
3. Create revenue_logs table for payment tracking
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "df12511b7d71"
down_revision: Union[str, Sequence[str], None] = "7a35791ef604"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN current_period_end TYPE TIMESTAMP WITH TIME ZONE"
    )
    op.add_column("subscriptions", sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "revenue_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("subscriptions.id")),
        sa.Column("amount", sa.Float),
        sa.Column("currency", sa.String, default="usd"),
        sa.Column("stripe_invoice_id", sa.String, unique=True, index=True),
        sa.Column("status", sa.String, default="paid"),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("revenue_logs")
    op.drop_column("subscriptions", "trial_end")
    op.execute(
        "ALTER TABLE subscriptions ALTER COLUMN current_period_end TYPE TIMESTAMP WITHOUT TIME ZONE"
    )