"""create_coach_tables

Revision ID: 703b0229f207
Revises: 8402689d001b
Create Date: 2026-08-04

Creates Coach tables:
  contest_results, lineup_results, coach_sessions, coach_metrics,
  coach_findings, coach_recommendations
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "703b0229f207"
down_revision: Union[str, Sequence[str], None] = "8402689d001b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, cols in [
        ("contest_results", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("contest_id", sa.String, unique=True, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("platform", sa.String),
            sa.Column("sport", sa.String, server_default="nba"),
            sa.Column("league", sa.String, server_default="NBA"),
            sa.Column("slate_id", sa.Integer, nullable=True),
            sa.Column("contest_type", sa.String, nullable=True),
            sa.Column("contest_name", sa.String, nullable=True),
            sa.Column("entry_fee", sa.Float, nullable=True),
            sa.Column("entry_count", sa.Integer, nullable=True),
            sa.Column("finishing_position", sa.Integer, nullable=True),
            sa.Column("payout", sa.Float, nullable=True),
            sa.Column("submitted_lineup_id", sa.String, nullable=True),
            sa.Column("final_lineup_score", sa.Float, nullable=True),
            sa.Column("cash_line", sa.Float, nullable=True),
            sa.Column("winning_score", sa.Float, nullable=True),
            sa.Column("ownership_data_available", sa.Boolean, server_default=sa.text("false")),
            sa.Column("result_timestamp", sa.DateTime(timezone=True)),
            sa.Column("data_source", sa.String, server_default="manual_import"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("lineup_results", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("lineup_id", sa.String, index=True),
            sa.Column("contest_id", sa.String, sa.ForeignKey("contest_results.contest_id"), index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("projected_score", sa.Float, nullable=True),
            sa.Column("projected_ceiling", sa.Float, nullable=True),
            sa.Column("final_score", sa.Float, nullable=True),
            sa.Column("projection_error", sa.Float, nullable=True),
            sa.Column("percentile_finish", sa.Float, nullable=True),
            sa.Column("salary_used", sa.Integer, nullable=True),
            sa.Column("ownership_sum", sa.Float, nullable=True),
            sa.Column("leverage_score", sa.Float, nullable=True),
            sa.Column("strategy_profile", sa.String, nullable=True),
            sa.Column("model_version", sa.String, nullable=True),
            sa.Column("stack_summary", sa.JSON, nullable=True),
            sa.Column("scout_events_after_lock", sa.JSON, server_default=sa.text("'[]'")),
            sa.Column("stale_at_lock", sa.Boolean, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("coach_sessions", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("session_id", sa.String, unique=True, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("session_type", sa.String),
            sa.Column("entity_ref", sa.String, nullable=True),
            sa.Column("contest_count", sa.Integer, server_default="0"),
            sa.Column("date_range_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("date_range_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("coach_metrics", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("session_id", sa.String, sa.ForeignKey("coach_sessions.session_id"), index=True),
            sa.Column("metric_name", sa.String),
            sa.Column("metric_value", sa.Float, nullable=True),
            sa.Column("metric_label", sa.String, nullable=True),
            sa.Column("sample_size", sa.Integer, server_default="0"),
            sa.Column("confidence", sa.Float, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("coach_findings", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("session_id", sa.String, sa.ForeignKey("coach_sessions.session_id"), index=True),
            sa.Column("finding_type", sa.String),
            sa.Column("category", sa.String),
            sa.Column("headline", sa.String),
            sa.Column("detail", sa.String),
            sa.Column("supporting_metric", sa.Float, nullable=True),
            sa.Column("sample_size", sa.Integer, server_default="0"),
            sa.Column("confidence", sa.Float, server_default="0.0"),
            sa.Column("missing_data_warning", sa.Boolean, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
        ("coach_recommendations", [
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("session_id", sa.String, sa.ForeignKey("coach_sessions.session_id"), index=True),
            sa.Column("recommendation", sa.String),
            sa.Column("rationale", sa.String),
            sa.Column("linked_finding_id", sa.Integer, nullable=True),
            sa.Column("priority", sa.String, server_default="medium"),
            sa.Column("confidence", sa.Float, server_default="0.0"),
            sa.Column("sample_size", sa.Integer, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]),
    ]:
        op.create_table(name, *cols)


def downgrade() -> None:
    for t in ["coach_recommendations", "coach_findings", "coach_metrics",
              "coach_sessions", "lineup_results", "contest_results"]:
        op.drop_table(t)