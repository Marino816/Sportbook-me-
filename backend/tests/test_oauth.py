import pytest
from httpx import ASGITransport, AsyncClient

from tests.auth_app import TestSession as _TestSession
from tests.auth_app import auth_app as app
from tests.auth_app import reset_auth_db
from models.domain import User
from api.auth import hash_password
from identity import resolve_oauth_account
from api import oauth as oauth_mod


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


def _google_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://sportbook-me-production.up.railway.app/api/auth/oauth/google/callback",
    )


@pytest.mark.asyncio
async def test_oauth_start_501_without_credentials(client):
    res = await client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert res.status_code == 501
    apple = await client.get("/api/auth/oauth/apple/start", follow_redirects=False)
    assert apple.status_code == 501


@pytest.mark.asyncio
async def test_google_start_redirects_when_configured(client, monkeypatch):
    _google_env(monkeypatch)
    res = await client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert res.status_code == 302
    assert "accounts.google.com" in res.headers["location"]
    assert "code_challenge" in res.headers["location"]
    assert "sbme_oauth" in res.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_google_state_mismatch_rejected(client, monkeypatch):
    _google_env(monkeypatch)
    start = await client.get("/api/auth/oauth/google/start", follow_redirects=False)
    cookie = start.headers["set-cookie"].split(";", 1)[0]
    res = await client.get(
        "/api/auth/oauth/google/callback",
        params={"code": "abc", "state": "not-the-state"},
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_oauth_links_existing_verified_email():
    async with _TestSession() as db:
        user = User(
            email="linked@example.com",
            hashed_password=hash_password("securepass123"),
            username="already",
            is_active=True,
            is_pro=True,
            role="user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        resolved, created = await resolve_oauth_account(
            db,
            provider="google",
            subject="google-sub-1",
            email="Linked@Example.com",
            email_verified=True,
        )
        assert created is False
        assert resolved.id == user.id
        assert resolved.username == "already"
        assert resolved.is_pro is True


@pytest.mark.asyncio
async def test_oauth_creates_new_user_without_username():
    async with _TestSession() as db:
        resolved, created = await resolve_oauth_account(
            db,
            provider="google",
            subject="google-sub-new",
            email="newoauth@example.com",
            email_verified=True,
        )
        assert created is True
        assert resolved.email == "newoauth@example.com"
        assert resolved.username is None
        assert resolved.role == "user"
        assert resolved.hashed_password is None


@pytest.mark.asyncio
async def test_duplicate_provider_subject_reuses_same_user():
    async with _TestSession() as db:
        first, created = await resolve_oauth_account(
            db,
            provider="google",
            subject="same-sub",
            email="first@example.com",
            email_verified=True,
        )
        assert created is True
        second, created2 = await resolve_oauth_account(
            db,
            provider="google",
            subject="same-sub",
            email="other@example.com",
            email_verified=True,
        )
        assert created2 is False
        assert second.id == first.id


@pytest.mark.asyncio
async def test_unverified_email_does_not_merge():
    async with _TestSession() as db:
        db.add(User(email="real@example.com", hashed_password=hash_password("securepass123")))
        await db.commit()
        with pytest.raises(Exception):
            await resolve_oauth_account(
                db,
                provider="apple",
                subject="apple-sub",
                email="real@example.com",
                email_verified=False,
            )


def test_google_identity_rejects_wrong_audience():
    from jose import jwt as jose_jwt
    token = jose_jwt.encode(
        {"iss": "https://accounts.google.com", "aud": "other", "sub": "s", "email": "a@b.com", "email_verified": True},
        "x",
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        oauth_mod.validate_google_identity(token, client_id="google-client")


def test_apple_client_secret_helpers_require_es256_inputs():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    secret = oauth_mod.build_apple_client_secret(
        team_id="TEAMID",
        client_id="com.sbme.web",
        key_id="KEYID",
        private_key=pem,
        now=1_700_000_000,
    )
    from jose import jwt as jose_jwt
    payload = jose_jwt.get_unverified_claims(secret)
    assert payload["iss"] == "TEAMID"
    assert payload["sub"] == "com.sbme.web"
    assert payload["aud"] == "https://appleid.apple.com"


def test_oauth_state_roundtrip():
    signed = oauth_mod.sign_oauth_state({"state": "abc", "provider": "google"})
    payload = oauth_mod.validate_oauth_state(signed, "abc")
    assert payload["provider"] == "google"
    with pytest.raises(Exception):
        oauth_mod.validate_oauth_state(signed, "nope")
