"""
Shared conftest for Sportsbook Me DFS AI tests.

Provides a single async database override so all test suites can
share one in-memory SQLite engine without fixture conflicts.

Import this in individual test files via:
  from conftest import _engine, _TestSession, override_get_db
  app.dependency_overrides[get_db] = override_get_db
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite://"

_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TestSession() as session:
        yield session


def pytest_configure(config):
    """Set up the shared engine before test collection."""
    app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
async def shared_module_setup():
    """Create tables once per test module."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def clean_db():
    """Reset all tables before each test function."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield