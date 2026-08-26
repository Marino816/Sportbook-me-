"""create espn_news_items table

Revision ID: e3f4a5b6c7d8
Revises: f7f78e663688
Create Date: 2026-08-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd3f3g2d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'espn_news_items',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('guid', sa.String(), unique=True, index=True),
        sa.Column('article_url', sa.String()),
        sa.Column('headline', sa.String()),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('sport', sa.String(), index=True),
        sa.Column('source', sa.String(), server_default='ESPN'),
        sa.Column('stale', sa.Boolean(), server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_table('espn_news_items')