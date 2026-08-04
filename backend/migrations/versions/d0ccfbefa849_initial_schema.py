"""initial_schema

Revision ID: d0ccfbefa849
Revises:
Create Date: 2026-08-04 13:09:24.872786

Creates all tables for the Sportsbook Me DFS AI platform:
  users, slates, players, game_logs, projections, lineups,
  subscriptions, matchups, system_status, stripe_events
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0ccfbefa849"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("email", sa.String, unique=True, index=True),
        sa.Column("hashed_password", sa.String, nullable=True),
        sa.Column("is_pro", sa.Boolean, default=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("stripe_customer_id", sa.String, nullable=True),
        sa.Column("active_subscription_id", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            default=sa.func.now(),
        ),
    )

    # ── slates ─────────────────────────────────────────────
    op.create_table(
        "slates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("sport", sa.String),
        sa.Column("site", sa.String),
        sa.Column("date", sa.DateTime),
        sa.Column("is_main_slate", sa.Boolean, default=True),
    )

    # ── players ────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("sport", sa.String),
        sa.Column("name", sa.String),
        sa.Column("team", sa.String),
        sa.Column("active", sa.Boolean, default=True),
    )

    # ── subscriptions (created before users FK) ────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column(
            "stripe_subscription_id", sa.String, unique=True, index=True, nullable=True
        ),
        sa.Column("plan_name", sa.String),
        sa.Column("status", sa.String),
        sa.Column("mrr_value", sa.Float, default=49.99),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, default=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            default=sa.func.now(),
        ),
    )

    # Add FK from users -> subscriptions
    op.create_foreign_key(
        "fk_users_active_subscription",
        "users",
        "subscriptions",
        ["active_subscription_id"],
        ["id"],
    )

    # ── game_logs ──────────────────────────────────────────
    op.create_table(
        "game_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id")),
        sa.Column("date", sa.DateTime),
        sa.Column("fantasy_points", sa.Float),
        sa.Column("minutes", sa.Float, nullable=True),
        sa.Column("stats_json", sa.JSON),
    )

    # ── projections ────────────────────────────────────────
    op.create_table(
        "projections",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slate_id", sa.Integer, sa.ForeignKey("slates.id")),
        sa.Column("player_id", sa.Integer, sa.ForeignKey("players.id")),
        sa.Column("salary", sa.Integer),
        sa.Column("roster_position", sa.String),
        sa.Column("projected_fp", sa.Float),
        sa.Column("ceiling", sa.Float),
        sa.Column("floor", sa.Float),
        sa.Column("ownership", sa.Float),
        sa.Column("leverage", sa.Float),
        sa.Column("value", sa.Float),
        sa.Column("is_locked", sa.Boolean, default=False),
    )

    # ── lineups ────────────────────────────────────────────
    op.create_table(
        "lineups",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("slate_id", sa.Integer, sa.ForeignKey("slates.id")),
        sa.Column("projected_score", sa.Float),
        sa.Column("total_salary", sa.Integer),
        sa.Column("players_json", sa.JSON),
        sa.Column("actual_score", sa.Float, nullable=True),
        sa.Column("won_amount", sa.Float, default=0.0),
        sa.Column("entry_fee", sa.Float, default=0.0),
        sa.Column(
            "created_at",
            sa.DateTime,
            default=sa.func.now(),
        ),
    )

    # ── matchups ───────────────────────────────────────────
    op.create_table(
        "matchups",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("sport", sa.String),
        sa.Column("league", sa.String),
        sa.Column("home_team", sa.String),
        sa.Column("away_team", sa.String),
        sa.Column("game_time", sa.DateTime),
        sa.Column("status", sa.String, default="scheduled"),
        sa.Column("score_json", sa.JSON, nullable=True),
        sa.Column("odds_json", sa.JSON, nullable=True),
    )

    # ── system_status ──────────────────────────────────────
    op.create_table(
        "system_status",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("provider_name", sa.String, unique=True),
        sa.Column("is_healthy", sa.Boolean, default=True),
        sa.Column(
            "last_sync_time",
            sa.DateTime,
            default=sa.func.now(),
        ),
        sa.Column("last_sync_result", sa.String),
        sa.Column("data_source_mode", sa.String, default="live"),
    )

    # ── stripe_events ──────────────────────────────────────
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("event_id", sa.String, unique=True, index=True),
        sa.Column("event_type", sa.String),
        sa.Column(
            "processed_at",
            sa.DateTime,
            default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_events")
    op.drop_table("system_status")
    op.drop_table("matchups")
    op.drop_table("lineups")
    op.drop_table("projections")
    op.drop_table("game_logs")
    op.drop_table("subscriptions")
    op.drop_table("players")
    op.drop_table("slates")
    op.drop_table("users")