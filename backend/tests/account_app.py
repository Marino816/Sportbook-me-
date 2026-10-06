"""Isolated FastAPI app for account-deletion tests."""

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api import account, auth
from models.database import Base, get_db

from assistant import models as _assistant_models  # noqa: F401
from builder import models as _builder_models  # noqa: F401
from coach import models as _coach_models  # noqa: F401
from mission_control import models as _mc_models  # noqa: F401
from models import ai_models as _ai_models  # noqa: F401
from models import domain as _domain  # noqa: F401
from scout import models as _scout_models  # noqa: F401

TEST_DB_PATH = "/tmp/sbme_account_delete_test.sqlite"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_ORM_TABLES = (
    "assistant_messages",
    "assistant_conversations",
    "assistant_preferences",
    "builder_exposure_rules",
    "builder_lineups",
    "builder_portfolios",
    "builder_runs",
    "coach_recommendations",
    "coach_findings",
    "coach_metrics",
    "coach_sessions",
    "lineup_results",
    "contest_results",
    "scout_alerts",
    "mission_control_preferences",
    "mission_control_snapshots",
    "lineups",
    "lineup_history",
    "revenue_logs",
    "ai_audit_logs",
    "ai_chat_logs",
    "stripe_events",
    "players",
    "slates",
    "users",
    "subscriptions",
)


async def override_get_db():
    async with TestSession() as session:
        yield session


def _rebuild(sync_conn):
    sync_conn.execute(text("PRAGMA foreign_keys=OFF"))
    for name in _ORM_TABLES:
        sync_conn.execute(text(f"DROP TABLE IF EXISTS {name}"))
    sync_conn.execute(text("DROP TABLE IF EXISTS user_oauth_identities"))
    sync_conn.execute(text("DROP TABLE IF EXISTS billing_checkouts"))
    Base.metadata.create_all(sync_conn)
    sync_conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS user_oauth_identities ("
            "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, provider VARCHAR, provider_subject VARCHAR)"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS billing_checkouts ("
            "id INTEGER PRIMARY KEY, user_id INTEGER, checkout_reference VARCHAR)"
        )
    )


async def reset_account_db():
    async with engine.begin() as conn:
        await conn.run_sync(_rebuild)


account_app = FastAPI()
account_app.include_router(auth.router, prefix="/api")
account_app.include_router(account.router, prefix="/api")
account_app.dependency_overrides[get_db] = override_get_db
