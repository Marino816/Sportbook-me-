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


@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "anotherpass456"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client):
    res = await client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/auth/register",
        json={"email": "login@test.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"email": "login@test.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "badpw@test.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"email": "badpw@test.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    res = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "whatever"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_missing_token(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client):
    res = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid_token_here"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_expired_token(client):
    from jose import jwt as jose_jwt
    from datetime import datetime, timedelta, timezone

    expired = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jose_jwt.encode(
        {"sub": 999, "exp": expired},
        "dev-secret-change-in-production",
        algorithm="HS256",
    )
    res = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_with_valid_token(client):
    # Register and login
    await client.post(
        "/api/auth/register",
        json={"email": "valid@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "valid@test.com", "password": "securepass123"},
    )
    token = login_res.json()["access_token"]

    res = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["email"] == "valid@test.com"


@pytest.mark.asyncio
async def test_optimize_requires_auth_missing_token(client):
    res = await client.post(
        "/api/optimize",
        json={"slate_id": 1, "settings": {"num_lineups": 1}},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_billing_status_requires_auth(client):
    res = await client.get("/api/billing/status")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_billing_status_with_token(client):
    await client.post(
        "/api/auth/register",
        json={"email": "bill@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "bill@test.com", "password": "securepass123"},
    )
    token = login_res.json()["access_token"]

    res = await client.get(
        "/api/billing/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["data"]["plan"] == "Starter"


@pytest.mark.asyncio
async def test_disabled_user_cannot_access(client):
    await client.post(
        "/api/auth/register",
        json={"email": "disabled@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "disabled@test.com", "password": "securepass123"},
    )
    token = login_res.json()["access_token"]

    # Disable the user
    async with _TestSession() as db:
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(User).where(User.email == "disabled@test.com")
        )
        user = result.scalars().first()
        if user:
            user.is_active = False
            await db.commit()

    res = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403