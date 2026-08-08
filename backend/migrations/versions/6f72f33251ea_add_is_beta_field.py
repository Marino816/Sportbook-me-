"""add_is_beta_field

Revision ID: 6f72f33251ea
Revises: daf10664307c
Create Date: 2026-08-06
"""

from collections.abc import Sequence
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "6f72f33251ea"
down_revision: Union[str, None] = "daf10664307c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_beta", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "is_beta")