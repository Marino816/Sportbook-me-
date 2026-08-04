"""
Role-based access control tests for Sportsbook Me DFS AI.

Run with: pytest tests/test_rbac.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


async def _reset_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
async def setup_db():
    await _reset_db()
    yield
    await _reset_db()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_user(client, email, password="securepass123"):
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )


async def _login(client, email, password="securepass123"):
    res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    return res.json()["access_token"]


async def _make_admin(client, email):
    """Manually promote a user to admin in the test DB."""
    async with _TestSession() as db:
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            user.role = "admin"
            await db.commit()


class TestAdminEndpoints:
    """Verify admin API endpoints enforce role-based access."""

    async def test_unauthenticated_denied(self, client):
        res = await client.get("/api/admin/summary")
        assert res.status_code == 401

    async def test_normal_user_denied(self, client):
        await _register_user(client, "user@test.com")
        token = await _login(client, "user@test.com")
        res = await client.get(
            "/api/admin/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert "admin" in res.json()["detail"].lower()

    async def test_admin_allowed(self, client):
        await _register_user(client, "admin@test.com")
        await _make_admin(client, "admin@test.com")
        token = await _login(client, "admin@test.com")
        res = await client.get(
            "/api/admin/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

    async def test_admin_access_all_endpoints(self, client):
        await _register_user(client, "super@test.com")
        await _make_admin(client, "super@test.com")
        token = await _login(client, "super@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        endpoints = [
            "/api/admin/summary",
            "/api/admin/revenue-trends",
            "/api/admin/distribution",
            "/api/admin/events",
            "/api/admin/health",
        ]
        for ep in endpoints:
            res = await client.get(ep, headers=headers)
            assert res.status_code == 200, f"{ep} returned {res.status_code}"

    async def test_normal_user_denied_all_endpoints(self, client):
        await _register_user(client, "pleb@test.com")
        token = await _login(client, "pleb@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        endpoints = [
            "/api/admin/summary",
            "/api/admin/revenue-trends",
            "/api/admin/distribution",
            "/api/admin/events",
            "/api/admin/health",
            "/api/admin/sync/trigger",
        ]
        for ep in endpoints:
            res = await client.get(ep, headers=headers) if "sync" not in ep else await client.post(ep, headers=headers)
            assert res.status_code == 403, f"{ep} returned {res.status_code}"


class TestAuthMeRole:
    """Verify /auth/me includes the role field."""

    async def test_me_includes_role_for_user(self, client):
        await _register_user(client, "roleuser@test.com")
        token = await _login(client, "roleuser@test.com")
        res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "role" in data
        assert data["role"] == "user"

    async def test_me_includes_role_for_admin(self, client):
        await _register_user(client, "roleadmin@test.com")
        await _make_admin(client, "roleadmin@test.com")
        token = await _login(client, "roleadmin@test.com")
        res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["role"] == "admin"


class TestRegistrationDefaults:
    """Verify new users default to 'user' role."""

    async def test_new_registration_is_user_role(self, client):
        res = await client.post(
            "/api/auth/register",
            json={"email": "fresh@test.com", "password": "securepass123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "user"

    async def test_login_returns_role(self, client):
        await _register_user(client, "loginrole@test.com")
        res = await client.post(
            "/api/auth/login",
            json={"email": "loginrole@test.com", "password": "securepass123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "user"


class TestRegistrationDoesNotCreateAdmin:
    """Verify registration cannot create an admin — only manual promotion."""

    async def test_cannot_set_role_via_registration(self, client):
        # Try to register with a role in the request body — should be ignored
        res = await client.post(
            "/api/auth/register",
            json={"email": "hacker@test.com", "password": "securepass123", "role": "admin"},
        )
        assert res.status_code == 200
        assert res.json()["role"] == "user"  # Always defaults to user
