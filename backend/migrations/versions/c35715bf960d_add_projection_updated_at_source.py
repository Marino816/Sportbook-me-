"""add_projection_updated_at_source

Revision ID: c35715bf960d
Revises: 6f72f33251ea
Create Date: 2026-08-08
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("projections", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projections", sa.Column("source", sa.String(), nullable=True, server_default="seed"))


def downgrade() -> None:
    op.drop_column("projections", "source")
    op.drop_column("projections", "updated_at")