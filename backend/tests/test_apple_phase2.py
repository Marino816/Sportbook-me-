"""Phase 2 Apple verify endpoint, ASSN V2 lifecycle, and multi-provider tests.

Cryptographic verification is exercised against unsigned JWS (must fail).
Grant/lifecycle tests use trusted fixtures returned by monkeypatched
SignedDataVerifier wrappers — not live Apple credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from models.database import Base, get_db
from models.domain import BillingEntitlement, Subscription, User
from services.apple_environment import APPLE_ENVIRONMENT_PRODUCTION, APPLE_ENVIRONMENT_SANDBOX
from services.apple_verify import AppleGrantDecision, AppleVerificationError, AppleVerifiedTransaction
from services.apple_writer import already_current_apple_verify
from services.entitlements import (
    PROVIDER_APPLE,
    PROVIDER_PAYKINGS,
    PROVIDER_STRIPE,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    choose_effective_access,
    effective_access_for_user,
)

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
PAST = datetime.now(timezone.utc) - timedelta(days=1)
SIGNED_NEW = datetime.now(timezone.utc)
SIGNED_OLD = SIGNED_NEW - timedelta(hours=2)

PRO_MONTHLY = "com.sportbookme.app.pro.monthly"
ELITE_MONTHLY = "com.sportbookme.app.elite.monthly"


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


async def _register(client, email: str) -> str:
    username = "".join(ch for ch in email.split("@")[0] if ch.isalnum())[:24].ljust(3, "x")
    await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": "securepass123"},
    )
    res = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return res.json()["access_token"]


async def _account_token(client, jwt: str) -> str:
    res = await client.get(
        "/api/billing/apple/account-token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["appAccountToken"]
    assert token.count("-") == 4
    return token


def _verified(**kwargs) -> AppleVerifiedTransaction:
    base = dict(
        original_transaction_id="100000000000001",
        product_id=PRO_MONTHLY,
        bundle_id="com.sportbookme.app",
        app_account_token="11111111-1111-4111-8111-111111111111",
        environment="Production",
        expires_at=FUTURE,
        revocation_date=None,
        transaction_id="txn-1",
        signed_date=SIGNED_NEW,
        purchase_date=SIGNED_NEW,
        original_purchase_date=SIGNED_NEW,
    )
    base.update(kwargs)
    return AppleVerifiedTransaction(**base)


async def _entitlements(email: str) -> list[BillingEntitlement]:
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().one()
        return list(
            (
                await db.execute(
                    select(BillingEntitlement).where(BillingEntitlement.user_id == user.id)
                )
            ).scalars().all()
        )


async def _user(email: str) -> User:
    async with _TestSession() as db:
        return (await db.execute(select(User).where(User.email == email))).scalars().one()


async def _compat_sub(email: str) -> Subscription | None:
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().one()
        if not user.active_subscription_id:
            return None
        return (
            await db.execute(
                select(Subscription).where(Subscription.id == user.active_subscription_id)
            )
        ).scalars().first()


async def _access(email: str):
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().one()
        return await effective_access_for_user(db, user)


# ── Account token ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_account_token_is_stable_uuid_not_user_id(client):
    jwt = await _register(client, "token@test.com")
    first = await _account_token(client, jwt)
    second = await _account_token(client, jwt)
    assert first == second
    user = await _user("token@test.com")
    assert first != str(user.id)
    other_jwt = await _register(client, "other@test.com")
    other = await _account_token(client, other_jwt)
    assert other != first


@pytest.mark.asyncio
async def test_account_token_requires_auth(client):
    res = await client.get("/api/billing/apple/account-token")
    assert res.status_code in {401, 403}


# ── Verify endpoint ─────────────────────────────────────────


async def _verify(client, jwt, *, signed="jws-ok", extra=None, mock_txn=None):
    payload = {"signedTransaction": signed}
    if extra:
        payload.update(extra)
    with patch("api.apple_billing.verify_signed_transaction", return_value=mock_txn):
        return await client.post(
            "/api/billing/apple/verify",
            json=payload,
            headers={"Authorization": f"Bearer {jwt}"},
        )


@pytest.mark.asyncio
async def test_verify_production_pro(client):
    jwt = await _register(client, "pro@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, environment="Production", product_id=PRO_MONTHLY)
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["granted"] is True
    assert data["tier"] == "pro"
    assert data["environment"] == APPLE_ENVIRONMENT_PRODUCTION
    rows = await _entitlements("pro@test.com")
    assert len(rows) == 1
    assert rows[0].is_test_mode is False
    assert rows[0].paid_verified is True
    assert rows[0].tier == "pro"


@pytest.mark.asyncio
async def test_verify_production_elite(client):
    jwt = await _register(client, "elite@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(
        app_account_token=token,
        product_id=ELITE_MONTHLY,
        environment="Production",
    )
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 200
    assert res.json()["data"]["tier"] == "elite"


@pytest.mark.asyncio
async def test_verify_sandbox_pro(client):
    jwt = await _register(client, "sandpro@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, environment="Sandbox")
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 200
    assert res.json()["data"]["environment"] == APPLE_ENVIRONMENT_SANDBOX
    rows = await _entitlements("sandpro@test.com")
    assert rows[0].is_test_mode is True
    assert rows[0].tier == "pro"


@pytest.mark.asyncio
async def test_verify_sandbox_elite(client):
    jwt = await _register(client, "sandelite@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(
        app_account_token=token,
        environment="Sandbox",
        product_id=ELITE_MONTHLY,
    )
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 200
    assert res.json()["data"]["tier"] == "elite"
    assert res.json()["data"]["environment"] == APPLE_ENVIRONMENT_SANDBOX


@pytest.mark.asyncio
async def test_verify_invalid_signature(client):
    jwt = await _register(client, "badsig@test.com")
    await _account_token(client, jwt)
    with patch(
        "api.apple_billing.verify_signed_transaction",
        side_effect=AppleVerificationError("invalid_signature"),
    ):
        res = await client.post(
            "/api/billing/apple/verify",
            json={"signedTransaction": "not-a-jws"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_signature"


@pytest.mark.asyncio
async def test_verify_wrong_bundle_id(client):
    jwt = await _register(client, "bundle@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, bundle_id="com.other.app")
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "wrong_bundle_id"


@pytest.mark.asyncio
async def test_verify_unknown_product(client):
    jwt = await _register(client, "sku@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, product_id="com.sportbookme.app.unknown")
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "unknown_product"


@pytest.mark.asyncio
async def test_verify_wrong_app_account_token(client):
    jwt = await _register(client, "wrongtok@test.com")
    await _account_token(client, jwt)
    txn = _verified(app_account_token="22222222-2222-4222-8222-222222222222")
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "wrong_app_account_binding"


@pytest.mark.asyncio
async def test_verify_missing_app_account_token(client):
    jwt = await _register(client, "notok@test.com")
    await _account_token(client, jwt)
    txn = _verified(app_account_token=None)
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "wrong_app_account_binding"


@pytest.mark.asyncio
async def test_verify_expired_transaction(client):
    jwt = await _register(client, "expired@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, expires_at=PAST)
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "expired"


@pytest.mark.asyncio
async def test_verify_revoked_transaction(client):
    jwt = await _register(client, "revoked@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, revocation_date=PAST, revocation_reason="1")
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "revoked"


@pytest.mark.asyncio
async def test_verify_cross_user_binding_rejected(client):
    jwt_a = await _register(client, "usera@test.com")
    token_a = await _account_token(client, jwt_a)
    jwt_b = await _register(client, "userb@test.com")
    await _account_token(client, jwt_b)
    txn = _verified(app_account_token=token_a)
    res = await _verify(client, jwt_b, mock_txn=txn)
    assert res.status_code == 400
    assert res.json()["detail"] == "wrong_app_account_binding"
    assert await _entitlements("userb@test.com") == []


@pytest.mark.asyncio
async def test_verify_duplicate_is_idempotent(client):
    jwt = await _register(client, "dup@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    first = await _verify(client, jwt, mock_txn=txn)
    second = await _verify(client, jwt, mock_txn=txn)
    assert first.status_code == 200
    assert second.status_code == 200
    rows = await _entitlements("dup@test.com")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_verify_client_sandbox_flag_cannot_grant(client):
    jwt = await _register(client, "flag@test.com")
    res = await client.post(
        "/api/billing/apple/verify",
        json={"sandbox": True, "is_test_mode": True, "environment": "Sandbox"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "missing_signed_transaction"
    assert await _entitlements("flag@test.com") == []


@pytest.mark.asyncio
async def test_verify_requires_auth(client):
    res = await client.post("/api/billing/apple/verify", json={"signedTransaction": "x"})
    assert res.status_code in {401, 403}


# ── ASSN V2 ─────────────────────────────────────────────────


def _notification(
    *,
    uuid: str,
    ntype: str,
    subtype: str | None = None,
    environment: str = "Production",
    signed_ms: int | None = None,
    status: int = 1,
    txn_jws: str = "txn-jws",
    renewal_jws: str | None = "ren-jws",
):
    data = SimpleNamespace(
        signedTransactionInfo=txn_jws,
        signedRenewalInfo=renewal_jws,
        rawEnvironment=environment,
        environment=None,
        rawStatus=status,
        status=None,
    )
    return SimpleNamespace(
        notificationUUID=uuid,
        notificationType=None,
        rawNotificationType=ntype,
        subtype=None,
        rawSubtype=subtype,
        signedDate=signed_ms if signed_ms is not None else int(SIGNED_NEW.timestamp() * 1000),
        data=data,
    )


async def _post_notification(client, decoded, txn, renewal=None):
    with patch("services.apple_notifications.verify_signed_notification", return_value=decoded), \
            patch("services.apple_notifications.verify_signed_transaction", return_value=txn), \
            patch("services.apple_notifications.verify_signed_renewal_info", return_value=renewal or SimpleNamespace(
                originalTransactionId=txn.original_transaction_id,
                productId=txn.product_id,
                appAccountToken=txn.app_account_token,
                isInBillingRetryPeriod=False,
                gracePeriodExpiresDate=None,
            )):
        return await client.post(
            "/api/webhooks/apple",
            json={"signedPayload": "signed-notification-jws"},
        )


@pytest.mark.asyncio
async def test_unsigned_notification_rejected(client):
    res = await client.post("/api/webhooks/apple", json={"hello": "world"})
    assert res.status_code == 400
    assert res.json()["detail"] == "missing_signed_payload"


@pytest.mark.asyncio
async def test_invalid_notification_jws_rejected(client):
    res = await client.post("/api/webhooks/apple", json={"signedPayload": "not-a-jws"})
    assert res.status_code in {400, 503}
    assert res.json()["detail"] in {
        "invalid_signature",
        "apple_root_certificates_not_configured",
        "retryable_verification_failure",
    }


@pytest.mark.asyncio
async def test_assn_subscribed(client):
    jwt = await _register(client, "sub@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    res = await _post_notification(client, _notification(uuid="n-sub", ntype="SUBSCRIBED"), txn)
    assert res.status_code == 200
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("sub@test.com")
    assert rows[0].status == STATUS_ACTIVE
    assert rows[0].paid_verified is True


@pytest.mark.asyncio
async def test_assn_did_renew(client):
    jwt = await _register(client, "renew@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-sub2", ntype="SUBSCRIBED"), txn)
    later = _verified(app_account_token=token, signed_date=SIGNED_NEW + timedelta(days=30), transaction_id="txn-2")
    res = await _post_notification(client, _notification(uuid="n-renew", ntype="DID_RENEW"), later)
    assert res.status_code == 200
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("renew@test.com")
    assert len(rows) == 1
    assert rows[0].last_successful_transaction_id == "txn-2"


@pytest.mark.asyncio
async def test_assn_fail_to_renew_does_not_revoke_in_retry(client):
    jwt = await _register(client, "retry@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-r1", ntype="SUBSCRIBED"), txn)
    res = await _post_notification(
        client,
        _notification(uuid="n-fail", ntype="DID_FAIL_TO_RENEW", status=3, subtype="GRACE_PERIOD"),
        txn,
    )
    assert res.status_code == 200
    rows = await _entitlements("retry@test.com")
    assert rows[0].status == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_assn_grace_period_expired(client):
    jwt = await _register(client, "grace@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-g1", ntype="SUBSCRIBED"), txn)
    res = await _post_notification(
        client,
        _notification(uuid="n-g2", ntype="GRACE_PERIOD_EXPIRED", status=2),
        txn,
    )
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("grace@test.com")
    assert rows[0].status == STATUS_EXPIRED


@pytest.mark.asyncio
async def test_assn_expired(client):
    jwt = await _register(client, "exp@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-e1", ntype="SUBSCRIBED"), txn)
    res = await _post_notification(client, _notification(uuid="n-e2", ntype="EXPIRED"), txn)
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("exp@test.com")
    assert rows[0].status == STATUS_EXPIRED


@pytest.mark.asyncio
async def test_assn_refund(client):
    jwt = await _register(client, "ref@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-f1", ntype="SUBSCRIBED"), txn)
    res = await _post_notification(client, _notification(uuid="n-f2", ntype="REFUND"), txn)
    rows = await _entitlements("ref@test.com")
    assert rows[0].status == STATUS_REVOKED
    assert res.json()["decision"] == "applied"


@pytest.mark.asyncio
async def test_assn_revoke(client):
    jwt = await _register(client, "rvk@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-v1", ntype="SUBSCRIBED"), txn)
    await _post_notification(client, _notification(uuid="n-v2", ntype="REVOKE"), txn)
    rows = await _entitlements("rvk@test.com")
    assert rows[0].status == STATUS_REVOKED


@pytest.mark.asyncio
async def test_active_apple_pro_http_plan_and_status(client):
    jwt = await _register(client, "httppro@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    res = await _verify(client, jwt, mock_txn=txn)
    assert res.status_code == 200
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
    assert me.status_code == 200
    assert me.json()["plan"] == "Pro Arena"
    assert me.json()["is_pro"] is True
    status = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {jwt}"})
    data = status.json()["data"]
    assert data["plan"] == "Pro Arena"
    assert data["status"] == "active"
    assert data["has_access"] is True
    assert data["provider"] == "apple"
    assert data["is_canceled"] is False
    access = await _access("httppro@test.com")
    assert access.max_lineups == 20
    assert access.plan_name == "Pro Arena"


@pytest.mark.asyncio
async def test_assn_renewal_status_change_does_not_revoke(client):
    jwt = await _register(client, "rs@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-rs1", ntype="SUBSCRIBED"), txn)
    res = await _post_notification(
        client,
        _notification(uuid="n-rs2", ntype="DID_CHANGE_RENEWAL_STATUS", subtype="AUTO_RENEW_DISABLED"),
        txn,
    )
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("rs@test.com")
    assert rows[0].status == STATUS_ACTIVE
    assert rows[0].paid_verified is True
    compat = await _compat_sub("rs@test.com")
    assert compat is not None
    assert compat.cancel_at_period_end is True
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
    assert me.json()["plan"] == "Pro Arena"
    assert me.json()["is_pro"] is True
    data = (
        await client.get("/api/billing/status", headers={"Authorization": f"Bearer {jwt}"})
    ).json()["data"]
    assert data["plan"] == "Pro Arena"
    assert data["has_access"] is True
    assert data["is_canceled"] is True
    assert data["provider"] == "apple"
    access = await _access("rs@test.com")
    assert access.is_pro is True
    assert access.max_lineups == 20


@pytest.mark.asyncio
async def test_expired_http_plan_is_starter_not_compat_label(client):
    jwt = await _register(client, "explabel@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="n-el1", ntype="SUBSCRIBED"), txn)
    await _post_notification(
        client,
        _notification(uuid="n-el2", ntype="DID_CHANGE_RENEWAL_STATUS", subtype="AUTO_RENEW_DISABLED"),
        txn,
    )
    res = await _post_notification(client, _notification(uuid="n-el3", ntype="EXPIRED"), txn)
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("explabel@test.com")
    assert len(rows) == 1
    assert rows[0].status == STATUS_EXPIRED
    assert rows[0].paid_verified is True
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt}"})
    assert me.json()["plan"] == "Starter"
    assert me.json()["is_pro"] is False
    data = (
        await client.get("/api/billing/status", headers={"Authorization": f"Bearer {jwt}"})
    ).json()["data"]
    assert data["plan"] == "Starter"
    assert data["status"] == "free"
    assert data["has_access"] is False
    assert data["provider"] is None
    access = await _access("explabel@test.com")
    assert access.plan_name == "Starter"
    assert access.max_lineups == 1


@pytest.mark.asyncio
async def test_assn_renewal_pref_does_not_grant_future_tier(client):
    jwt = await _register(client, "pref@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token, product_id=PRO_MONTHLY)
    await _post_notification(client, _notification(uuid="n-p1", ntype="SUBSCRIBED"), txn)
    renewal = SimpleNamespace(
        originalTransactionId=txn.original_transaction_id,
        productId=PRO_MONTHLY,
        autoRenewProductId=ELITE_MONTHLY,
        appAccountToken=token,
        isInBillingRetryPeriod=False,
        gracePeriodExpiresDate=None,
    )
    res = await _post_notification(
        client,
        _notification(uuid="n-p2", ntype="DID_CHANGE_RENEWAL_PREF", subtype="UPGRADE"),
        txn,
        renewal=renewal,
    )
    assert res.json()["decision"] == "applied"
    rows = await _entitlements("pref@test.com")
    assert rows[0].tier == "pro"
    assert rows[0].provider_plan_id == PRO_MONTHLY


@pytest.mark.asyncio
async def test_assn_duplicate_notification_uuid(client):
    jwt = await _register(client, "dupe@test.com")
    token = await _account_token(client, jwt)
    txn = _verified(app_account_token=token)
    decoded = _notification(uuid="same-uuid", ntype="SUBSCRIBED")
    first = await _post_notification(client, decoded, txn)
    second = await _post_notification(client, decoded, txn)
    assert first.json()["decision"] == "applied"
    assert second.json()["decision"] == "duplicate"
    assert len(await _entitlements("dupe@test.com")) == 1


@pytest.mark.asyncio
async def test_older_signed_date_cannot_overwrite(client):
    jwt = await _register(client, "order@test.com")
    token = await _account_token(client, jwt)
    newer = _verified(app_account_token=token, signed_date=SIGNED_NEW, transaction_id="new")
    await _post_notification(client, _notification(uuid="n-new", ntype="SUBSCRIBED"), newer)
    older = _verified(
        app_account_token=token,
        signed_date=SIGNED_OLD,
        transaction_id="old",
        revocation_date=PAST,
        revocation_reason="1",
    )
    res = await _post_notification(
        client,
        _notification(
            uuid="n-old",
            ntype="REVOKE",
            signed_ms=int(SIGNED_OLD.timestamp() * 1000),
        ),
        older,
    )
    assert res.json()["decision"] == "stale_notification"
    rows = await _entitlements("order@test.com")
    assert rows[0].status == STATUS_ACTIVE
    assert rows[0].last_successful_transaction_id == "new"


@pytest.mark.asyncio
async def test_sandbox_cannot_mutate_production(client):
    jwt = await _register(client, "iso@test.com")
    token = await _account_token(client, jwt)
    prod = _verified(app_account_token=token, environment="Production", original_transaction_id="shared-oid")
    await _post_notification(client, _notification(uuid="n-prod", ntype="SUBSCRIBED"), prod)
    sand = _verified(
        app_account_token=token,
        environment="Sandbox",
        original_transaction_id="shared-oid",
        revocation_date=PAST,
        revocation_reason="1",
    )
    res = await _post_notification(
        client,
        _notification(uuid="n-sand", ntype="REVOKE", environment="Sandbox"),
        sand,
    )
    assert res.json()["decision"] == "no_matching_entitlement"
    rows = await _entitlements("iso@test.com")
    assert len(rows) == 1
    assert rows[0].is_test_mode is False
    assert rows[0].status == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_production_cannot_mutate_sandbox(client):
    jwt = await _register(client, "iso2@test.com")
    token = await _account_token(client, jwt)
    sand = _verified(app_account_token=token, environment="Sandbox", original_transaction_id="shared-oid-2")
    await _post_notification(
        client,
        _notification(uuid="n-s1", ntype="SUBSCRIBED", environment="Sandbox"),
        sand,
    )
    prod = _verified(
        app_account_token=token,
        environment="Production",
        original_transaction_id="shared-oid-2",
        expires_at=PAST,
    )
    res = await _post_notification(
        client,
        _notification(uuid="n-p1", ntype="EXPIRED", environment="Production"),
        prod,
    )
    assert res.json()["decision"] == "no_matching_entitlement"
    rows = await _entitlements("iso2@test.com")
    assert rows[0].is_test_mode is True
    assert rows[0].status == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_same_original_id_can_exist_in_both_environments(client):
    jwt = await _register(client, "both@test.com")
    token = await _account_token(client, jwt)
    prod = _verified(app_account_token=token, environment="Production", original_transaction_id="oid-both")
    sand = _verified(app_account_token=token, environment="Sandbox", original_transaction_id="oid-both")
    await _post_notification(client, _notification(uuid="b1", ntype="SUBSCRIBED"), prod)
    await _post_notification(
        client,
        _notification(uuid="b2", ntype="SUBSCRIBED", environment="Sandbox"),
        sand,
    )
    rows = await _entitlements("both@test.com")
    assert len(rows) == 2
    envs = sorted(row.is_test_mode for row in rows)
    assert envs == [False, True]


# ── Multi-provider ──────────────────────────────────────────


def _stripe(plan_name="Pro Arena") -> Subscription:
    return Subscription(
        id=9, user_id=1, stripe_subscription_id="sub_stripe_1",
        plan_name=plan_name, status="active",
    )


def _paykings(*, tier: str, plan_id: str) -> BillingEntitlement:
    return BillingEntitlement(
        id=2, user_id=1, provider=PROVIDER_PAYKINGS,
        provider_subscription_id="pk-sub-1", provider_plan_id=plan_id,
        checkout_reference="pkchk_test", tier=tier, billing_period="monthly",
        status=STATUS_ACTIVE, paid_verified=True, is_test_mode=False,
    )


def _apple_row(*, status=STATUS_ACTIVE, tier="pro", product=PRO_MONTHLY):
    return BillingEntitlement(
        id=3, user_id=1, provider=PROVIDER_APPLE,
        provider_subscription_id="100000000000001", provider_plan_id=product,
        checkout_reference="apple:Production:100000000000001",
        tier=tier, billing_period="monthly", status=status,
        paid_verified=True, is_test_mode=False,
    )


def test_apple_revoked_stripe_pro_remains():
    access = choose_effective_access(
        subscriptions=[_stripe("Pro Arena")],
        apple=[_apple_row(status=STATUS_REVOKED)],
    )
    assert access.tier == "pro"
    assert access.provider == PROVIDER_STRIPE


def test_apple_expired_paykings_elite_remains():
    access = choose_effective_access(
        paykings=[_paykings(tier="elite", plan_id="SBME_ELITE_MONTHLY")],
        apple=[_apple_row(status=STATUS_EXPIRED, tier="pro")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_PAYKINGS


def test_apple_elite_plus_stripe_pro():
    access = choose_effective_access(
        subscriptions=[_stripe("Pro Arena")],
        apple=[_apple_row(tier="elite", product=ELITE_MONTHLY)],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_APPLE


def test_apple_pro_plus_paykings_elite():
    access = choose_effective_access(
        paykings=[_paykings(tier="elite", plan_id="SBME_ELITE_MONTHLY")],
        apple=[_apple_row(tier="pro")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_PAYKINGS


@pytest.mark.asyncio
async def test_reconcile_preserves_stripe_when_apple_revoked(client):
    jwt = await _register(client, "multi@test.com")
    token = await _account_token(client, jwt)
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "multi@test.com"))).scalars().one()
        sub = Subscription(
            user_id=user.id,
            stripe_subscription_id="sub_live_1",
            plan_name="Pro Arena",
            status="active",
        )
        db.add(sub)
        await db.flush()
        user.active_subscription_id = sub.id
        user.is_pro = True
        await db.commit()
    txn = _verified(app_account_token=token)
    await _post_notification(client, _notification(uuid="m1", ntype="SUBSCRIBED"), txn)
    await _post_notification(client, _notification(uuid="m2", ntype="REVOKE"), txn)
    async with _TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "multi@test.com"))).scalars().one()
        access = await effective_access_for_user(db, user)
        assert access.tier == "pro"
        assert access.provider == PROVIDER_STRIPE


# ── Verify already_current / stale race ─────────────────────


def _snapshot(row: BillingEntitlement) -> dict:
    signed = row.last_provider_signed_at
    if signed is not None and signed.tzinfo is None:
        signed = signed.replace(tzinfo=timezone.utc)
    return {
        "status": row.status,
        "paid_verified": row.paid_verified,
        "is_test_mode": row.is_test_mode,
        "tier": row.tier,
        "provider_subscription_id": row.provider_subscription_id,
        "last_successful_transaction_id": row.last_successful_transaction_id,
        "signed_ms": int(signed.timestamp() * 1000) if signed is not None else None,
    }


@pytest.mark.asyncio
async def test_assn_initial_buy_then_older_verify_is_already_current(client):
    jwt = await _register(client, "race@test.com")
    token = await _account_token(client, jwt)
    assn_txn = _verified(
        app_account_token=token,
        environment="Sandbox",
        signed_date=SIGNED_NEW,
        transaction_id="assn-buy",
        original_transaction_id="otid-race-1",
    )
    assn = await _post_notification(
        client,
        _notification(
            uuid="n-initial",
            ntype="SUBSCRIBED",
            subtype="INITIAL_BUY",
            environment="Sandbox",
            signed_ms=int(SIGNED_NEW.timestamp() * 1000),
        ),
        assn_txn,
    )
    assert assn.json()["decision"] == "applied"
    before = _snapshot((await _entitlements("race@test.com"))[0])
    older = _verified(
        app_account_token=token,
        environment="Sandbox",
        signed_date=SIGNED_NEW - timedelta(seconds=2),
        transaction_id="device-jws",
        original_transaction_id="otid-race-1",
        original_purchase_date=SIGNED_NEW - timedelta(seconds=2),
    )
    res = await _verify(client, jwt, mock_txn=older)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["granted"] is True
    assert data["decision"] == "already_current"
    assert data["tier"] == "pro"
    assert data["status"] in {"active", "pro"}
    assert data["environment"] == APPLE_ENVIRONMENT_SANDBOX
    rows = await _entitlements("race@test.com")
    assert len(rows) == 1
    after = _snapshot(rows[0])
    assert after == before
    assert rows[0].status == STATUS_ACTIVE
    assert rows[0].paid_verified is True
    access = await _access("race@test.com")
    assert access.tier == "pro"
    assert access.provider == PROVIDER_APPLE


@pytest.mark.asyncio
async def test_restore_already_current_does_not_require_new_purchase(client):
    jwt = await _register(client, "restore-race@test.com")
    token = await _account_token(client, jwt)
    assn_txn = _verified(
        app_account_token=token,
        environment="Sandbox",
        signed_date=SIGNED_NEW,
        original_transaction_id="otid-restore-1",
    )
    await _post_notification(
        client,
        _notification(
            uuid="n-restore-buy",
            ntype="SUBSCRIBED",
            subtype="INITIAL_BUY",
            environment="Sandbox",
        ),
        assn_txn,
    )
    before = _snapshot((await _entitlements("restore-race@test.com"))[0])
    older = _verified(
        app_account_token=token,
        environment="Sandbox",
        signed_date=SIGNED_NEW - timedelta(seconds=2),
        original_transaction_id="otid-restore-1",
    )
    res = await _verify(
        client,
        jwt,
        extra={"signedTransactions": ["restore-jws-1"]},
        mock_txn=older,
    )
    assert res.status_code == 200
    assert res.json()["data"]["decision"] == "already_current"
    assert res.json()["data"]["granted"] is True
    after = _snapshot((await _entitlements("restore-race@test.com"))[0])
    assert after == before
    access = await _access("restore-race@test.com")
    assert access.tier == "pro"


@pytest.mark.asyncio
async def test_stale_revoke_verify_remains_rejected(client):
    jwt = await _register(client, "stale-rev@test.com")
    token = await _account_token(client, jwt)
    live = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW,
        transaction_id="live-txn",
        original_transaction_id="otid-rev-1",
    )
    await _post_notification(client, _notification(uuid="n-rev-1", ntype="SUBSCRIBED"), live)
    revoke = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW + timedelta(seconds=5),
        transaction_id="revoke-txn",
        original_transaction_id="otid-rev-1",
        revocation_date=SIGNED_NEW + timedelta(seconds=5),
        revocation_reason="1",
    )
    applied = await _post_notification(
        client,
        _notification(
            uuid="n-rev-2",
            ntype="REVOKE",
            signed_ms=int((SIGNED_NEW + timedelta(seconds=5)).timestamp() * 1000),
        ),
        revoke,
    )
    assert applied.json()["decision"] == "applied"
    before = _snapshot((await _entitlements("stale-rev@test.com"))[0])
    assert before["status"] == STATUS_REVOKED
    older_purchase = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW,
        transaction_id="device-old",
        original_transaction_id="otid-rev-1",
    )
    res = await _verify(client, jwt, mock_txn=older_purchase)
    assert res.status_code == 400
    assert res.json()["detail"] == "stale_notification"
    after = _snapshot((await _entitlements("stale-rev@test.com"))[0])
    assert after == before
    access = await _access("stale-rev@test.com")
    assert access.tier == "free"


@pytest.mark.asyncio
async def test_stale_expire_verify_does_not_revive(client):
    jwt = await _register(client, "stale-exp@test.com")
    token = await _account_token(client, jwt)
    live = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW,
        original_transaction_id="otid-exp-1",
    )
    await _post_notification(client, _notification(uuid="n-exp-1", ntype="SUBSCRIBED"), live)
    expired = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW + timedelta(seconds=5),
        original_transaction_id="otid-exp-1",
        expires_at=PAST,
    )
    applied = await _post_notification(
        client,
        _notification(
            uuid="n-exp-2",
            ntype="EXPIRED",
            signed_ms=int((SIGNED_NEW + timedelta(seconds=5)).timestamp() * 1000),
        ),
        expired,
    )
    assert applied.json()["decision"] == "applied"
    before = _snapshot((await _entitlements("stale-exp@test.com"))[0])
    assert before["status"] == STATUS_EXPIRED
    older = _verified(
        app_account_token=token,
        signed_date=SIGNED_NEW,
        original_transaction_id="otid-exp-1",
        expires_at=FUTURE,
    )
    res = await _verify(client, jwt, mock_txn=older)
    assert res.status_code == 400
    assert res.json()["detail"] == "stale_notification"
    after = _snapshot((await _entitlements("stale-exp@test.com"))[0])
    assert after == before
    access = await _access("stale-exp@test.com")
    assert access.tier == "free"


@pytest.mark.asyncio
async def test_stale_verify_wrong_user_rejected(client):
    jwt_a = await _register(client, "owner@test.com")
    token_a = await _account_token(client, jwt_a)
    jwt_b = await _register(client, "other-user@test.com")
    token_b = await _account_token(client, jwt_b)
    owner = _verified(
        app_account_token=token_a,
        signed_date=SIGNED_NEW,
        original_transaction_id="otid-owner-1",
    )
    await _post_notification(client, _notification(uuid="n-owner", ntype="SUBSCRIBED"), owner)
    before = _snapshot((await _entitlements("owner@test.com"))[0])
    spoofed = _verified(
        app_account_token=token_b,
        signed_date=SIGNED_NEW - timedelta(seconds=2),
        original_transaction_id="otid-owner-1",
    )
    res = await _verify(client, jwt_b, mock_txn=spoofed)
    assert res.status_code == 400
    assert res.json()["detail"] == "stale_notification"
    assert await _entitlements("other-user@test.com") == []
    after = _snapshot((await _entitlements("owner@test.com"))[0])
    assert after == before
    access = await _access("owner@test.com")
    assert access.tier == "pro"


@pytest.mark.asyncio
async def test_stale_verify_opposite_environment_rejected(client):
    jwt = await _register(client, "env-iso@test.com")
    token = await _account_token(client, jwt)
    sandbox = _verified(
        app_account_token=token,
        environment="Sandbox",
        signed_date=SIGNED_NEW,
        original_transaction_id="otid-env-1",
    )
    await _post_notification(
        client,
        _notification(uuid="n-env-s", ntype="SUBSCRIBED", environment="Sandbox"),
        sandbox,
    )
    before = _snapshot((await _entitlements("env-iso@test.com"))[0])
    production = _verified(
        app_account_token=token,
        environment="Production",
        signed_date=SIGNED_NEW - timedelta(seconds=2),
        original_transaction_id="otid-env-1",
    )
    res = await _verify(client, jwt, mock_txn=production)
    assert res.status_code == 400
    assert res.json()["detail"] == "stale_notification"
    rows = await _entitlements("env-iso@test.com")
    assert len(rows) == 1
    assert rows[0].is_test_mode is True
    assert _snapshot(rows[0]) == before
    access = await _access("env-iso@test.com")
    assert access.tier == "pro"


def test_already_current_helper_rejects_mismatched_and_dead_rows():
    user = SimpleNamespace(id=11)
    other = SimpleNamespace(id=12)
    verified = _verified(
        environment="Sandbox",
        original_transaction_id="otid-helper-1",
        app_account_token="11111111-1111-4111-8111-111111111111",
    )
    decision = AppleGrantDecision(
        allowed=True,
        reason="ok_sandbox",
        product_id=PRO_MONTHLY,
        tier="pro",
        billing_period="monthly",
        is_sandbox=True,
    )
    live = BillingEntitlement(
        id=30,
        user_id=11,
        provider=PROVIDER_APPLE,
        provider_subscription_id="otid-helper-1",
        provider_plan_id=PRO_MONTHLY,
        checkout_reference="apple:Sandbox:otid-helper-1",
        tier="pro",
        billing_period="monthly",
        status=STATUS_ACTIVE,
        paid_verified=True,
        is_test_mode=True,
        current_period_end=FUTURE,
    )
    assert already_current_apple_verify(user, verified, decision, live) is True
    assert already_current_apple_verify(other, verified, decision, live) is False
    live_prod = BillingEntitlement(
        id=31,
        user_id=11,
        provider=PROVIDER_APPLE,
        provider_subscription_id="otid-helper-1",
        provider_plan_id=PRO_MONTHLY,
        checkout_reference="apple:Production:otid-helper-1",
        tier="pro",
        billing_period="monthly",
        status=STATUS_ACTIVE,
        paid_verified=True,
        is_test_mode=False,
        current_period_end=FUTURE,
    )
    assert already_current_apple_verify(user, verified, decision, live_prod) is False
    expired = BillingEntitlement(
        id=32,
        user_id=11,
        provider=PROVIDER_APPLE,
        provider_subscription_id="otid-helper-1",
        provider_plan_id=PRO_MONTHLY,
        checkout_reference="apple:Sandbox:otid-helper-1",
        tier="pro",
        billing_period="monthly",
        status=STATUS_EXPIRED,
        paid_verified=True,
        is_test_mode=True,
        current_period_end=PAST,
    )
    assert already_current_apple_verify(user, verified, decision, expired) is False
    revoked = BillingEntitlement(
        id=33,
        user_id=11,
        provider=PROVIDER_APPLE,
        provider_subscription_id="otid-helper-1",
        provider_plan_id=PRO_MONTHLY,
        checkout_reference="apple:Sandbox:otid-helper-1",
        tier="pro",
        billing_period="monthly",
        status=STATUS_REVOKED,
        paid_verified=True,
        is_test_mode=True,
        current_period_end=FUTURE,
    )
    assert already_current_apple_verify(user, verified, decision, revoked) is False
