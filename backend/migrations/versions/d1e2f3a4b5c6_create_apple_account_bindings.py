"""create apple_account_bindings for StoreKit appAccountToken

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "apple_account_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_apple_account_bindings_user_id", "apple_account_bindings", ["user_id"], unique=True)
    op.create_index("ix_apple_account_bindings_token", "apple_account_bindings", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_apple_account_bindings_token", table_name="apple_account_bindings")
    op.drop_index("ix_apple_account_bindings_user_id", table_name="apple_account_bindings")
    op.drop_table("apple_account_bindings")
