"""create_analyst_tables

Revision ID: 605191c0ba9c
Revises: f7f78e663688
Create Date: 2026-08-04

Creates analyst tables:
  analyst_insights, analyst_factors, analyst_risks
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "605191c0ba9c"
down_revision: Union[str, Sequence[str], None] = "f7f78e663688"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_insights",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("insight_id", sa.String, unique=True, index=True),
        sa.Column("insight_type", sa.String, index=True),
        sa.Column("sport", sa.String, server_default="nba"),
        sa.Column("league", sa.String, server_default="NBA"),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("entity_type", sa.String, nullable=True),
        sa.Column("event_id", sa.Integer, nullable=True),
        sa.Column("slate_id", sa.Integer, nullable=True),
        sa.Column("platform", sa.String, server_default="draftkings"),
        sa.Column("headline", sa.String),
        sa.Column("summary", sa.String),
        sa.Column("verified_facts", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("projection_factors", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("market_factors", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("injury_factors", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("matchup_factors", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("risk_factors", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("edge_score", sa.Float, nullable=True),
        sa.Column("confidence_score", sa.Float),
        sa.Column("confidence_components", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("source_event_ids", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("model_name", sa.String),
        sa.Column("model_version", sa.String),
        sa.Column("data_timestamp", sa.DateTime(timezone=True)),
        sa.Column("stale_data_flag", sa.Boolean, server_default=sa.text("false")),
        sa.Column("missing_data_flags", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "analyst_factors",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("insight_id", sa.String, sa.ForeignKey("analyst_insights.insight_id"), index=True),
        sa.Column("factor_type", sa.String),
        sa.Column("factor_name", sa.String),
        sa.Column("factor_value", sa.Float, nullable=True),
        sa.Column("factor_label", sa.String, nullable=True),
        sa.Column("weight", sa.Float, server_default=sa.text("1.0")),
        sa.Column("direction", sa.String, server_default="neutral"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "analyst_risks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("insight_id", sa.String, sa.ForeignKey("analyst_insights.insight_id"), index=True),
        sa.Column("risk_type", sa.String),
        sa.Column("risk_label", sa.String),
        sa.Column("severity", sa.Float),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("is_mitigated", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analyst_risks")
    op.drop_table("analyst_factors")
    op.drop_table("analyst_insights")