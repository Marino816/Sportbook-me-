"""
Alembic environment configuration for Sportsbook Me DFS AI.

Reads DATABASE_URL from the environment (with asyncpg conversion for Railway).
Imports all SQLAlchemy models so autogenerate can detect schema changes.

Usage:
    # From the backend/ directory:
    alembic upgrade head          # apply all migrations
    alembic downgrade -1          # roll back one revision
    alembic revision --autogenerate -m "description"  # create new migration
    alembic current               # show current revision
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure backend package is on sys.path
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from models.database import Base

# Import all domain models so Base.metadata knows about every table
from models.domain import (  # noqa: F401
    User,
    Slate,
    Player,
    GameLog,
    Projection,
    Lineup,
    Subscription,
    Matchup,
    SystemStatus,
    StripeEvent,
)

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable (with asyncpg conversion)
_raw_url = os.getenv(
    "DATABASE_URL", config.get_main_option("sqlalchemy.url")
)
if _raw_url and _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", _raw_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live database)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Configure context and run migrations synchronously within async connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Run async migrations against a live async database (asyncpg)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Synchronous wrapper to invoke async migration runner."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()