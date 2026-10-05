"""create payment_webhook_events for PayKings idempotency

Revision ID: f8a4c1d2e3b0
Revises: e4a1b2c3
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f8a4c1d2e3b0"
down_revision: Union[str, Sequence[str], None] = "e4a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False, server_default="paykings"),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("idempotency_source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sanitized_payload", sa.JSON(), nullable=True),
    )
    op.create_index("ix_payment_webhook_events_id", "payment_webhook_events", ["id"])
    op.create_index("ix_payment_webhook_events_provider", "payment_webhook_events", ["provider"])
    op.create_index(
        "ix_payment_webhook_events_provider_event_id",
        "payment_webhook_events",
        ["provider_event_id"],
    )
    op.create_index("ix_payment_webhook_events_event_type", "payment_webhook_events", ["event_type"])
    op.create_unique_constraint(
        "uq_payment_webhook_provider_event",
        "payment_webhook_events",
        ["provider", "provider_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payment_webhook_provider_event", "payment_webhook_events", type_="unique")
    op.drop_index("ix_payment_webhook_events_event_type", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_provider_event_id", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_provider", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
