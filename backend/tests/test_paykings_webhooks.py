"""PayKings webhook receiver: HMAC verification, idempotency, no entitlement writes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from models.database import Base, get_db
from models.domain import PaymentWebhookEvent, Subscription, User
from services.paykings_webhooks import (
    EVENT_ACU_AUTOMATICALLY_UPDATED,
    EVENT_ACU_CLOSED_ACCOUNT,
    EVENT_ACU_CONTACT_CUSTOMER,
    EVENT_RECURRING_CANCELED,
    EVENT_RECURRING_CREATED,
    EVENT_RECURRING_UPDATED,
    EVENT_TRANSACTION_FAILURE,
    EVENT_TRANSACTION_REFUND_FAILURE,
    EVENT_TRANSACTION_REFUND_SUCCESS,
    EVENT_TRANSACTION_SUCCESS,
    EVENT_TRANSACTION_UNKNOWN,
    SUBSCRIBED_EVENT_TYPES,
    SBME_PLAN_IDS,
    compute_signature,
    dispatch_event,
    extract_confirmed_fields,
    handle_recurring_canceled,
    handle_recurring_created,
    handle_transaction_refund_success,
    handle_transaction_success,
    operational_payload,
    parse_signature_header,
    recognized_sbme_plan_id,
    sanitize_payload,
    signing_key,
)

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_SIGNING_KEY = "test-paykings-webhook-signing-key"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TestSession() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup(monkeypatch):
    monkeypatch.setenv("PAYKINGS_WEBHOOK_SIGNING_KEY", TEST_SIGNING_KEY)
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


def _sign(body: bytes, nonce: str = "test-nonce") -> str:
    sig = compute_signature(TEST_SIGNING_KEY, nonce, body)
    return f"t={nonce},s={sig}"


def _payload(**extra) -> bytes:
    data = {
        "event_id": "evt-paykings-001",
        "event_type": EVENT_TRANSACTION_SUCCESS,
        "transaction_id": "txn-1001",
        "customerid": "cust-77",
        "order_id": "SBME_PRO_MONTHLY-order-1",
        "requested_amount": "49.99",
        "currency": "USD",
        "condition": "pendingsettlement",
        "transaction_type": "cc",
        "is_test_mode": False,
        "action": {
            "success": "1",
            "response_code": "100",
            "response_text": "Approved",
            "amount": "49.99",
        },
        "cc_number": "4111111111111111",
    }
    data.update(extra)
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


async def test_valid_signature_accepted(client, caplog):
    body = _payload()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert TEST_SIGNING_KEY not in caplog.text
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row is not None
        assert row.provider == "paykings"
        assert row.provider_event_id == "evt-paykings-001"
        assert row.idempotency_source == "event_id"
        assert row.event_type == EVENT_TRANSACTION_SUCCESS
        assert row.processing_status == "processed"
        assert row.processed_at is not None
        assert row.received_at is not None
        stored = row.sanitized_payload
        assert stored["event_id"] == "evt-paykings-001"
        assert stored["transaction_id"] == "txn-1001"
        assert stored["customerid"] == "cust-77"
        assert stored["order_id"] == "SBME_PRO_MONTHLY-order-1"
        assert stored["requested_amount"] == "49.99"
        assert stored["currency"] == "USD"
        assert stored["condition"] == "pendingsettlement"
        assert stored["transaction_type"] == "cc"
        assert stored["is_test_mode"] is False
        assert stored["action"] == {
            "success": "1",
            "response_code": "100",
            "response_text": "Approved",
        }
        assert "cc_number" not in stored
        assert "amount" not in stored.get("action", {})


async def test_invalid_signature_401(client):
    body = _payload()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": "t=test-nonce,s=" + ("0" * 64)},
    )
    assert res.status_code == 401


async def test_missing_signature_401(client):
    body = _payload()
    res = await client.post("/api/webhooks/paykings", content=body)
    assert res.status_code == 401


async def test_malformed_signature_401(client):
    body = _payload()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": "not-a-valid-header"},
    )
    assert res.status_code == 401


async def test_invalid_json_with_valid_signature_400(client):
    body = b"{not-json"
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 400
    assert "Invalid JSON" in res.json()["detail"]


async def test_duplicate_webhook_no_duplicate_processing(client, monkeypatch):
    calls = {"n": 0}
    orig = handle_transaction_success

    def counting(payload):
        calls["n"] += 1
        return orig(payload)

    monkeypatch.setattr("api.paykings_webhooks.dispatch_event", lambda event_type, payload: counting(payload))
    body = _payload()
    headers = {"Webhook-Signature": _sign(body), "Content-Type": "application/json"}
    first = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    second = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "success"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert calls["n"] == 1
    async with _TestSession() as db:
        count = (await db.execute(select(func.count()).select_from(PaymentWebhookEvent))).scalar_one()
        assert count == 1


async def test_raw_body_verification_rejects_canonicalized_json(client):
    """Signature is bound to exact bytes; pretty-printed JSON with same object fails."""
    compact = _payload()
    parsed = json.loads(compact)
    pretty = json.dumps(parsed, indent=2).encode("utf-8")
    # Sign compact, send pretty
    res = await client.post(
        "/api/webhooks/paykings",
        content=pretty,
        headers={"Webhook-Signature": _sign(compact)},
    )
    assert res.status_code == 401


async def test_signing_secret_never_logged(client, caplog):
    body = _payload()
    await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert TEST_SIGNING_KEY not in caplog.text
    assert "PAYKINGS_WEBHOOK_SIGNING_KEY" not in caplog.text or TEST_SIGNING_KEY not in caplog.text
    logged = caplog.text.lower()
    assert TEST_SIGNING_KEY.lower() not in logged


async def test_success_response_shape(client):
    body = _payload()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "success"}


async def test_nested_event_body_fields_are_persisted(client):
    body = json.dumps({
        "event_id": "evt-body-1",
        "event_type": EVENT_TRANSACTION_SUCCESS,
        "event_body": {
            "transaction_id": "txn-body",
            "customerid": "cust-body",
            "order_id": "ord-body",
            "requested_amount": "599.99",
            "currency": "USD",
            "condition": "pendingsettlement",
            "transaction_type": "cc",
            "is_test_mode": False,
            "action": {"success": "1", "response_code": "100", "response_text": "Approved"},
        },
    }, separators=(",", ":")).encode("utf-8")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row.provider_event_id == "evt-body-1"
        assert row.sanitized_payload["customerid"] == "cust-body"
        assert row.sanitized_payload["transaction_id"] == "txn-body"
        assert row.sanitized_payload["requested_amount"] == "599.99"


async def test_fingerprint_fallback_when_no_event_id(client):
    body = json.dumps({"event_type": EVENT_TRANSACTION_SUCCESS}).encode()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row.idempotency_source == "payload_sha256_fallback"
        assert row.provider_event_id == "sha256:" + hashlib.sha256(body).hexdigest()


async def test_sanitize_redacts_card_fields():
    cleaned = sanitize_payload({
        "event_id": "evt-1",
        "event_body": {"card": {"cc_number": "4111111111111111", "cvv": "123", "cc_exp": "1028"}},
    })
    assert cleaned["event_body"]["card"]["cc_number"] == "[redacted]"
    assert cleaned["event_body"]["card"]["cvv"] == "[redacted]"
    assert cleaned["event_body"]["card"]["cc_exp"] == "[redacted]"


def test_extract_confirmed_fields_top_level_and_nested_event_body():
    top = extract_confirmed_fields({
        "event_id": "evt-top",
        "event_type": EVENT_TRANSACTION_SUCCESS,
        "transaction_id": 9001,
        "customerid": 44,
        "order_id": "ord-1",
        "requested_amount": "89.99",
        "currency": "USD",
        "condition": "complete",
        "transaction_type": "cc",
        "is_test_mode": True,
        "action": {"success": "1", "response_code": "100", "response_text": "Approved"},
        "cc_number": "4111111111111111",
        "plan_id": "do-not-invent",
    })
    assert top["event_id"] == "evt-top"
    assert top["transaction_id"] == "9001"
    assert top["customerid"] == "44"
    assert "cc_number" not in top
    assert "plan_id" not in top

    nested = extract_confirmed_fields({
        "event_id": "evt-nested",
        "event_type": EVENT_TRANSACTION_SUCCESS,
        "event_body": {
            "transaction_id": "txn-nested",
            "customerid": "vault-9",
            "order_id": "ord-nested",
            "requested_amount": "399.99",
            "currency": "USD",
            "condition": "pendingsettlement",
            "transaction_type": "cc",
            "is_test_mode": False,
            "action": {
                "success": "1",
                "response_code": "100",
                "response_text": "Approved",
                "amount": "399.99",
            },
            "cc_number": "4111111111111111",
        },
    })
    assert nested["event_id"] == "evt-nested"
    assert nested["transaction_id"] == "txn-nested"
    assert nested["customerid"] == "vault-9"
    assert nested["order_id"] == "ord-nested"
    assert nested["action"]["success"] == "1"
    assert "amount" not in nested["action"]
    assert "cc_number" not in nested
    assert "event_body" not in nested


def test_extract_recurring_subscription_add_fields():
    extracted = extract_confirmed_fields({
        "event_id": "evt-sub-add",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "subscription_id": 8811,
            "subscription_type": "add",
            "next_charge_date": "2026-10-03",
            "completed_payments": 0,
            "attempted_payments": 0,
            "remaining_payments": 0,
            "plan": {
                "id": "SBME_PRO_MONTHLY",
                "name": "Pro Arena Monthly",
                "amount": "49.99",
                "day_frequency": None,
                "payments": 0,
                "month_frequency": 1,
                "day_of_month": 3,
                "undocumented_extra": "drop-me",
            },
            "features": {"is_test_mode": False, "undocumented_extra": True},
            "cc_number": "4111111111111111",
        },
    })
    assert extracted["event_id"] == "evt-sub-add"
    assert extracted["event_type"] == EVENT_RECURRING_CREATED
    assert extracted["subscription_id"] == "8811"
    assert extracted["subscription_type"] == "add"
    assert extracted["next_charge_date"] == "2026-10-03"
    assert extracted["completed_payments"] == 0
    assert extracted["attempted_payments"] == 0
    assert extracted["remaining_payments"] == 0
    assert extracted["plan"] == {
        "id": "SBME_PRO_MONTHLY",
        "name": "Pro Arena Monthly",
        "amount": "49.99",
        "payments": 0,
        "month_frequency": 1,
        "day_of_month": 3,
    }
    assert extracted["features"] == {"is_test_mode": False}
    assert extracted["is_test_mode"] is False
    assert "cc_number" not in extracted
    assert "event_body" not in extracted
    assert "undocumented_extra" not in extracted["plan"]
    assert recognized_sbme_plan_id(extracted["plan"]["id"]) == "SBME_PRO_MONTHLY"


async def test_recurring_subscription_add_is_persisted(client):
    body = json.dumps({
        "event_id": "evt-recurring-add",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "subscription_id": "sub-55",
            "subscription_type": "add",
            "next_charge_date": "2026-10-03",
            "completed_payments": 0,
            "attempted_payments": 0,
            "remaining_payments": 0,
            "plan": {
                "id": "SBME_ELITE_MONTHLY",
                "name": "Elite Stack Monthly",
                "amount": "89.99",
                "day_frequency": None,
                "payments": 0,
                "month_frequency": 1,
                "day_of_month": 3,
            },
            "features": {"is_test_mode": False},
        },
    }, separators=(",", ":")).encode("utf-8")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row.event_type == EVENT_RECURRING_CREATED
        assert row.provider_event_id == "evt-recurring-add"
        assert row.sanitized_payload["subscription_id"] == "sub-55"
        assert row.sanitized_payload["plan"]["id"] == "SBME_ELITE_MONTHLY"
        assert row.sanitized_payload["plan"]["amount"] == "89.99"
        assert row.sanitized_payload["features"]["is_test_mode"] is False


@pytest.mark.parametrize("event_type,subscription_type,event_id", [
    (EVENT_RECURRING_CREATED, "add", "evt-recurring-add-shape"),
    (EVENT_RECURRING_UPDATED, "update", "evt-recurring-update-shape"),
    (EVENT_RECURRING_CANCELED, "delete", "evt-recurring-delete-shape"),
])
def test_extract_recurring_shape_for_all_subscription_events(event_type, subscription_type, event_id):
    extracted = extract_confirmed_fields({
        "event_id": event_id,
        "event_type": event_type,
        "event_body": {
            "subscription_id": "sub-shared",
            "subscription_type": subscription_type,
            "next_charge_date": "2026-11-01",
            "completed_payments": 1,
            "attempted_payments": 1,
            "remaining_payments": 0,
            "plan": {
                "id": "SBME_PRO_ANNUAL",
                "name": "Pro Arena Annual",
                "amount": "399.99",
                "day_frequency": None,
                "payments": 1,
                "month_frequency": 12,
                "day_of_month": 1,
            },
        },
    })
    assert extracted["event_id"] == event_id
    assert extracted["event_type"] == event_type
    assert extracted["subscription_id"] == "sub-shared"
    assert extracted["subscription_type"] == subscription_type
    assert extracted["next_charge_date"] == "2026-11-01"
    assert extracted["completed_payments"] == 1
    assert extracted["attempted_payments"] == 1
    assert extracted["remaining_payments"] == 0
    assert extracted["plan"]["id"] == "SBME_PRO_ANNUAL"
    assert extracted["plan"]["amount"] == "399.99"
    assert "features" not in extracted


@pytest.mark.parametrize("event_type,event_id", [
    (EVENT_RECURRING_UPDATED, "evt-http-update"),
    (EVENT_RECURRING_CANCELED, "evt-http-delete"),
])
async def test_recurring_update_and_delete_are_persisted(client, event_type, event_id):
    body = json.dumps({
        "event_id": event_id,
        "event_type": event_type,
        "event_body": {
            "subscription_id": "sub-updated",
            "subscription_type": "update" if event_type == EVENT_RECURRING_UPDATED else "delete",
            "next_charge_date": "2026-12-01",
            "completed_payments": 2,
            "attempted_payments": 2,
            "remaining_payments": 0,
            "plan": {
                "id": "SBME_ELITE_ANNUAL",
                "name": "Elite Stack Annual",
                "amount": "599.99",
                "payments": 1,
                "month_frequency": 12,
                "day_of_month": 1,
            },
        },
    }, separators=(",", ":")).encode("utf-8")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row.event_type == event_type
        assert row.provider_event_id == event_id
        assert row.sanitized_payload["subscription_id"] == "sub-updated"
        assert row.sanitized_payload["plan"]["id"] == "SBME_ELITE_ANNUAL"
        assert row.processing_status == "unresolved"


_BLOCKED_RECURRING_KEYS = (
    "billing_address",
    "card",
    "check",
    "merchant",
    "processor",
    "cc_number",
    "cc_exp",
    "account_number",
    "routing",
    "email",
    "first_name",
    "last_name",
    "phone",
)


def _recurring_raw(event_type: str, event_id: str, plan_id: str = "SBME_PRO_MONTHLY", **body_extra) -> dict:
    event_body = {
        "subscription_id": "sub-recurring-1",
        "subscription_type": event_type.rsplit(".", 1)[-1],
        "next_charge_date": "2026-10-03",
        "completed_payments": 0,
        "attempted_payments": 0,
        "remaining_payments": 0,
        "plan": {
            "id": plan_id,
            "name": SBME_PLAN_IDS[plan_id],
            "amount": "49.99",
            "day_frequency": None,
            "payments": 0,
            "month_frequency": 1,
            "day_of_month": 3,
        },
        "billing_address": {"address1": "1 Main", "city": "Miami", "zip": "33101"},
        "card": {"cc_number": "4111111111111111", "cc_exp": "1028", "cvv": "123"},
        "check": {"account_number": "000111", "routing": "021000021"},
        "merchant": {"id": "m-1", "processor": "secret-processor"},
        "email": "buyer@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone": "3055550100",
    }
    event_body.update(body_extra)
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_body": event_body,
    }


async def test_recurring_add_does_not_mutate_entitlements(client):
    async with _TestSession() as db:
        db.add(User(email="recurring@test.com", hashed_password="x", is_pro=False, is_active=True))
        await db.commit()
    body = json.dumps({
        "event_id": "evt-recurring-no-entitle",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {
            "subscription_id": "sub-99",
            "plan": {"id": "SBME_PRO_MONTHLY", "name": "Pro Arena Monthly", "amount": "49.99"},
            "features": {"is_test_mode": False},
        },
    }, separators=(",", ":")).encode("utf-8")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "recurring@test.com"))).scalars().first()
        assert user.is_pro is False
        assert user.active_subscription_id is None


async def test_recurring_optional_is_test_mode_omitted(client):
    raw = _recurring_raw(EVENT_RECURRING_UPDATED, "evt-no-test-mode")
    body = json.dumps(raw, separators=(",", ":")).encode("utf-8")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert "features" not in row.sanitized_payload
        assert "is_test_mode" not in row.sanitized_payload


async def test_recurring_sensitive_fields_not_persisted(client):
    raw = _recurring_raw(EVENT_RECURRING_CREATED, "evt-sensitive")
    body = json.dumps(raw, separators=(",", ":")).encode("utf-8")
    received = {}

    def capture(payload):
        received["payload"] = payload
        return handle_recurring_created(payload)

    # Handler is invoked via dispatch; capture the operational payload.
    import services.paykings_webhooks as svc
    orig = svc.handle_recurring_created
    svc.handle_recurring_created = capture
    try:
        res = await client.post(
            "/api/webhooks/paykings",
            content=body,
            headers={"Webhook-Signature": _sign(body)},
        )
    finally:
        svc.handle_recurring_created = orig
    assert res.status_code == 200
    async with _TestSession() as db:
        stored = (await db.execute(select(PaymentWebhookEvent))).scalars().first().sanitized_payload
    for key in _BLOCKED_RECURRING_KEYS:
        assert key not in stored
        assert key not in stored.get("plan", {})
        assert key not in stored.get("features", {})
        assert key not in received["payload"]
    assert stored["subscription_id"] == "sub-recurring-1"
    assert stored["plan"]["id"] == "SBME_PRO_MONTHLY"
    assert "recognized_sbme_plan_id" not in stored
    assert received["payload"]["recognized_sbme_plan_id"] == "SBME_PRO_MONTHLY"


async def test_duplicate_recurring_event_idempotency(client, monkeypatch):
    calls = {"n": 0}

    def counting(payload):
        calls["n"] += 1
        return handle_recurring_created(payload)

    monkeypatch.setattr(
        "api.paykings_webhooks.dispatch_event",
        lambda event_type, payload: counting(payload),
    )
    raw = _recurring_raw(EVENT_RECURRING_CREATED, "evt-dup-recurring")
    body = json.dumps(raw, separators=(",", ":")).encode("utf-8")
    headers = {"Webhook-Signature": _sign(body)}
    first = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    second = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "success"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert calls["n"] == 1
    async with _TestSession() as db:
        count = (await db.execute(select(func.count()).select_from(PaymentWebhookEvent))).scalar_one()
        assert count == 1


@pytest.mark.parametrize("plan_id", list(SBME_PLAN_IDS))
def test_plan_recognition_all_sbme_ids(plan_id):
    assert recognized_sbme_plan_id(plan_id) == plan_id
    extracted = extract_confirmed_fields({
        "event_id": "evt-plan",
        "event_type": EVENT_RECURRING_CREATED,
        "event_body": {"plan": {"id": plan_id, "name": SBME_PLAN_IDS[plan_id], "amount": "1.00"}},
    })
    assert extracted["plan"]["id"] == plan_id
    assert operational_payload(extracted)["recognized_sbme_plan_id"] == plan_id
    assert recognized_sbme_plan_id("not-a-real-plan") is None


async def test_recurring_delete_does_not_deactivate_user(client):
    async with _TestSession() as db:
        db.add(User(
            email="elite@test.com",
            hashed_password="x",
            is_pro=True,
            is_active=True,
        ))
        await db.commit()
    raw = _recurring_raw(EVENT_RECURRING_CANCELED, "evt-delete-no-revoke", plan_id="SBME_ELITE_MONTHLY")
    body = json.dumps(raw, separators=(",", ":")).encode("utf-8")
    received = {}

    def capture(payload):
        received["payload"] = payload
        return handle_recurring_canceled(payload)

    import services.paykings_webhooks as svc
    orig = svc.handle_recurring_canceled
    svc.handle_recurring_canceled = capture
    try:
        res = await client.post(
            "/api/webhooks/paykings",
            content=body,
            headers={"Webhook-Signature": _sign(body)},
        )
    finally:
        svc.handle_recurring_canceled = orig
    assert res.status_code == 200
    assert received["payload"]["subscription_id"] == "sub-recurring-1"
    assert received["payload"]["event_type"] == EVENT_RECURRING_CANCELED
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "elite@test.com"))).scalars().first()
        assert user.is_pro is True
        assert user.is_active is True
        assert user.active_subscription_id is None


async def test_does_not_mutate_user_entitlements(client):
    async with _TestSession() as db:
        db.add(User(email="buyer@test.com", hashed_password="x", is_pro=False, is_active=True))
        await db.commit()
    body = _payload()
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 200
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "buyer@test.com"))).scalars().first()
        assert user.is_pro is False
        assert user.active_subscription_id is None


async def test_parse_signature_header():
    assert parse_signature_header("t=abc,s=def") == ("abc", "def")
    assert parse_signature_header("") is None
    assert parse_signature_header("t=only") is None


async def test_compute_signature_matches_algorithm():
    body = b'{"event_id":"x"}'
    nonce = "n1"
    expected = hmac.new(
        TEST_SIGNING_KEY.encode(),
        nonce.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    assert compute_signature(TEST_SIGNING_KEY, nonce, body) == expected


def test_signing_key_not_exposed_as_next_public(monkeypatch):
    monkeypatch.setenv("PAYKINGS_WEBHOOK_SIGNING_KEY", TEST_SIGNING_KEY)
    monkeypatch.delenv("NEXT_PUBLIC_PAYKINGS_WEBHOOK_SIGNING_KEY", raising=False)
    assert signing_key() == TEST_SIGNING_KEY
    assert os.getenv("NEXT_PUBLIC_PAYKINGS_WEBHOOK_SIGNING_KEY") is None


_NEW_RECORD_ONLY_EVENTS = (
    EVENT_TRANSACTION_UNKNOWN,
    EVENT_TRANSACTION_REFUND_SUCCESS,
    EVENT_TRANSACTION_REFUND_FAILURE,
    EVENT_ACU_AUTOMATICALLY_UPDATED,
    EVENT_ACU_CONTACT_CUSTOMER,
    EVENT_ACU_CLOSED_ACCOUNT,
)

_BLOCKED_TRANSACTION_KEYS = (
    "cc_number",
    "cc_exp",
    "cvv",
    "account_number",
    "routing",
    "social_security_number",
    "drivers_license_number",
    "billing_address",
    "shipping_address",
    "email",
    "phone",
    "first_name",
    "last_name",
    "event_body",
    "vault_updated_cards",
    "vault_updated_expiration_dates",
    "recurring_updated_cards",
    "recurring_updated_expiration_dates",
    "vault_updates",
    "recurring_updates",
)


def _transaction_family_raw(event_type: str, event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_body": {
            "transaction_id": "txn-refund-or-unknown",
            "customerid": "cust-ledger",
            "order_id": "ord-ledger",
            "requested_amount": "-49.99" if "refund" in event_type else "49.99",
            "currency": "USD",
            "condition": "pendingsettlement",
            "transaction_type": "cc",
            "features": {"is_test_mode": True},
            "action": {"success": "1", "response_code": "100", "response_text": "Approved"},
            "cc_number": "4111111111111111",
            "cc_exp": "1028",
            "cvv": "123",
            "account_number": "000111",
            "social_security_number": "111223333",
            "drivers_license_number": "D1234567",
            "billing_address": {"address_1": "1 Main", "email": "buyer@example.com", "phone": "3055550100"},
            "shipping_address": {"address_1": "2 Main"},
            "email": "buyer@example.com",
            "first_name": "Test",
            "last_name": "User",
            "phone": "3055550100",
        },
    }


def _acu_raw(event_type: str, event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_body": {
            "updated_date": "2022-08-22",
            "merchant": {"id": 123456, "name": "Test Account"},
            "cards_checked": {
                "customer_vault": {"checked": 10, "updated": 1},
                "subscriptions": {"checked": 8, "updated": 1},
            },
            "vault_updated_cards": [{
                "customer_vault_id": "308229500",
                "cc_number": "445701******0009",
                "cc_exp": "01/50",
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bsmith@example.com",
                "phone": "+14801112222",
            }],
            "recurring_updated_cards": [{
                "subscription_id": "281474976710720",
                "cc_number": "445701******0459",
                "cc_exp": "01/50",
                "email": "fjones@example.com",
            }],
            "cc_number": "4111111111111111",
        },
    }


def _body_for_new_event(event_type: str, event_id: str) -> bytes:
    if event_type.startswith("acu."):
        raw = _acu_raw(event_type, event_id)
    else:
        raw = _transaction_family_raw(event_type, event_id)
    return json.dumps(raw, separators=(",", ":")).encode("utf-8")


def test_subscribed_event_allowlist_includes_all_eleven():
    assert SUBSCRIBED_EVENT_TYPES == frozenset({
        EVENT_RECURRING_UPDATED,
        EVENT_RECURRING_CREATED,
        EVENT_RECURRING_CANCELED,
        EVENT_TRANSACTION_FAILURE,
        EVENT_TRANSACTION_SUCCESS,
        EVENT_TRANSACTION_UNKNOWN,
        EVENT_TRANSACTION_REFUND_SUCCESS,
        EVENT_TRANSACTION_REFUND_FAILURE,
        EVENT_ACU_AUTOMATICALLY_UPDATED,
        EVENT_ACU_CONTACT_CUSTOMER,
        EVENT_ACU_CLOSED_ACCOUNT,
    })
    assert dispatch_event("transaction.chargeback.unknown", {"event_type": "transaction.chargeback.unknown"}) == "unmapped"


@pytest.mark.parametrize("event_type", _NEW_RECORD_ONLY_EVENTS)
async def test_new_subscribed_events_valid_signature_200(client, event_type):
    body = _body_for_new_event(event_type, f"evt-{event_type}")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "success"}
    async with _TestSession() as db:
        row = (await db.execute(select(PaymentWebhookEvent))).scalars().first()
        assert row.event_type == event_type
        assert row.provider_event_id == f"evt-{event_type}"
        assert row.processing_status == "processed"
        assert row.processed_at is not None
        stored = row.sanitized_payload
        assert stored["event_id"] == f"evt-{event_type}"
        assert stored["event_type"] == event_type
        for blocked in _BLOCKED_TRANSACTION_KEYS:
            assert blocked not in stored
        dumped = json.dumps(stored)
        assert "4111111111111111" not in dumped
        assert "445701" not in dumped
        assert "bsmith@example.com" not in dumped
        assert "111223333" not in dumped


@pytest.mark.parametrize("event_type", _NEW_RECORD_ONLY_EVENTS)
async def test_new_event_duplicate_does_not_reprocess(client, monkeypatch, event_type):
    calls = {"n": 0}
    orig = dispatch_event

    def counting(et, payload):
        calls["n"] += 1
        return orig(et, payload)

    monkeypatch.setattr("api.paykings_webhooks.dispatch_event", counting)
    body = _body_for_new_event(event_type, f"evt-dup-{event_type}")
    headers = {"Webhook-Signature": _sign(body), "Content-Type": "application/json"}
    first = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    second = await client.post("/api/webhooks/paykings", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "success"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert calls["n"] == 1


@pytest.mark.parametrize("event_type", _NEW_RECORD_ONLY_EVENTS)
async def test_new_event_invalid_signature_401(client, event_type):
    body = _body_for_new_event(event_type, f"evt-bad-{event_type}")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": "t=test-nonce,s=" + ("0" * 64)},
    )
    assert res.status_code == 401


@pytest.mark.parametrize("event_type", _NEW_RECORD_ONLY_EVENTS)
async def test_new_event_malformed_signature_401(client, event_type):
    body = _body_for_new_event(event_type, f"evt-mal-{event_type}")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": "not-a-valid-header"},
    )
    assert res.status_code == 401


@pytest.mark.parametrize("event_type", _NEW_RECORD_ONLY_EVENTS)
async def test_new_event_missing_signature_401(client, event_type):
    body = _body_for_new_event(event_type, f"evt-miss-{event_type}")
    res = await client.post("/api/webhooks/paykings", content=body)
    assert res.status_code == 401


async def test_missing_signing_key_503(client, monkeypatch):
    monkeypatch.delenv("PAYKINGS_WEBHOOK_SIGNING_KEY", raising=False)
    body = _body_for_new_event(EVENT_TRANSACTION_REFUND_SUCCESS, "evt-no-key")
    res = await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body)},
    )
    assert res.status_code == 503


def test_refund_extract_keeps_sale_allowlist_only():
    extracted = extract_confirmed_fields(_transaction_family_raw(
        EVENT_TRANSACTION_REFUND_SUCCESS, "evt-refund-extract",
    ))
    assert extracted["event_id"] == "evt-refund-extract"
    assert extracted["event_type"] == EVENT_TRANSACTION_REFUND_SUCCESS
    assert extracted["transaction_id"] == "txn-refund-or-unknown"
    assert extracted["customerid"] == "cust-ledger"
    assert extracted["order_id"] == "ord-ledger"
    assert extracted["requested_amount"] == "-49.99"
    assert extracted["currency"] == "USD"
    assert extracted["condition"] == "pendingsettlement"
    assert extracted["transaction_type"] == "cc"
    assert extracted["is_test_mode"] is True
    assert extracted["action"]["success"] == "1"
    assert extracted["features"]["is_test_mode"] is True
    for blocked in _BLOCKED_TRANSACTION_KEYS:
        assert blocked not in extracted


def test_acu_extract_drops_card_arrays_and_does_not_guess_fields():
    extracted = extract_confirmed_fields(_acu_raw(
        EVENT_ACU_AUTOMATICALLY_UPDATED, "evt-acu-extract",
    ))
    assert extracted == {
        "event_id": "evt-acu-extract",
        "event_type": EVENT_ACU_AUTOMATICALLY_UPDATED,
    }
    assert "updated_date" not in extracted
    assert "merchant" not in extracted
    assert "cards_checked" not in extracted
    assert "subscription_id" not in extracted


async def test_refund_and_acu_do_not_mutate_entitlements_or_subscriptions(client):
    async with _TestSession() as db:
        user = User(email="refund-acu@test.com", hashed_password="x", is_pro=True, is_active=True)
        db.add(user)
        await db.flush()
        db.add(Subscription(
            user_id=user.id,
            plan_name="Pro Arena",
            status="active",
            mrr_value=49.99,
            stripe_subscription_id="sub_keep_me",
        ))
        await db.commit()

    for event_type, event_id in (
        (EVENT_TRANSACTION_REFUND_SUCCESS, "evt-refund-no-revoke"),
        (EVENT_ACU_CLOSED_ACCOUNT, "evt-acu-no-revoke"),
    ):
        body = _body_for_new_event(event_type, event_id)
        res = await client.post(
            "/api/webhooks/paykings",
            content=body,
            headers={"Webhook-Signature": _sign(body), "Content-Type": "application/json"},
        )
        assert res.status_code == 200

    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "refund-acu@test.com"))).scalars().one()
        assert user.is_pro is True
        assert user.active_subscription_id is None
        sub = (await db.execute(select(Subscription))).scalars().one()
        assert sub.status == "active"
        assert sub.plan_name == "Pro Arena"
        assert sub.stripe_subscription_id == "sub_keep_me"


async def test_refund_handler_is_record_only():
    assert handle_transaction_refund_success({
        "event_type": EVENT_TRANSACTION_REFUND_SUCCESS,
        "event_id": "evt-fn",
    }) == "recorded"


async def test_new_events_do_not_log_sensitive_fields(client, caplog):
    body = _body_for_new_event(EVENT_ACU_CONTACT_CUSTOMER, "evt-acu-log")
    await client.post(
        "/api/webhooks/paykings",
        content=body,
        headers={"Webhook-Signature": _sign(body), "Content-Type": "application/json"},
    )
    logged = caplog.text
    assert "445701" not in logged
    assert "bsmith@example.com" not in logged
    assert "4111111111111111" not in logged
    assert TEST_SIGNING_KEY not in logged
