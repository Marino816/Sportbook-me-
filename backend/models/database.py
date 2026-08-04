import os
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

_engine = None
_SessionLocal = None
_sync_engine = None
_SyncSessionLocal = None


def _get_database_url():
    raw = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/apex_dfs")
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


def _init_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return
    url = _get_database_url()
    is_production = os.getenv("NODE_ENV") == "production"
    connect_args = {"ssl": "require"} if is_production else {}
    _engine = create_async_engine(
        url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )
    _SessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    _init_engine()
    async with _SessionLocal() as session:
        yield session


def SessionLocal():
    """Synchronous accessor for Stripe webhooks and Celery tasks."""
    _init_engine()
    return _SessionLocal()


def SyncSessionLocal():
    """Create a sync SQLAlchemy session for Stripe webhooks.

    Stripe's Python library is synchronous, so webhook handlers need a sync
    session. This returns a standard SQLAlchemy Session (not async).
    """
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        url = _get_database_url()
        # Convert asyncpg URL to sync psycopg2 URL for sync engine
        sync_url = url.replace("+asyncpg", "")
        is_production = os.getenv("NODE_ENV") == "production"
        connect_args = {"ssl": "require"} if is_production else {}
        _sync_engine = create_sync_engine(
            sync_url,
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        _SyncSessionLocal = sessionmaker(
            _sync_engine, class_=Session, expire_on_commit=False
        )
    return _SyncSessionLocal()