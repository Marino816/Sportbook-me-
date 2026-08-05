"""create_ai_engine_phase7a_tables

Revision ID: d5835ac224eb
Revises: df12511b7d71
Create Date: 2026-08-04

Creates the 6 Phase 7A AI engine tables:
  ai_models, ai_model_versions, ai_predictions, ai_prediction_inputs,
  ai_explanations, ai_audit_logs
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5835ac224eb"
down_revision: Union[str, Sequence[str], None] = "df12511b7d71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, unique=True, index=True),
        sa.Column("sport", sa.String, index=True),
        sa.Column("model_type", sa.String),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_model_versions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("ai_models.id")),
        sa.Column("version", sa.String),
        sa.Column("parameters_json", sa.JSON, nullable=True),
        sa.Column("training_data_range", sa.String, nullable=True),
        sa.Column("metrics_json", sa.JSON, nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_table(
        "ai_predictions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("model_version_id", sa.Integer, sa.ForeignKey("ai_model_versions.id")),
        sa.Column("entity_id", sa.Integer),
        sa.Column("entity_type", sa.String),
        sa.Column("sport", sa.String),
        sa.Column("slate_id", sa.Integer, sa.ForeignKey("slates.id"), nullable=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("matchups.id"), nullable=True),
        sa.Column("platform", sa.String),
        sa.Column("median_projection", sa.Float),
        sa.Column("floor_projection", sa.Float),
        sa.Column("ceiling_projection", sa.Float),
        sa.Column("boom_probability", sa.Float, nullable=True),
        sa.Column("bust_probability", sa.Float, nullable=True),
        sa.Column("salary", sa.Integer, nullable=True),
        sa.Column("value_score", sa.Float, nullable=True),
        sa.Column("matchup_score", sa.Float, nullable=True),
        sa.Column("ownership_projection", sa.Float, nullable=True),
        sa.Column("leverage_score", sa.Float, nullable=True),
        sa.Column("injury_adjustment", sa.Float, nullable=True),
        sa.Column("market_adjustment", sa.Float, nullable=True),
        sa.Column("confidence_score", sa.Float),
        sa.Column("model_version", sa.String),
        sa.Column("input_data_timestamp", sa.DateTime(timezone=True)),
        sa.Column("missing_data_flags", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("stale_data_flag", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_prediction_inputs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("prediction_id", sa.Integer, sa.ForeignKey("ai_predictions.id")),
        sa.Column("input_type", sa.String),
        sa.Column("input_value", sa.JSON),
        sa.Column("source", sa.String),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_explanations",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("prediction_id", sa.Integer, sa.ForeignKey("ai_predictions.id")),
        sa.Column("explanation_text", sa.String),
        sa.Column("factors_json", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("model_version", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String),
        sa.Column("endpoint", sa.String),
        sa.Column("input_hash", sa.String),
        sa.Column("response_hash", sa.String),
        sa.Column("model_version", sa.String, nullable=True),
        sa.Column("tokens_used", sa.Integer, server_default=sa.text("0")),
        sa.Column("cost", sa.Float, server_default=sa.text("0.0")),
        sa.Column("latency_ms", sa.Float),
        sa.Column("success", sa.Boolean, server_default=sa.text("true")),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_audit_logs")
    op.drop_table("ai_explanations")
    op.drop_table("ai_prediction_inputs")
    op.drop_table("ai_predictions")
    op.drop_table("ai_model_versions")
    op.drop_table("ai_models")
