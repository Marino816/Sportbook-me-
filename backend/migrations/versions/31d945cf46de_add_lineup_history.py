"""add_lineup_history

Revision ID: 31d945cf46de
Revises: c35715bf960d
Create Date: 2026-08-11
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "31d945cf46de"
down_revision: Union[str, None] = "c35715bf960d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lineup_history",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("sport", sa.String),
        sa.Column("platform", sa.String),
        sa.Column("slate_id", sa.Integer),
        sa.Column("strategy", sa.String),
        sa.Column("lineup_count", sa.Integer, default=1),
        sa.Column("player_count", sa.Integer),
        sa.Column("total_salary", sa.Integer),
        sa.Column("projected_score", sa.Float),
        sa.Column("data_mode", sa.String, default="TRIAL_SCRAMBLED"),
        sa.Column("lineups_json", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("lineup_history")