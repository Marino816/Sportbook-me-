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
from datetime import datetime, timedelta, timezone

from models.domain import User, Subscription, StripeEvent, RevenueLog, BillingEntitlement
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
    await client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
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
            mrr_value=49.99,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        res = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["plan"] == "Pro Arena"
        assert data["amount"] == 49.99
        assert data["billing_interval"] == "monthly"
        assert data["provider"] == "stripe"
        assert data["purchases_paused"] is True

    async def test_status_paykings_subscription(self, client):
        token = await _register_and_login(client, "pk@test.com")
        await _create_sub_async(
            "pk@test.com",
            plan_name="Pro Arena",
            status="active",
            mrr_value=49.99,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=29),
            cancel_at_period_end=True,
        )
        paid_through = datetime(2026, 11, 17, tzinfo=timezone.utc)
        async with _TestSession() as db:
            user = (await db.execute(sa_select(User).where(User.email == "pk@test.com"))).scalars().first()
            db.add(BillingEntitlement(
                user_id=user.id,
                provider="paykings",
                provider_subscription_id="12574008155",
                provider_plan_id="SBME_PRO_MONTHLY",
                checkout_reference="pkchk_test",
                tier="pro",
                billing_period="monthly",
                status="active",
                paid_verified=True,
                current_period_end=paid_through,
                canceled_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
                last_successful_transaction_id="12695555360",
            ))
            await db.commit()
        res = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["plan"] == "Pro Arena"
        assert data["amount"] == 49.99
        assert data["billing_interval"] == "monthly"
        assert data["provider"] == "paykings"
        assert data["is_canceled"] is True
        assert data["renewal_status"] == "canceled"
        assert data["has_access"] is True
        assert data["next_billing"] is None
        assert data["paid_through"].startswith("2026-11-17")
        assert data["can_cancel"] is False


class TestCheckout:
    """POST /api/billing/checkout"""

    async def test_checkout_requires_auth(self, client):
        res = await client.post("/api/billing/checkout", json={"plan": "Pro Arena"})
        assert res.status_code == 401

    @patch("services.stripe_service.stripe.checkout.Session.create")
    async def test_checkout_paused(self, mock_create, client):
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/test")
        token = await _register_and_login(client, "buyer@test.com")
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "Pro Arena"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert "paused" in res.json()["detail"].lower()
        mock_create.assert_not_called()

    async def test_checkout_invalid_plan_paused(self, client):
        token = await _register_and_login(client, "badplan@test.com")
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "Nonexistent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


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


class TestCancel:
    """POST /api/billing/cancel"""

    async def test_cancel_requires_confirmation(self, client):
        token = await _register_and_login(client, "noconfirm@test.com")
        res = await client.post(
            "/api/billing/cancel",
            json={"confirm": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "Confirmation required" in res.json()["detail"]

    async def test_cancel_success_only_after_processor(self, client):
        token = await _register_and_login(client, "cancelok@test.com")
        await _create_sub_async(
            "cancelok@test.com",
            plan_name="Pro Arena",
            status="active",
            mrr_value=49.99,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=29),
        )
        async with _TestSession() as db:
            user = (await db.execute(sa_select(User).where(User.email == "cancelok@test.com"))).scalars().first()
            db.add(BillingEntitlement(
                user_id=user.id,
                provider="paykings",
                provider_subscription_id="sub-live",
                provider_plan_id="SBME_PRO_MONTHLY",
                checkout_reference="pkchk_cancel_ok",
                tier="pro",
                billing_period="monthly",
                status="active",
                paid_verified=True,
                current_period_end=datetime.now(timezone.utc) + timedelta(days=29),
            ))
            await db.commit()

        class _Parsed:
            approved = True
            responsetext = "Recurring Transaction Deleted"
            response_code = "100"
            subscription_id = "sub-live"

        class _Client:
            async def delete_subscription(self, subscription_id):
                assert subscription_id == "sub-live"
                return _Parsed()

            async def query_subscription(self, subscription_id):
                return None

        with patch("services.billing_account.PayKingsRecurringClient", return_value=_Client()):
            res = await client.post(
                "/api/billing/cancel",
                json={"confirm": True},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["processor_confirmed"] is True
        assert data["is_canceled"] is True
        assert data["has_access"] is True
        assert data["renewal_status"] == "canceled"

    async def test_cancel_does_not_report_success_on_processor_failure(self, client):
        from services.paykings_recurring import PayKingsProviderError, PayKingsTransactResponse

        token = await _register_and_login(client, "cancelfail@test.com")
        await _create_sub_async(
            "cancelfail@test.com",
            plan_name="Pro Arena",
            status="active",
            mrr_value=49.99,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=29),
        )
        async with _TestSession() as db:
            user = (await db.execute(sa_select(User).where(User.email == "cancelfail@test.com"))).scalars().first()
            db.add(BillingEntitlement(
                user_id=user.id,
                provider="paykings",
                provider_subscription_id="sub-fail",
                provider_plan_id="SBME_PRO_MONTHLY",
                checkout_reference="pkchk_cancel_fail",
                tier="pro",
                billing_period="monthly",
                status="active",
                paid_verified=True,
                current_period_end=datetime.now(timezone.utc) + timedelta(days=29),
            ))
            await db.commit()

        class _Client:
            async def delete_subscription(self, subscription_id):
                raise PayKingsProviderError(
                    "paykings_not_approved",
                    PayKingsTransactResponse(raw="response=2", response="2", responsetext="Declined"),
                )

        with patch("services.billing_account.PayKingsRecurringClient", return_value=_Client()):
            res = await client.post(
                "/api/billing/cancel",
                json={"confirm": True},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 502
        assert "Processor did not confirm" in res.json()["detail"]