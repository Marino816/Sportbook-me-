"""add_timezone_to_datetime_columns

Revision ID: 7a35791ef604
Revises: 9bfba1581b4f
Create Date: 2026-08-04

Converts all TIMESTAMP WITHOUT TIME ZONE columns that store timezone-aware
UTC values to TIMESTAMP WITH TIME ZONE. This fixes the asyncpg error:

    can't subtract offset-naive and offset-aware datetimes

Columns affected (5):
  users.created_at, lineups.created_at, subscriptions.created_at,
  system_status.last_sync_time, stripe_events.processed_at
"""

from collections.abc import Sequence
from typing import Union

from alembic import op


revision: str = "7a35791ef604"
down_revision: Union[str, Sequence[str], None] = "9bfba1581b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE lineups ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE system_status ALTER COLUMN last_sync_time TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE stripe_events ALTER COLUMN processed_at TYPE TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    op.execute("ALTER TABLE stripe_events ALTER COLUMN processed_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE system_status ALTER COLUMN last_sync_time TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE lineups ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
