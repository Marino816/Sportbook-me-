"""Market snapshots and tracked markets — SGO v1.1

Revision ID: a1b2c3d4_market_snapshots
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "a1b2c3d4_market_snapshots"
down_revision = "1fcda0c11f14"  # add_dfs_slates
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("event_id", sa.String(), nullable=False, index=True),
        sa.Column("odd_id", sa.String(), nullable=True, index=True),
        sa.Column("market_type", sa.String(), nullable=False),
        sa.Column("period", sa.String(), default="FULL_GAME"),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("stat_id", sa.String(), nullable=True),
        sa.Column("selection", sa.String(), nullable=True),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("bookmaker", sa.String(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),  # American odds
        sa.Column("opening_line", sa.Float(), nullable=True),
        sa.Column("opening_price", sa.Integer(), nullable=True),
        sa.Column("fair_odds", sa.Float(), nullable=True),
        sa.Column("snapshot_data", JSONB(), nullable=True),  # full normalized payload
        sa.Column("captured_at", TIMESTAMP(timezone=True), nullable=False, index=True),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "tracked_markets",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("event_id", sa.String(), nullable=False, index=True),
        sa.Column("odd_id", sa.String(), nullable=False),
        sa.Column("bookmaker", sa.String(), nullable=False),
        sa.Column("market_type", sa.String(), nullable=False),
        sa.Column("stat_id", sa.String(), nullable=True),
        sa.Column("selection", sa.String(), nullable=True),
        sa.Column("current_line", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Integer(), nullable=True),
        sa.Column("previous_line", sa.Float(), nullable=True),
        sa.Column("previous_price", sa.Integer(), nullable=True),
        sa.Column("opening_line", sa.Float(), nullable=True),
        sa.Column("opening_price", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(), nullable=True),
        sa.Column("movement_amount", sa.Float(), default=0.0),
        sa.Column("last_movement_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("snapshot_count", sa.Integer(), default=1),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index("ix_snapshots_event_market", "market_snapshots", ["event_id", "market_type"])
    op.create_index("ix_snapshots_captured", "market_snapshots", ["event_id", "captured_at"])
    op.create_index("ix_tracked_event_odd", "tracked_markets", ["event_id", "odd_id", "bookmaker"], unique=True)


def downgrade():
    op.drop_index("ix_tracked_event_odd", table_name="tracked_markets")
    op.drop_index("ix_snapshots_captured", table_name="market_snapshots")
    op.drop_index("ix_snapshots_event_market", table_name="market_snapshots")
    op.drop_table("tracked_markets")
    op.drop_table("market_snapshots")