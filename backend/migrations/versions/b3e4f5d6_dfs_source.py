"""add dfs_source to lineup_history

Revision ID: b3e4f5d6_dfs_source
Revises: 31d945cf46de
Create Date: 2026-08-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b3e4f5d6_dfs_source"
down_revision: Union[str, None] = "31d945cf46de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lineup_history",
        sa.Column("dfs_source", sa.String(), nullable=True, server_default="native"),
    )
    # Backfill existing rows
    op.execute("UPDATE lineup_history SET dfs_source = 'native' WHERE dfs_source IS NULL")


def downgrade() -> None:
    op.drop_column("lineup_history", "dfs_source")