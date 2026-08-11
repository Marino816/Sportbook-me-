"""add_dfs_slates

Revision ID: 1fcda0c11f14
Revises: 31d945cf46de
Create Date: 2026-08-11
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "1fcda0c11f14"
down_revision: Union[str, Sequence[str], None] = "31d945cf46de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "dfs_slates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("platform", sa.String, index=True),
        sa.Column("sport", sa.String, index=True),
        sa.Column("external_slate_id", sa.String, nullable=True),
        sa.Column("slate_name", sa.String),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by", sa.Integer, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String, default="DRAFT"),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("data_source", sa.String, default="native"),
        sa.Column("player_count", sa.Integer, default=0),
        sa.Column("matched_count", sa.Integer, default=0),
        sa.Column("review_count", sa.Integer, default=0),
        sa.Column("unmatched_count", sa.Integer, default=0),
        sa.Column("reconciliation_report", sa.JSON, nullable=True),
    )

    op.create_table(
        "dfs_slate_players",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slate_id", sa.Integer, sa.ForeignKey("dfs_slates.id"), nullable=False, index=True),
        sa.Column("provider_player_id", sa.String, index=True),
        sa.Column("player_name", sa.String),
        sa.Column("team", sa.String),
        sa.Column("opponent", sa.String, nullable=True),
        sa.Column("position", sa.String),
        sa.Column("eligible_positions", sa.JSON, default=list),
        sa.Column("salary", sa.Integer, default=0),
        sa.Column("game_info", sa.String, nullable=True),
        sa.Column("sbme_player_id", sa.String, nullable=True),
        sa.Column("sbme_team_id", sa.String, nullable=True),
        sa.Column("mapping_confidence", sa.Float, default=0.0),
        sa.Column("mapping_status", sa.String, default="UNMATCHED"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("dfs_slate_players")
    op.drop_table("dfs_slates")