"""apple environment identity + ASSN V2 notification ledger

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_billing_entitlement_provider_subscription",
        "billing_entitlements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_billing_entitlement_provider_subscription_env",
        "billing_entitlements",
        ["provider", "provider_subscription_id", "is_test_mode"],
    )
    op.add_column(
        "billing_entitlements",
        sa.Column("last_provider_signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "apple_notification_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_uuid", sa.String(), nullable=False),
        sa.Column("signed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_type", sa.String(), nullable=True),
        sa.Column("subtype", sa.String(), nullable=True),
        sa.Column("environment", sa.String(), nullable=True),
        sa.Column("original_transaction_id", sa.String(), nullable=True),
        sa.Column("transaction_id", sa.String(), nullable=True),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("decision", sa.String(), nullable=False, server_default="received"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_apple_notification_events_notification_uuid",
        "apple_notification_events",
        ["notification_uuid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_apple_notification_events_notification_uuid",
        table_name="apple_notification_events",
    )
    op.drop_table("apple_notification_events")
    op.drop_column("billing_entitlements", "last_provider_signed_at")
    op.drop_constraint(
        "uq_billing_entitlement_provider_subscription_env",
        "billing_entitlements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_billing_entitlement_provider_subscription",
        "billing_entitlements",
        ["provider", "provider_subscription_id"],
    )
