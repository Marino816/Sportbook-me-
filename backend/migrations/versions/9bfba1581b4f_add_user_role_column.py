"""add_user_role_column

Revision ID: 9bfba1581b4f
Revises: d0ccfbefa849
Create Date: 2026-08-04

Adds the 'role' column to the users table with a default of 'user'.
Existing users are NOT auto-promoted to admin.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "9bfba1581b4f"
down_revision: Union[str, Sequence[str], None] = "d0ccfbefa849"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String, nullable=False, server_default="user"))


def downgrade() -> None:
    op.drop_column("users", "role")
