"""make_revenue_log_subscription_id_nullable

Revision ID: daf10664307c
Revises: 3652a3cd5d8d
Create Date: 2026-08-05

Allow RevenueLog rows when subscription_id is not yet linked.
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "daf10664307c"
down_revision: Union[str, None] = "3652a3cd5d8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("revenue_logs", "subscription_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("revenue_logs", "period_start", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("revenue_logs", "period_end", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade() -> None:
    op.alter_column("revenue_logs", "period_end", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("revenue_logs", "period_start", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("revenue_logs", "subscription_id", existing_type=sa.Integer(), nullable=False)