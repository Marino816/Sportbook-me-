"""create billing_entitlements for provider-aware access

Revision ID: c7d8e9f0a1b2
Revises: a9b8c7d6e5f4
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subscription_id", sa.String(), nullable=True),
        sa.Column("provider_plan_id", sa.String(), nullable=True),
        sa.Column("checkout_reference", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("billing_period", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_payment"),
        sa.Column("paid_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_test_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_transaction_id", sa.String(), nullable=True),
        sa.Column("last_refund_transaction_id", sa.String(), nullable=True),
        sa.Column("refunded_amount", sa.String(), nullable=True),
        sa.Column("compatibility_subscription_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_billing_entitlements_id", "billing_entitlements", ["id"])
    op.create_index("ix_billing_entitlements_user_id", "billing_entitlements", ["user_id"])
    op.create_index("ix_billing_entitlements_provider", "billing_entitlements", ["provider"])
    op.create_index(
        "ix_billing_entitlements_provider_subscription_id",
        "billing_entitlements",
        ["provider_subscription_id"],
    )
    op.create_index(
        "ix_billing_entitlements_checkout_reference",
        "billing_entitlements",
        ["checkout_reference"],
    )
    op.create_unique_constraint(
        "uq_billing_entitlement_provider_subscription",
        "billing_entitlements",
        ["provider", "provider_subscription_id"],
    )
    op.create_unique_constraint(
        "uq_billing_entitlement_provider_checkout",
        "billing_entitlements",
        ["provider", "checkout_reference"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_billing_entitlement_provider_checkout",
        "billing_entitlements",
        type_="unique",
    )
    op.drop_constraint(
        "uq_billing_entitlement_provider_subscription",
        "billing_entitlements",
        type_="unique",
    )
    op.drop_index("ix_billing_entitlements_checkout_reference", table_name="billing_entitlements")
    op.drop_index(
        "ix_billing_entitlements_provider_subscription_id",
        table_name="billing_entitlements",
    )
    op.drop_index("ix_billing_entitlements_provider", table_name="billing_entitlements")
    op.drop_index("ix_billing_entitlements_user_id", table_name="billing_entitlements")
    op.drop_index("ix_billing_entitlements_id", table_name="billing_entitlements")
    op.drop_table("billing_entitlements")
