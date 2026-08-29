import pytest

from httpx import AsyncClient, ASGITransport

from tests.auth_app import TestSession as _TestSession
from tests.auth_app import auth_app as app
from tests.auth_app import reset_auth_db
from models.domain import User


async def _reset_db():
    await reset_auth_db()


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
        json={"username": "test", "email": "test@example.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/api/auth/register",
        json={"username": "dup", "email": "dup@example.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/register",
        json={"username": "dup", "email": "dup@example.com", "password": "anotherpass456"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client):
    res = await client.post(
        "/api/auth/register",
        json={"username": "short", "email": "short@example.com", "password": "abc"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_normal_password(client):
    """A normal, short (8-20 char) ASCII password should register fine."""
    res = await client.post(
        "/api/auth/register",
        json={"username": "normal", "email": "normal@example.com", "password": "goodpass123"},
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
        json={"username": "seventytwo", "email": "seventytwo@example.com", "password": password},
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
        json={"username": "seventythree", "email": "seventythree@example.com", "password": password},
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
        json={"username": "multibyte", "email": "multibyte@example.com", "password": password},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/auth/register",
        json={"username": "login", "email": "login@test.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"username": "login", "email": "login@test.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    await client.post(
        "/api/auth/register",
        json={"username": "badpw", "email": "badpw@test.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"username": "badpw", "email": "badpw@test.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    res = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "email": "nobody@test.com", "password": "whatever"},
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
        json={"username": "valid", "email": "valid@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"username": "valid", "email": "valid@test.com", "password": "securepass123"},
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
        json={"username": "bill", "email": "bill@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"username": "bill", "email": "bill@test.com", "password": "securepass123"},
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
        json={"username": "disabled", "email": "disabled@test.com", "password": "securepass123"},
    )
    login_res = await client.post(
        "/api/auth/login",
        json={"username": "disabled", "email": "disabled@test.com", "password": "securepass123"},
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


@pytest.mark.asyncio
async def test_username_login_and_case_normalization(client):
    res = await client.post(
        "/api/auth/register",
        json={"username": "Mario.User", "email": "Mario.User@Example.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    assert res.json()["username"] == "mario.user"
    assert res.json()["email"] == "mario.user@example.com"

    login = await client.post(
        "/api/auth/login",
        json={"identifier": "MARIO.USER", "password": "securepass123"},
    )
    assert login.status_code == 200
    email_login = await client.post(
        "/api/auth/login",
        json={"email": "MARIO.USER@EXAMPLE.COM", "password": "securepass123"},
    )
    assert email_login.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_username_rejected(client):
    await client.post(
        "/api/auth/register",
        json={"username": "takenname", "email": "one@example.com", "password": "securepass123"},
    )
    res = await client.post(
        "/api/auth/register",
        json={"username": "TakenName", "email": "two@example.com", "password": "securepass123"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_invalid_login_is_generic(client):
    await client.post(
        "/api/auth/register",
        json={"username": "knownuser", "email": "known@example.com", "password": "securepass123"},
    )
    missing = await client.post("/api/auth/login", json={"identifier": "nope", "password": "securepass123"})
    wrong = await client.post("/api/auth/login", json={"identifier": "knownuser", "password": "nopexxxx"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["detail"] == "Invalid username/email or password."
    assert wrong.json()["detail"] == "Invalid username/email or password."


@pytest.mark.asyncio
async def test_oauth_only_user_password_login_is_generic(client):
    async with _TestSession() as db:
        db.add(User(email="oauthonly@example.com", hashed_password=None, username="oauthonly", is_active=True))
        await db.commit()
    res = await client.post(
        "/api/auth/login",
        json={"identifier": "oauthonly", "password": "anything1"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username/email or password."


@pytest.mark.asyncio
async def test_legacy_user_without_username_can_email_login(client):
    from api.auth import hash_password
    async with _TestSession() as db:
        db.add(User(email="legacy@example.com", hashed_password=hash_password("securepass123"), username=None, is_active=True))
        await db.commit()
    res = await client.post(
        "/api/auth/login",
        json={"email": "legacy@example.com", "password": "securepass123"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    claim = await client.post(
        "/api/auth/username",
        json={"username": "legacyfan"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert claim.status_code == 200
    assert claim.json()["username"] == "legacyfan"
    again = await client.post(
        "/api/auth/username",
        json={"username": "newnameok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_providers_report_oauth_and_username(client):
    res = await client.get("/api/auth/providers")
    assert res.status_code == 200
    body = res.json()
    assert body["username_login"]["enabled"] is True
    assert body["google"]["configured"] is False
    assert body["apple"]["configured"] is False
    assert body["password_reset"]["enabled"] is False


@pytest.mark.asyncio
async def test_username_available_endpoint(client):
    await client.post(
        "/api/auth/register",
        json={"username": "availme", "email": "avail@example.com", "password": "securepass123"},
    )
    taken = await client.get("/api/auth/username/available", params={"u": "AvailMe"})
    free = await client.get("/api/auth/username/available", params={"u": "newhandle"})
    bad = await client.get("/api/auth/username/available", params={"u": "ab"})
    assert taken.json()["available"] is False
    assert free.json()["available"] is True
    assert bad.json()["available"] is False