"""add users.username and user_oauth_identities

Revision ID: e4a1b2c3
Revises: d3f3g2d1
Create Date: 2026-08-29

Existing users keep their email, password hash, role, subscription, and
billing identity. username is nullable so current accounts remain valid.

users.hashed_password is already nullable at d3f3g2d1 (created that way in
d0ccfbefa849; no later revision changes it). OAuth-only accounts use NULL
hashes. This revision only alters hashed_password if a database somehow
has it NOT NULL.

Downgrade never restores NOT NULL: the d3f3g2d1 constraint is nullable, and
OAuth-only NULL hashes would make a NOT NULL restore unsafe.
"""

from typing import Optional

from alembic import op
import sqlalchemy as sa

revision = "e4a1b2c3"
down_revision = "d3f3g2d1"
branch_labels = None
depends_on = None


def _hashed_password_nullable(bind) -> Optional[bool]:
    inspector = sa.inspect(bind)
    for col in inspector.get_columns("users"):
        if col["name"] == "hashed_password":
            return bool(col.get("nullable"))
    return None


def upgrade():
    bind = op.get_bind()
    if _hashed_password_nullable(bind) is False:
        op.alter_column(
            "users",
            "hashed_password",
            existing_type=sa.String(),
            nullable=True,
        )

    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "user_oauth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subject", sa.String(), nullable=False),
        sa.Column("provider_email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_oauth_identities_user_id", "user_oauth_identities", ["user_id"])
    op.create_index(
        "uq_oauth_provider_subject",
        "user_oauth_identities",
        ["provider", "provider_subject"],
        unique=True,
    )


def downgrade():
    # Intentionally do not set hashed_password back to NOT NULL.
    # Prior revision d3f3g2d1 is already nullable, and OAuth-only rows
    # with NULL hashes would make that restore fail or lose accounts.
    op.drop_index("uq_oauth_provider_subject", table_name="user_oauth_identities")
    op.drop_index("ix_user_oauth_identities_user_id", table_name="user_oauth_identities")
    op.drop_table("user_oauth_identities")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
