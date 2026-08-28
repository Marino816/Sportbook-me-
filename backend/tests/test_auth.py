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
async def test_register_normal_password(client):
    """A normal, short (8-20 char) ASCII password should register fine."""
    res = await client.post(
        "/api/auth/register",
        json={"email": "normal@example.com", "password": "goodpass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "normal@example.com"


@pytest.mark.asyncio
async def test_register_password_exactly_72_bytes(client):
    """A password that is exactly 72 ASCII bytes is valid (bcrypt's limit)."""
    password = "a" * 72
    assert len(password.encode("utf-8")) == 72
    res = await client.post(
        "/api/auth/register",
        json={"email": "seventytwo@example.com", "password": password},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_password_73_bytes_rejected(client):
    """A password of 73 ASCII bytes exceeds bcrypt's 72-byte limit and
    must be rejected with HTTP 422 rather than bubbling up as a 500."""
    password = "a" * 73
    assert len(password.encode("utf-8")) == 73
    res = await client.post(
        "/api/auth/register",
        json={"email": "seventythree@example.com", "password": password},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_multibyte_password_exceeds_72_bytes(client):
    """Multibyte unicode characters must be measured in UTF-8 bytes, not
    character count. A password of 30 multibyte chars (3 bytes each in
    UTF-8) is 90 bytes and must be rejected, even though it is only
    30 characters long."""
    password = "\u4e2d" * 30  # CJK character, 3 bytes each in UTF-8 = 90 bytes
    assert len(password) == 30
    assert len(password.encode("utf-8")) > 72
    res = await client.post(
        "/api/auth/register",
        json={"email": "multibyte@example.com", "password": password},
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
    assert res.json()["plan"] == "Starter"
    assert "is_pro" in res.json()


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


# ── Unit tests: password hashing (passlib/bcrypt) ────────────

class TestPasswordHashing:
    """Direct unit tests for hash_password()/verify_password() to confirm
    the passlib 1.7.4 / bcrypt 4.3.0 combination works correctly."""

    def test_hash_and_verify_roundtrip(self):
        from api.auth import hash_password, verify_password

        hashed = hash_password("securepass123")
        assert hashed != "securepass123"
        assert verify_password("securepass123", hashed) is True

    def test_verify_rejects_wrong_password(self):
        from api.auth import hash_password, verify_password

        hashed = hash_password("securepass123")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_at_72_byte_limit(self):
        """bcrypt's underlying limit is 72 bytes; hashing a password at
        exactly that limit must not raise."""
        from api.auth import hash_password, verify_password

        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ── Unit tests: JWT creation and validation ──────────────────

class TestJWTTokens:
    """Direct unit tests for create_access_token()/decode_access_token()."""

    def test_create_and_decode_access_token(self):
        from api.auth import create_access_token, decode_access_token

        token = create_access_token({"sub": "42", "role": "user"})
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "user"
        assert "exp" in payload

    def test_decode_invalid_token_raises_401(self):
        from fastapi import HTTPException
        from api.auth import decode_access_token

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_decode_expired_token_raises_401(self):
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt
        from fastapi import HTTPException
        from api.auth import decode_access_token, SECRET_KEY, ALGORITHM

        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jose_jwt.encode(
            {"sub": "1", "exp": expired}, SECRET_KEY, algorithm=ALGORITHM
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401