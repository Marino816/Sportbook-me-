"""Apple as a third billing provider: resolver, fail-closed verify, account token."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from models.domain import BillingEntitlement, Subscription
from services.apple_account_token import normalize_apple_account_token
from services.apple_environment import (
    APPLE_ENVIRONMENT_PRODUCTION,
    APPLE_ENVIRONMENT_SANDBOX,
    apple_client_access_override,
    apple_row_environment,
    apple_sandbox_entitlements_allowed,
    apple_subscription_identity,
    apply_verified_apple_lifecycle,
    select_apple_entitlement_for_lifecycle,
)
from services.apple_notifications import verify_signed_notification
from services.apple_plans import get_apple_product, recognized_apple_product_id
from services.apple_verify import (
    AppleVerificationError,
    AppleVerifiedTransaction,
    apple_grant_decision,
    verify_signed_renewal_info,
    verify_signed_transaction,
)
from services.entitlements import (
    PROVIDER_APPLE,
    PROVIDER_PAYKINGS,
    PROVIDER_STRIPE,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    apple_entitlement_is_live,
    choose_effective_access,
)

FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
PAST = datetime.now(timezone.utc) - timedelta(days=1)


def _trusted_verified_apple(
    *,
    tier: str = "pro",
    product_id: str = "com.sportbookme.app.pro.monthly",
    status: str = STATUS_ACTIVE,
    paid_verified: bool = True,
    is_test_mode: bool = False,
    original_transaction_id: str = "100000000000001",
    period_end=FUTURE,
    billing_period: str | None = None,
    row_id: int = 1,
) -> BillingEntitlement:
    """Trusted resolver fixture: a row as if Phase 2 JWS already persisted it.

    This is not cryptographic verification. verify_signed_transaction remains
    fail-closed and is tested separately.
    """
    period = billing_period or ("annual" if "annual" in product_id else "monthly")
    return BillingEntitlement(
        id=row_id,
        user_id=1,
        provider=PROVIDER_APPLE,
        provider_subscription_id=original_transaction_id,
        provider_plan_id=product_id,
        tier=tier,
        billing_period=period,
        status=status,
        paid_verified=paid_verified,
        is_test_mode=is_test_mode,
        current_period_end=period_end,
    )


_apple = _trusted_verified_apple


def _paykings(*, tier: str, plan_id: str, status: str = STATUS_ACTIVE) -> BillingEntitlement:
    return BillingEntitlement(
        id=2,
        user_id=1,
        provider=PROVIDER_PAYKINGS,
        provider_subscription_id="pk-sub-1",
        provider_plan_id=plan_id,
        checkout_reference="pkchk_test",
        tier=tier,
        billing_period="monthly",
        status=status,
        paid_verified=True,
        is_test_mode=False,
    )


def _stripe(*, plan_name: str, status: str = "active") -> Subscription:
    return Subscription(
        id=9,
        user_id=1,
        stripe_subscription_id="sub_stripe_1",
        plan_name=plan_name,
        status=status,
    )


def test_apple_catalog_is_product_id_authoritative():
    pro_m = get_apple_product("com.sportbookme.app.pro.monthly")
    pro_a = get_apple_product("com.sportbookme.app.pro.annual")
    elite_m = get_apple_product("com.sportbookme.app.elite.monthly")
    elite_a = get_apple_product("com.sportbookme.app.elite.annual")
    assert pro_m.tier == "pro" and pro_m.max_lineups == 20 and pro_m.billing_period == "monthly"
    assert pro_a.tier == "pro" and pro_a.max_lineups == 20 and pro_a.billing_period == "annual"
    assert elite_m.tier == "elite" and elite_m.max_lineups == 150
    assert elite_a.tier == "elite" and elite_a.max_lineups == 150
    assert recognized_apple_product_id("com.sportbookme.app.unknown") is None
    assert get_apple_product("") is None


def test_apple_pro_only():
    access = choose_effective_access(apple=[_apple(tier="pro")])
    assert access.tier == "pro"
    assert access.is_pro is True
    assert access.provider == PROVIDER_APPLE
    assert access.max_lineups == 20
    assert access.plan_name == "Pro Arena"


def test_apple_elite_only():
    access = choose_effective_access(apple=[_apple(
        tier="elite",
        product_id="com.sportbookme.app.elite.monthly",
    )])
    assert access.tier == "elite"
    assert access.provider == PROVIDER_APPLE
    assert access.max_lineups == 150


def test_stripe_pro_plus_apple_elite():
    access = choose_effective_access(
        subscriptions=[_stripe(plan_name="Pro Arena")],
        apple=[_apple(tier="elite", product_id="com.sportbookme.app.elite.annual")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_APPLE
    assert access.max_lineups == 150


def test_stripe_elite_plus_apple_pro():
    access = choose_effective_access(
        subscriptions=[_stripe(plan_name="Elite Stack")],
        apple=[_apple(tier="pro")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_STRIPE
    assert access.max_lineups == 150


def test_paykings_pro_plus_apple_elite():
    access = choose_effective_access(
        paykings=[_paykings(tier="pro", plan_id="SBME_PRO_MONTHLY")],
        apple=[_apple(tier="elite", product_id="com.sportbookme.app.elite.monthly")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_APPLE


def test_paykings_elite_plus_apple_pro():
    access = choose_effective_access(
        paykings=[_paykings(tier="elite", plan_id="SBME_ELITE_MONTHLY")],
        apple=[_apple(tier="pro")],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_PAYKINGS


def test_expired_apple_alone_is_free():
    row = _apple(status=STATUS_EXPIRED, period_end=PAST)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.is_pro is False
    assert access.tier == "free"
    assert access.provider is None


def test_apple_period_end_in_past_is_not_live():
    row = _apple(status=STATUS_ACTIVE, period_end=PAST)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_revoked_apple_alone_is_free():
    row = _apple(status=STATUS_REVOKED)
    access = choose_effective_access(apple=[row])
    assert access.is_pro is False
    assert access.tier == "free"


def test_unverified_apple_alone_is_free():
    row = _apple(paid_verified=False)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_unknown_apple_product_is_not_live():
    row = _apple(product_id="com.sportbookme.app.not.a.sku", tier="elite")
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_verified_sandbox_pro_grants_when_node_env_is_production(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    row = _trusted_verified_apple(is_test_mode=True, tier="pro")
    assert apple_entitlement_is_live(row) is True
    access = choose_effective_access(apple=[row])
    assert access.tier == "pro"
    assert access.provider == PROVIDER_APPLE
    assert access.max_lineups == 20
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_SANDBOX


def test_verified_sandbox_elite_grants_when_node_env_is_production(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    row = _trusted_verified_apple(
        is_test_mode=True,
        tier="elite",
        product_id="com.sportbookme.app.elite.monthly",
    )
    assert apple_entitlement_is_live(row) is True
    access = choose_effective_access(apple=[row])
    assert access.tier == "elite"
    assert access.max_lineups == 150
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_SANDBOX


def test_client_supplied_sandbox_flag_cannot_grant():
    assert apple_client_access_override(sandbox=True) is False
    assert apple_client_access_override(allow_sandbox=True, environment="Sandbox") is False
    assert apple_client_access_override(is_test_mode=True) is False
    assert apple_sandbox_entitlements_allowed(client_requested=True) is False
    unverified = _trusted_verified_apple(is_test_mode=True, paid_verified=False)
    assert apple_entitlement_is_live(unverified) is False
    access = choose_effective_access(apple=[unverified])
    assert access.tier == "free"
    assert access.is_pro is False


def test_unsigned_unverified_sandbox_data_cannot_grant():
    with pytest.raises(AppleVerificationError) as exc:
        verify_signed_transaction("eyJhbGciOiJub25lIn0.e30.")
    assert exc.value.reason in {
        "invalid_signature",
        "apple_root_certificates_not_configured",
        "retryable_verification_failure",
    }
    row = _trusted_verified_apple(is_test_mode=True, paid_verified=False)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_sandbox_entitlement_remains_marked_sandbox():
    row = _trusted_verified_apple(is_test_mode=True, tier="pro")
    assert row.is_test_mode is True
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_SANDBOX
    assert apple_subscription_identity(
        row.provider_subscription_id, APPLE_ENVIRONMENT_SANDBOX,
    ) == ("apple", row.provider_subscription_id, APPLE_ENVIRONMENT_SANDBOX)
    choose_effective_access(apple=[row])
    assert row.is_test_mode is True
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_SANDBOX


def test_production_entitlement_remains_marked_production():
    row = _trusted_verified_apple(is_test_mode=False, tier="pro")
    assert row.is_test_mode is False
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_PRODUCTION
    choose_effective_access(apple=[row])
    assert row.is_test_mode is False
    applied = apply_verified_apple_lifecycle(
        row,
        original_transaction_id=row.provider_subscription_id,
        environment="Production",
        status=STATUS_ACTIVE,
    )
    assert applied == "applied"
    assert row.is_test_mode is False


def test_sandbox_lifecycle_cannot_revoke_production_entitlement():
    production = _trusted_verified_apple(
        is_test_mode=False,
        original_transaction_id="200000000000001",
        row_id=10,
    )
    sandbox = _trusted_verified_apple(
        is_test_mode=True,
        original_transaction_id="200000000000001",
        row_id=11,
    )
    selected = select_apple_entitlement_for_lifecycle(
        [production],
        original_transaction_id="200000000000001",
        environment="Sandbox",
    )
    assert selected is None
    reason = apply_verified_apple_lifecycle(
        production,
        original_transaction_id="200000000000001",
        environment="Sandbox",
        status=STATUS_REVOKED,
    )
    assert reason == "environment_mismatch"
    assert production.status == STATUS_ACTIVE
    assert production.is_test_mode is False
    assert apple_entitlement_is_live(production) is True
    sandbox_hit = select_apple_entitlement_for_lifecycle(
        [production, sandbox],
        original_transaction_id="200000000000001",
        environment="Sandbox",
    )
    assert sandbox_hit is sandbox


def test_production_lifecycle_cannot_mutate_sandbox_entitlement():
    sandbox = _trusted_verified_apple(
        is_test_mode=True,
        original_transaction_id="300000000000001",
        row_id=12,
    )
    reason = apply_verified_apple_lifecycle(
        sandbox,
        original_transaction_id="300000000000001",
        environment="Production",
        status=STATUS_EXPIRED,
    )
    assert reason == "environment_mismatch"
    assert sandbox.status == STATUS_ACTIVE
    assert sandbox.is_test_mode is True
    assert apple_entitlement_is_live(sandbox) is True


def test_stripe_and_paykings_remain_unaffected_by_apple_environment():
    stripe_pro = _stripe(plan_name="Pro Arena")
    paykings_elite = _paykings(tier="elite", plan_id="SBME_ELITE_MONTHLY")
    sandbox_revoked = _trusted_verified_apple(is_test_mode=True, status=STATUS_REVOKED)
    access = choose_effective_access(
        subscriptions=[stripe_pro],
        paykings=[paykings_elite],
        apple=[sandbox_revoked],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_PAYKINGS
    assert stripe_pro.status == "active"
    assert paykings_elite.status == STATUS_ACTIVE
    assert paykings_elite.is_test_mode is False
    same_tier = choose_effective_access(
        subscriptions=[stripe_pro],
        apple=[_trusted_verified_apple(is_test_mode=True, tier="pro")],
    )
    assert same_tier.provider == PROVIDER_STRIPE
    assert same_tier.tier == "pro"


def test_testflight_sandbox_against_production_backend(monkeypatch):
    monkeypatch.setenv("NODE_ENV", "production")
    row = _trusted_verified_apple(
        is_test_mode=True,
        tier="pro",
        product_id="com.sportbookme.app.pro.monthly",
        original_transaction_id="400000000000001",
    )
    assert apple_client_access_override(sandbox=True, allow_sandbox=True) is False
    assert apple_entitlement_is_live(row) is True
    access = choose_effective_access(apple=[row])
    assert access.tier == "pro"
    assert access.provider == PROVIDER_APPLE
    assert access.is_pro is True
    assert row.is_test_mode is True
    assert apple_row_environment(row) == APPLE_ENVIRONMENT_SANDBOX


def test_revoked_sandbox_subscription_does_not_grant():
    row = _apple(is_test_mode=True, status=STATUS_REVOKED)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_expired_sandbox_subscription_does_not_grant():
    row = _apple(is_test_mode=True, status=STATUS_EXPIRED, period_end=PAST)
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_unknown_product_sandbox_subscription_does_not_grant():
    row = _apple(is_test_mode=True, product_id="com.sportbookme.app.not.a.sku", tier="elite")
    assert apple_entitlement_is_live(row) is False
    access = choose_effective_access(apple=[row])
    assert access.tier == "free"


def test_expired_apple_falls_back_to_stripe_pro():
    access = choose_effective_access(
        subscriptions=[_stripe(plan_name="Pro Arena")],
        apple=[_apple(
            tier="elite",
            product_id="com.sportbookme.app.elite.monthly",
            status=STATUS_EXPIRED,
            period_end=PAST,
        )],
    )
    assert access.tier == "pro"
    assert access.provider == PROVIDER_STRIPE
    assert access.max_lineups == 20


def test_revoked_apple_falls_back_to_paykings_pro():
    access = choose_effective_access(
        paykings=[_paykings(tier="pro", plan_id="SBME_PRO_MONTHLY")],
        apple=[_apple(
            tier="elite",
            product_id="com.sportbookme.app.elite.monthly",
            status=STATUS_REVOKED,
        )],
    )
    assert access.tier == "pro"
    assert access.provider == PROVIDER_PAYKINGS
    assert access.max_lineups == 20


def test_unverified_apple_does_not_erase_stripe():
    access = choose_effective_access(
        subscriptions=[_stripe(plan_name="Elite Stack Annual")],
        apple=[_apple(tier="pro", paid_verified=False)],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_STRIPE


def test_apple_revoke_does_not_erase_paykings():
    access = choose_effective_access(
        paykings=[_paykings(tier="elite", plan_id="SBME_ELITE_ANNUAL")],
        apple=[_apple(status=STATUS_REVOKED)],
    )
    assert access.tier == "elite"
    assert access.provider == PROVIDER_PAYKINGS


def test_same_tier_stripe_wins_display_tie():
    access = choose_effective_access(
        subscriptions=[_stripe(plan_name="Pro Arena")],
        apple=[_apple(tier="pro")],
    )
    assert access.tier == "pro"
    assert access.provider == PROVIDER_STRIPE


def test_verify_signed_transaction_rejects_unsigned_jws():
    with pytest.raises(AppleVerificationError) as exc:
        verify_signed_transaction("eyJhbGciOiJub25lIn0.e30.")
    assert exc.value.reason in {
        "invalid_signature",
        "apple_root_certificates_not_configured",
        "retryable_verification_failure",
    }


def test_verify_renewal_and_notification_reject_unsigned_jws():
    with pytest.raises(AppleVerificationError) as exc:
        verify_signed_renewal_info("not-a-jws")
    assert exc.value.reason in {
        "invalid_signature",
        "apple_root_certificates_not_configured",
        "retryable_verification_failure",
    }
    with pytest.raises(AppleVerificationError) as exc:
        verify_signed_notification("not-a-jws")
    assert exc.value.reason in {
        "invalid_signature",
        "apple_root_certificates_not_configured",
        "retryable_verification_failure",
    }


def test_grant_decision_denies_unknown_expired_revoked_wrong_bundle_wrong_token_sandbox():
    token = "11111111-1111-4111-8111-111111111111"
    base = dict(
        original_transaction_id="1001",
        product_id="com.sportbookme.app.pro.monthly",
        bundle_id="com.sportbookme.app",
        app_account_token=token,
        environment="Production",
        expires_at=FUTURE,
        revocation_date=None,
    )
    assert apple_grant_decision(
        AppleVerifiedTransaction(**{**base, "product_id": "com.other.app.sku"}),
        bound_account_token=token,
    ).reason == "unknown_product"
    assert apple_grant_decision(
        AppleVerifiedTransaction(**{**base, "expires_at": PAST}),
        bound_account_token=token,
    ).reason == "expired"
    assert apple_grant_decision(
        AppleVerifiedTransaction(**{**base, "revocation_date": PAST}),
        bound_account_token=token,
    ).reason == "revoked"
    assert apple_grant_decision(
        AppleVerifiedTransaction(**{**base, "bundle_id": "com.other.app"}),
        bound_account_token=token,
    ).reason == "wrong_bundle_id"
    assert apple_grant_decision(
        AppleVerifiedTransaction(**base),
        bound_account_token="22222222-2222-4222-8222-222222222222",
    ).reason == "wrong_app_account_binding"
    sandbox = apple_grant_decision(
        AppleVerifiedTransaction(**{**base, "environment": "Sandbox"}),
        bound_account_token=token,
    )
    assert sandbox.allowed is True
    assert sandbox.is_sandbox is True
    assert sandbox.reason == "ok_sandbox"
    assert sandbox.tier == "pro"
    ok = apple_grant_decision(AppleVerifiedTransaction(**base), bound_account_token=token)
    assert ok.allowed is True
    assert ok.tier == "pro"
    assert ok.is_sandbox is False
    assert ok.reason == "ok"


def test_normalize_account_token_rejects_raw_user_id():
    assert normalize_apple_account_token("42") is None
    assert normalize_apple_account_token("not-a-uuid") is None
    assert normalize_apple_account_token("11111111-1111-4111-8111-111111111111") == (
        "11111111-1111-4111-8111-111111111111"
    )


@pytest.mark.asyncio
async def test_apple_account_token_is_stable_uuid_not_user_id():
    import uuid
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from models.database import Base
    from models.domain import User
    from services.apple_account_token import (
        apple_account_token_matches_user,
        get_or_create_apple_account_token,
        lookup_user_id_for_apple_account_token,
    )

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_maker() as db:
        user = User(email="apple-bind@test.com", hashed_password="x", is_pro=False, is_active=True)
        db.add(user)
        await db.flush()
        first = await get_or_create_apple_account_token(db, user)
        second = await get_or_create_apple_account_token(db, user)
        await db.commit()
        assert first == second
        parsed = uuid.UUID(first)
        assert str(parsed) == first
        assert first != str(user.id)
        assert await apple_account_token_matches_user(db, user, first) is True
        assert await apple_account_token_matches_user(db, user, str(user.id)) is False
        assert await lookup_user_id_for_apple_account_token(db, first) == user.id
        assert await lookup_user_id_for_apple_account_token(db, str(user.id)) is None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
