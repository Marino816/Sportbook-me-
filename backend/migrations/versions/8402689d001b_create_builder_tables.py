"""create_builder_tables

Revision ID: 8402689d001b
Revises: 605191c0ba9c
Create Date: 2026-08-04

Creates builder tables:
  builder_runs, builder_lineups, builder_portfolios, builder_exposure_rules
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "8402689d001b"
down_revision: Union[str, Sequence[str], None] = "605191c0ba9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("builder_runs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("run_id", sa.String, unique=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("slate_id", sa.Integer),
        sa.Column("sport", sa.String, server_default="nba"),
        sa.Column("platform", sa.String, server_default="draftkings"),
        sa.Column("strategy_profile", sa.String, server_default="balanced"),
        sa.Column("lineup_count", sa.Integer, server_default="1"),
        sa.Column("locked_player_ids", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("excluded_player_ids", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("exposure_rules", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("stack_rules", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("uniqueness_count", sa.Integer, server_default="2"),
        sa.Column("generated_count", sa.Integer, server_default="0"),
        sa.Column("solver_status", sa.String, server_default="pending"),
        sa.Column("runtime_ms", sa.Float, nullable=True),
        sa.Column("portfolio_metrics", sa.JSON, nullable=True),
        sa.Column("scout_event_ids", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("model_name", sa.String),
        sa.Column("model_version", sa.String),
        sa.Column("projection_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("builder_lineups",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("builder_runs.run_id"), index=True),
        sa.Column("lineup_index", sa.Integer),
        sa.Column("projected_score", sa.Float),
        sa.Column("ceiling_score", sa.Float, nullable=True),
        sa.Column("total_salary", sa.Integer),
        sa.Column("remaining_salary", sa.Integer, nullable=True),
        sa.Column("ownership_estimate", sa.Float, nullable=True),
        sa.Column("leverage_estimate", sa.Float, nullable=True),
        sa.Column("correlation_summary", sa.String, nullable=True),
        sa.Column("edge_score", sa.Float, nullable=True),
        sa.Column("risk_score", sa.Float, nullable=True),
        sa.Column("players_json", sa.JSON),
        sa.Column("strategy_profile", sa.String),
        sa.Column("explanation", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("is_stale", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("builder_portfolios",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("portfolio_id", sa.String, unique=True, index=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("builder_runs.run_id")),
        sa.Column("lineup_count", sa.Integer),
        sa.Column("avg_projection", sa.Float),
        sa.Column("avg_ceiling", sa.Float, nullable=True),
        sa.Column("avg_salary", sa.Float),
        sa.Column("avg_ownership", sa.Float, nullable=True),
        sa.Column("avg_leverage", sa.Float, nullable=True),
        sa.Column("exposure_json", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("diversity_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("builder_exposure_rules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("builder_runs.run_id"), index=True),
        sa.Column("entity_type", sa.String),
        sa.Column("entity_id", sa.Integer),
        sa.Column("entity_name", sa.String, nullable=True),
        sa.Column("min_exposure", sa.Float, server_default="0.0"),
        sa.Column("max_exposure", sa.Float, server_default="1.0"),
        sa.Column("actual_exposure", sa.Float, nullable=True),
        sa.Column("is_satisfied", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("builder_exposure_rules")
    op.drop_table("builder_portfolios")
    op.drop_table("builder_lineups")
    op.drop_table("builder_runs")