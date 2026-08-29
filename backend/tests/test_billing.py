"""
Billing integration tests for Sportsbook Me DFS AI.

Run isolated: pytest tests/test_billing.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User, Subscription, StripeEvent, RevenueLog
from services.stripe_service import StripeService

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


async def _register_and_login(client, email):
    await client.post("/api/auth/register", json={"email": email, "username": "".join(ch for ch in email.split("@")[0] if ch.isalnum())[:24].ljust(3,"x"), "password": "securepass123"})
    res = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return res.json()["access_token"]


def _get_user_sync(db, email):
    return db.query(User).filter(User.email == email).first()


async def _get_user_async(email):
    async with _TestSession() as db:
        result = await db.execute(sa_select(User).where(User.email == email))
        return result.scalars().first()


async def _set_attr_async(email, **kwargs):
    """Set attributes on a User ORM instance via async session."""
    async with _TestSession() as db:
        result = await db.execute(sa_select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            for key, val in kwargs.items():
                setattr(user, key, val)
            await db.commit()


async def _create_sub_async(email, **kwargs):
    """Create a Subscription and link it to the user."""
    async with _TestSession() as db:
        result = await db.execute(sa_select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            return None
        sub = Subscription(user_id=user.id, **kwargs)
        db.add(sub)
        await db.commit()
        user.active_subscription_id = sub.id
        await db.commit()
        return sub


class TestBillingStatus:
    """GET /api/billing/status"""

    async def test_status_free_user(self, client):
        token = await _register_and_login(client, "free@test.com")
        res = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["plan"] == "Starter"
        assert data["has_access"] == False

    async def test_status_requires_auth(self, client):
        res = await client.get("/api/billing/status")
        assert res.status_code == 401

    async def test_status_with_active_subscription(self, client):
        token = await _register_and_login(client, "pro@test.com")
        await _create_sub_async(
            "pro@test.com",
            plan_name="Pro Arena", status="active",
            stripe_subscription_id="sub_test_123",
        )
        res = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["plan"] == "Pro Arena"


class TestCheckout:
    """POST /api/billing/checkout"""

    async def test_checkout_requires_auth(self, client):
        res = await client.post("/api/billing/checkout", json={"plan": "Pro Arena"})
        assert res.status_code == 401

    @patch("services.stripe_service.stripe.checkout.Session.create")
    async def test_checkout_creates_session(self, mock_create, client):
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/test")
        token = await _register_and_login(client, "buyer@test.com")
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "Pro Arena"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert "checkout.stripe.com" in res.json()["data"]["url"]

    async def test_checkout_invalid_plan(self, client):
        token = await _register_and_login(client, "badplan@test.com")
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "Nonexistent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400


class TestPortal:
    """GET /api/billing/portal"""

    async def test_portal_requires_auth(self, client):
        res = await client.get("/api/billing/portal")
        assert res.status_code == 401

    async def test_portal_no_customer(self, client):
        token = await _register_and_login(client, "nocust@test.com")
        res = await client.get("/api/billing/portal", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 400
        assert "No active Stripe customer" in res.json()["detail"]

    @patch("services.stripe_service.stripe.billing_portal.Session.create")
    async def test_portal_creates_session(self, mock_create, client):
        mock_create.return_value = MagicMock(url="https://billing.stripe.com/test")
        token = await _register_and_login(client, "portal@test.com")
        await _set_attr_async("portal@test.com", stripe_customer_id="cus_test")
        res = await client.get("/api/billing/portal", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert "billing.stripe.com" in res.json()["data"]["url"]


# ── Webhook Tests (require mocked SyncSessionLocal) ──────────

@pytest.fixture
def mock_sync_session(monkeypatch):
    """Replace SyncSessionLocal with a function that returns an async session."""
    from models import database as db_module

    original = db_module.SyncSessionLocal

    def _fake_sync_session():
        import asyncio
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_TestSession().__aenter__())

    def _fake_close(self):
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_TestSession().__aexit__(None, None, None))

    # Patch the module-level reference in billing.py
    import api.billing as billing_module
    monkeypatch.setattr(billing_module, "SyncSessionLocal", _fake_sync_session)
    # Also patch the service to use a mock DB session
    monkeypatch.setattr(
        "services.stripe_service.stripe.Webhook.construct_event",
        lambda *a, **kw: MagicMock(),
    )
    yield
    monkeypatch.undo()


class TestWebhookIdempotency:
    """POST /api/billing/webhook — idempotency via StripeEvent"""

    @patch("services.stripe_service.stripe.Webhook.construct_event")
    async def test_webhook_invalid_signature(self, mock_construct, client):
        mock_construct.side_effect = ValueError("Invalid signature")
        res = await client.post(
            "/api/billing/webhook",
            content=b'{"id":"x"}',
            headers={"stripe-signature": "bad"},
        )
        assert res.status_code == 400
        assert "Invalid Webhook" in res.json()["detail"]