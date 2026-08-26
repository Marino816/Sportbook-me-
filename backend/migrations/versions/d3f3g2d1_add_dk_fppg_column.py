"""add_dk_fppg_to_dfs_players

Revision ID: d3f3g2d1
Revises: b2e2f1c0
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "d3f3g2d1"
down_revision = "b2e2f1c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "dfs_slate_players",
        sa.Column("fppg", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_column("dfs_slate_players", "fppg")