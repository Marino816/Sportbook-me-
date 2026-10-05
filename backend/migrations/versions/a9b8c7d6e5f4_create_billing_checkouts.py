"""create billing_checkouts for PayKings pending checkout binding

Revision ID: a9b8c7d6e5f4
Revises: f8a4c1d2e3b0
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f8a4c1d2e3b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_checkouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="paykings"),
        sa.Column("checkout_reference", sa.String(), nullable=False),
        sa.Column("provider_customer_id", sa.String(), nullable=True),
        sa.Column("provider_transaction_id", sa.String(), nullable=True),
        sa.Column("provider_subscription_id", sa.String(), nullable=True),
        sa.Column("provider_plan_id", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("billing_period", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_billing_checkouts_id", "billing_checkouts", ["id"])
    op.create_index("ix_billing_checkouts_user_id", "billing_checkouts", ["user_id"])
    op.create_index("ix_billing_checkouts_provider", "billing_checkouts", ["provider"])
    op.create_index(
        "ix_billing_checkouts_checkout_reference",
        "billing_checkouts",
        ["checkout_reference"],
        unique=True,
    )
    op.create_index(
        "ix_billing_checkouts_provider_customer_id",
        "billing_checkouts",
        ["provider_customer_id"],
    )
    op.create_index(
        "ix_billing_checkouts_provider_subscription_id",
        "billing_checkouts",
        ["provider_subscription_id"],
    )
    op.create_unique_constraint(
        "uq_billing_checkout_provider_subscription",
        "billing_checkouts",
        ["provider", "provider_subscription_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_billing_checkout_provider_subscription",
        "billing_checkouts",
        type_="unique",
    )
    op.drop_index("ix_billing_checkouts_provider_subscription_id", table_name="billing_checkouts")
    op.drop_index("ix_billing_checkouts_provider_customer_id", table_name="billing_checkouts")
    op.drop_index("ix_billing_checkouts_checkout_reference", table_name="billing_checkouts")
    op.drop_index("ix_billing_checkouts_provider", table_name="billing_checkouts")
    op.drop_index("ix_billing_checkouts_user_id", table_name="billing_checkouts")
    op.drop_index("ix_billing_checkouts_id", table_name="billing_checkouts")
    op.drop_table("billing_checkouts")
