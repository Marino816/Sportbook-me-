"""PayKings checkout binding: pending records, plan mapping, resolution. No entitlements."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from models.database import Base, get_db
from models.domain import BillingCheckout, PaymentWebhookEvent, User
from services.paykings_billing import (
    CHECKOUT_REFERENCE_PREFIX,
    ORDER_ID_RECURRING_CORRELATION_ENABLED,
    PROVIDER,
    STATUS_BOUND,
    STATUS_DELETE_RECORDED,
    attach_provider_identifiers,
    is_paykings_test_event,
    reject_test_mode_for_production_entitlement,
    resolve_billing_checkout,
    resolve_for_cancellation,
)
from services.paykings_client import PayKingsTransactResponse, parse_transact_response
from services.paykings_plans import SBME_PLANS, get_plan
from services.paykings_webhooks import (
    EVENT_RECURRING_CANCELED,
    EVENT_RECURRING_CREATED,
    EVENT_RECURRING_UPDATED,
    compute_signature,
)

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TestSession() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if previous is not None:
        app.dependency_overrides[get_db] = previous
    else:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_login(client, email: str) -> str:
    username = "".join(ch for ch in email.split("@")[0] if ch.isalnum())[:24].ljust(3, "x")
    await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": "securepass123"},
    )
    res = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return res.json()["access_token"]


async def _user_by_email(email: str) -> User:
    async with _TestSession() as db:
        return (await db.execute(select(User).where(User.email == email))).scalars().one()


async def test_unauthenticated_checkout_rejected(client):
    res = await client.post("/api/billing/paykings/checkout", json={"plan_id": "SBME_PRO_MONTHLY"})
    assert res.status_code in (401, 403)


async def test_unsupported_plan_rejected(client):
    token = await _register_and_login(client, "badplan@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "NOT_A_PLAN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "Unsupported plan_id" in res.json()["detail"]


@pytest.mark.parametrize("plan_id", list(SBME_PLANS))
async def test_valid_plan_creates_pending_record(client, plan_id):
    token = await _register_and_login(client, f"{plan_id.lower()}@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": plan_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    plan = get_plan(plan_id)
    assert data["plan_id"] == plan_id
    assert data["tier"] == plan.tier
    assert data["billing_period"] == plan.billing_period
    assert data["expected_price"] == float(plan.expected_price)
    assert data["provider"] == "paykings"
    assert data["status"] == "pending"
    assert data["checkout_reference"].startswith(CHECKOUT_REFERENCE_PREFIX)
    assert "user_id" not in data
    assert "id" not in data
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.status == "pending"
        assert row.provider == "paykings"
        assert row.provider_plan_id == plan_id
        assert row.tier == plan.tier
        assert row.billing_period == plan.billing_period


async def test_checkout_reference_unique_and_not_user_id(client):
    token = await _register_and_login(client, "unique@test.com")
    refs = []
    for _ in range(2):
        res = await client.post(
            "/api/billing/paykings/checkout",
            json={"plan_id": "SBME_PRO_MONTHLY"},
            headers={"Authorization": f"Bearer {token}"},
        )
        refs.append(res.json()["data"]["checkout_reference"])
    assert refs[0] != refs[1]
    user = await _user_by_email("unique@test.com")
    for ref in refs:
        assert ref != str(user.id)
        assert ref.startswith("pkchk_")
        assert len(ref) == len("pkchk_") + 32
    async with _TestSession() as db:
        count = (await db.execute(select(func.count()).select_from(BillingCheckout))).scalar_one()
        assert count == 2


async def test_user_id_comes_from_auth_not_request_body(client):
    token_a = await _register_and_login(client, "alice@test.com")
    user_b = await _register_and_login(client, "bob@test.com")
    bob = await _user_by_email("bob@test.com")
    alice = await _user_by_email("alice@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_ELITE_MONTHLY", "user_id": bob.id, "tier": "elite", "price": 0.01},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.user_id == alice.id
        assert row.user_id != bob.id
        assert row.tier == "elite"
        assert row.provider_plan_id == "SBME_ELITE_MONTHLY"
    assert user_b  # login succeeded for the other user; unused beyond that


async def test_server_determines_tier_period_and_price(client):
    token = await _register_and_login(client, "servermap@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={
            "plan_id": "SBME_PRO_ANNUAL",
            "tier": "elite",
            "billing_period": "monthly",
            "expected_price": 1.00,
            "price": 1.00,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["tier"] == "pro"
    assert data["billing_period"] == "annual"
    assert data["expected_price"] == 399.99


async def test_frontend_price_cannot_override_plan_price(client):
    token = await _register_and_login(client, "pricehack@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_ELITE_ANNUAL", "expected_price": 0.01, "amount": "0.01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["data"]["expected_price"] == 599.99
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.provider_plan_id == "SBME_ELITE_ANNUAL"
        assert row.tier == "elite"


async def test_pending_record_does_not_grant_entitlement(client):
    token = await _register_and_login(client, "noaccess@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    user = await _user_by_email("noaccess@test.com")
    assert user.is_pro is False
    assert user.active_subscription_id is None
    status = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert status.json()["data"]["has_access"] is False
    assert status.json()["data"]["plan"] == "Starter"


async def test_duplicate_provider_subscription_id_cannot_map_two_users(client):
    await _register_and_login(client, "one@test.com")
    await _register_and_login(client, "two@test.com")
    u1 = await _user_by_email("one@test.com")
    u2 = await _user_by_email("two@test.com")
    async with _TestSession() as db:
        db.add(BillingCheckout(
            user_id=u1.id, provider="paykings", checkout_reference="pkchk_aaa",
            provider_plan_id="SBME_PRO_MONTHLY", tier="pro", billing_period="monthly",
            status="pending", provider_subscription_id="sub-shared",
        ))
        await db.commit()
        db.add(BillingCheckout(
            user_id=u2.id, provider="paykings", checkout_reference="pkchk_bbb",
            provider_plan_id="SBME_ELITE_MONTHLY", tier="elite", billing_period="monthly",
            status="pending", provider_subscription_id="sub-shared",
        ))
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_unknown_webhook_subscription_id_cannot_resolve_user():
    async with _TestSession() as db:
        resolved = await resolve_billing_checkout(db, provider_subscription_id="sub-unknown")
        assert resolved is None
        canceled = await resolve_for_cancellation(db, "sub-unknown")
        assert canceled is None


async def test_known_provider_subscription_id_resolves_exactly_one_user(client):
    token = await _register_and_login(client, "bound@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user = await _user_by_email("bound@test.com")
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        await attach_provider_identifiers(db, row, provider_subscription_id="sub-bound-1")
        found = await resolve_billing_checkout(db, provider_subscription_id="sub-bound-1")
        assert found is not None
        assert found.user_id == user.id
        assert found.checkout_reference == res.json()["data"]["checkout_reference"]
        only = await resolve_for_cancellation(db, "sub-bound-1")
        assert only.id == found.id


async def test_order_id_correlation_resolves_checkout(client):
    token = await _register_and_login(client, "ordercor@test.com")
    res = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ref = res.json()["data"]["checkout_reference"]
    assert ORDER_ID_RECURRING_CORRELATION_ENABLED is True
    async with _TestSession() as db:
        found = await resolve_billing_checkout(db, checkout_reference=ref)
        assert found is not None
        assert found.checkout_reference == ref


def test_test_mode_blocks_future_production_entitlement():
    assert is_paykings_test_event({"features": {"is_test_mode": True}}) is True
    assert reject_test_mode_for_production_entitlement({"is_test_mode": True}) is True
    assert reject_test_mode_for_production_entitlement({"features": {"is_test_mode": False}}) is False
    assert reject_test_mode_for_production_entitlement({}) is False


TEST_SIGNING_KEY = "test-paykings-webhook-signing-key"
TEST_SECURITY_KEY = "test-paykings-security-key"


class _FakePayKingsClient:
    def __init__(self):
        self.calls = []

    async def create_subscription(self, *, plan_id, payment_token, order_id):
        self.calls.append({
            "recurring": "add_subscription",
            "plan_id": plan_id,
            "payment_token": payment_token,
            "orderid": order_id,
        })
        return PayKingsTransactResponse(
            raw=f"response=1&responsetext=Approved&transactionid=txn-1&orderid={order_id}",
            response="1",
            responsetext="Approved",
            transactionid="txn-1",
            orderid=order_id,
        )


def _sign(body: bytes, nonce: str = "test-nonce") -> str:
    sig = compute_signature(TEST_SIGNING_KEY, nonce, body)
    return f"t={nonce},s={sig}"


@pytest.fixture
def fake_paykings(monkeypatch):
    fake = _FakePayKingsClient()
    monkeypatch.setenv("PAYKINGS_SECURITY_KEY", TEST_SECURITY_KEY)
    monkeypatch.setenv("PAYKINGS_WEBHOOK_SIGNING_KEY", TEST_SIGNING_KEY)
    monkeypatch.setattr("services.paykings_billing.PayKingsClient", lambda *a, **k: fake)
    return fake


async def test_subscribe_uses_server_checkout_reference_as_orderid(client, fake_paykings, caplog):
    token = await _register_and_login(client, "subuser@test.com")
    user = await _user_by_email("subuser@test.com")
    res = await client.post(
        "/api/billing/paykings/subscribe",
        json={
            "plan_id": "SBME_PRO_MONTHLY",
            "payment_token": "tok_collect_once",
            "orderid": str(user.id),
            "user_id": 999999,
            "tier": "elite",
            "price": 0.01,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    ref = data["checkout_reference"]
    assert ref.startswith("pkchk_")
    assert len(ref) == len("pkchk_") + 32
    assert ref != str(user.id)
    assert data["tier"] == "pro"
    assert data["expected_price"] == 49.99
    assert data["status"] == "submitted"
    assert fake_paykings.calls[0]["recurring"] == "add_subscription"
    assert fake_paykings.calls[0]["plan_id"] == "SBME_PRO_MONTHLY"
    assert fake_paykings.calls[0]["payment_token"] == "tok_collect_once"
    assert fake_paykings.calls[0]["orderid"] == ref
    assert fake_paykings.calls[0]["orderid"] != str(user.id)
    assert "tok_collect_once" not in caplog.text
    assert TEST_SECURITY_KEY not in caplog.text
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.checkout_reference == ref
        assert row.user_id == user.id
        dumped = json.dumps(row.__dict__, default=str)
        assert "tok_collect_once" not in dumped
        assert row.provider_transaction_id == "txn-1"
        user_row = (await db.execute(select(User).where(User.id == user.id))).scalars().one()
        assert user_row.is_pro is False
        assert user_row.active_subscription_id is None


async def test_subscribe_rejects_unsupported_plan(client, fake_paykings):
    token = await _register_and_login(client, "badsub@test.com")
    res = await client.post(
        "/api/billing/paykings/subscribe",
        json={"plan_id": "NOPE", "payment_token": "tok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert fake_paykings.calls == []


async def test_subscribe_requires_payment_token(client, fake_paykings):
    token = await _register_and_login(client, "notoken@test.com")
    res = await client.post(
        "/api/billing/paykings/subscribe",
        json={"plan_id": "SBME_PRO_MONTHLY", "payment_token": "  "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert fake_paykings.calls == []


async def test_subscribe_unauthenticated_rejected(client):
    res = await client.post(
        "/api/billing/paykings/subscribe",
        json={"plan_id": "SBME_PRO_MONTHLY", "payment_token": "tok"},
    )
    assert res.status_code in (401, 403)


def test_parse_documented_transact_response():
    parsed = parse_transact_response(
        "response=1&responsetext=Approved&transactionid=555&orderid=pkchk_abc&response_code=100"
    )
    assert parsed.approved is True
    assert parsed.transactionid == "555"
    assert parsed.orderid == "pkchk_abc"
    assert parsed.subscription_id is None


def test_build_add_subscription_fields():
    from services.paykings_client import build_add_subscription_fields
    fields = build_add_subscription_fields(
        plan_id="SBME_ELITE_MONTHLY",
        payment_token="tok_x",
        order_id="pkchk_abc",
        key="sec",
    )
    assert fields == {
        "security_key": "sec",
        "recurring": "add_subscription",
        "plan_id": "SBME_ELITE_MONTHLY",
        "payment_token": "tok_x",
        "orderid": "pkchk_abc",
    }
    assert "ccnumber" not in fields
    assert "ccexp" not in fields
    assert "cvv" not in fields


async def _post_signed_webhook(client, payload: dict):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body), "Content-Type": "application/json"},
    )


async def test_webhook_add_resolves_order_id_and_binds_subscription(client, fake_paykings):
    token = await _register_and_login(client, "bindme@test.com")
    checkout = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ref = checkout.json()["data"]["checkout_reference"]
    user = await _user_by_email("bindme@test.com")
    res = await _post_signed_webhook(client, {
        "event_id": "evt-bind-1",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref,
            "subscription_id": "sub-new-1",
            "plan": {"id": "SBME_PRO_MONTHLY", "name": "Pro Arena", "amount": "49.99"},
        },
    })
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.provider_subscription_id == "sub-new-1"
        assert row.status == STATUS_BOUND
        assert row.user_id == user.id
        evt = (await db.execute(select(PaymentWebhookEvent))).scalars().one()
        assert evt.processing_status == "processed"
        stored = json.dumps(row.__dict__, default=str)
        assert "tok_" not in stored
        u = (await db.execute(select(User).where(User.id == user.id))).scalars().one()
        assert u.is_pro is False


async def test_webhook_plan_must_match_checkout_plan(client, fake_paykings):
    token = await _register_and_login(client, "mismatch@test.com")
    checkout = await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ref = checkout.json()["data"]["checkout_reference"]
    res = await _post_signed_webhook(client, {
        "event_id": "evt-mismatch",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref,
            "subscription_id": "sub-mismatch",
            "plan": {"id": "SBME_ELITE_MONTHLY", "name": "Elite Stack", "amount": "89.99"},
        },
    })
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.provider_subscription_id is None
        assert row.status == "error"
        evt = (await db.execute(select(PaymentWebhookEvent))).scalars().one()
        assert evt.processing_status == "error"


async def test_duplicate_subscription_id_rejected_safely(client, fake_paykings):
    token_a = await _register_and_login(client, "dupa@test.com")
    token_b = await _register_and_login(client, "dupb@test.com")
    ref_a = (await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token_a}"},
    )).json()["data"]["checkout_reference"]
    ref_b = (await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token_b}"},
    )).json()["data"]["checkout_reference"]
    await _post_signed_webhook(client, {
        "event_id": "evt-dup-a",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref_a,
            "subscription_id": "sub-only-one",
            "plan": {"id": "SBME_PRO_MONTHLY", "amount": "49.99"},
        },
    })
    await _post_signed_webhook(client, {
        "event_id": "evt-dup-b",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref_b,
            "subscription_id": "sub-only-one",
            "plan": {"id": "SBME_PRO_MONTHLY", "amount": "49.99"},
        },
    })
    user_a = await _user_by_email("dupa@test.com")
    user_b = await _user_by_email("dupb@test.com")
    async with _TestSession() as db:
        rows = (await db.execute(select(BillingCheckout))).scalars().all()
        by_ref = {r.checkout_reference: r for r in rows}
        assert by_ref[ref_a].provider_subscription_id == "sub-only-one"
        assert by_ref[ref_a].user_id == user_a.id
        assert by_ref[ref_b].provider_subscription_id is None
        assert by_ref[ref_b].user_id == user_b.id


async def test_update_and_delete_resolve_by_subscription_id(client, fake_paykings):
    token = await _register_and_login(client, "updel@test.com")
    ref = (await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_ELITE_ANNUAL"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()["data"]["checkout_reference"]
    await _post_signed_webhook(client, {
        "event_id": "evt-updel-add",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref,
            "subscription_id": "sub-updel",
            "plan": {"id": "SBME_ELITE_ANNUAL", "amount": "599.99"},
        },
    })
    upd = await _post_signed_webhook(client, {
        "event_id": "evt-updel-upd",
        "event_type": EVENT_RECURRING_UPDATED,
        "event_body": {
            "subscription_id": "sub-updel",
            "plan": {"id": "SBME_ELITE_ANNUAL", "amount": "599.99"},
        },
    })
    assert upd.status_code == 200
    user = await _user_by_email("updel@test.com")
    async with _TestSession() as db:
        u = (await db.execute(select(User).where(User.id == user.id))).scalars().one()
        assert u.is_pro is False
    deleted = await _post_signed_webhook(client, {
        "event_id": "evt-updel-del",
        "event_type": EVENT_RECURRING_CANCELED,
        "event_body": {"subscription_id": "sub-updel"},
    })
    assert deleted.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(BillingCheckout))).scalars().one()
        assert row.status == STATUS_DELETE_RECORDED
        u = (await db.execute(select(User).where(User.id == user.id))).scalars().one()
        assert u.is_pro is False
        assert u.active_subscription_id is None


async def test_unknown_subscription_cannot_revoke_user(client, fake_paykings):
    token = await _register_and_login(client, "keeppro@test.com")
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "keeppro@test.com"))).scalars().one()
        user.is_pro = True
        await db.commit()
    res = await _post_signed_webhook(client, {
        "event_id": "evt-unknown-del",
        "event_type": EVENT_RECURRING_CANCELED,
        "event_body": {"subscription_id": "sub-does-not-exist"},
    })
    assert res.status_code == 200
    async with _TestSession() as db:
        evt = (await db.execute(select(PaymentWebhookEvent))).scalars().one()
        assert evt.processing_status == "unresolved"
        u = (await db.execute(select(User).where(User.email == "keeppro@test.com"))).scalars().one()
        assert u.is_pro is True


async def test_test_mode_webhook_does_not_grant_access(client, fake_paykings):
    token = await _register_and_login(client, "testmode@test.com")
    ref = (await client.post(
        "/api/billing/paykings/checkout",
        json={"plan_id": "SBME_PRO_MONTHLY"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()["data"]["checkout_reference"]
    await _post_signed_webhook(client, {
        "event_id": "evt-test-mode",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "order_id": ref,
            "subscription_id": "sub-test-mode",
            "plan": {"id": "SBME_PRO_MONTHLY", "amount": "49.99"},
            "features": {"is_test_mode": True},
        },
    })
    user = await _user_by_email("testmode@test.com")
    assert user.is_pro is False
    assert reject_test_mode_for_production_entitlement({"features": {"is_test_mode": True}}) is True
