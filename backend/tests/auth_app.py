"""Minimal FastAPI app for auth tests (avoids importing the full DFS stack)."""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api import auth, oauth
from api.auth import get_current_user
from models.database import Base, get_db
from models.domain import Subscription, User

TEST_DB_PATH = "/tmp/sbme_auth_shared_test.sqlite"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


def _rebuild(sync_conn):
    sync_conn.execute(text("PRAGMA foreign_keys=OFF"))
    for name in ("user_oauth_identities", "users", "subscriptions"):
        sync_conn.execute(text(f"DROP TABLE IF EXISTS {name}"))
    Base.metadata.create_all(sync_conn)


async def reset_auth_db():
    async with engine.begin() as conn:
        await conn.run_sync(_rebuild)


auth_app = FastAPI()
auth_app.include_router(auth.router, prefix="/api")
auth_app.include_router(oauth.router, prefix="/api")
auth_app.dependency_overrides[get_db] = override_get_db


@auth_app.get("/api/billing/status")
async def billing_status(user: User = Depends(get_current_user)):
    return {"data": {"plan": "Starter"}}


@auth_app.post("/api/optimize")
async def optimize(user: User = Depends(get_current_user)):
    return {"ok": True}
