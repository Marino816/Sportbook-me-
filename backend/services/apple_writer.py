"""Persist verified Apple entitlements with environment isolation.

Identity: (provider='apple', originalTransactionId, is_test_mode).
Sandbox lifecycle never mutates Production rows and the reverse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import BillingEntitlement, Subscription, User
from services.apple_environment import (
    APPLE_ENVIRONMENT_PRODUCTION,
    APPLE_ENVIRONMENT_SANDBOX,
    apple_environment_from_flag,
    apple_lifecycle_may_mutate,
    normalize_apple_environment,
)
from services.apple_plans import get_apple_product
from services.apple_verify import AppleGrantDecision, AppleVerifiedTransaction
from services.entitlements import (
    PROVIDER_APPLE,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    apple_entitlement_is_live,
    reconcile_user_access,
)

logger = logging.getLogger(__name__)


def mask_apple_id(value: object) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return "***"
    return f"…{text[-4:]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _signed_ms(value: Optional[datetime]) -> Optional[int]:
    aware = _aware(value)
    if aware is None:
        return None
    return int(aware.timestamp() * 1000)


def incoming_signed_is_stale(
    row: BillingEntitlement,
    incoming_signed_at: Optional[datetime],
) -> bool:
    stored_ms = _signed_ms(row.last_provider_signed_at)
    incoming_ms = _signed_ms(incoming_signed_at)
    if stored_ms is None or incoming_ms is None:
        return False
    return incoming_ms < stored_ms


def apple_checkout_reference(original_transaction_id: str, is_sandbox: bool) -> str:
    env = APPLE_ENVIRONMENT_SANDBOX if is_sandbox else APPLE_ENVIRONMENT_PRODUCTION
    return f"apple:{env}:{original_transaction_id}"


async def find_apple_entitlement(
    db: AsyncSession,
    *,
    original_transaction_id: str,
    is_sandbox: bool,
) -> Optional[BillingEntitlement]:
    return (
        await db.execute(
            select(BillingEntitlement).where(
                BillingEntitlement.provider == PROVIDER_APPLE,
                BillingEntitlement.provider_subscription_id == original_transaction_id,
                BillingEntitlement.is_test_mode == is_sandbox,
            )
        )
    ).scalars().first()


async def find_user_apple_entitlement(
    db: AsyncSession,
    user: User,
    *,
    original_transaction_id: str,
    is_sandbox: bool,
) -> Optional[BillingEntitlement]:
    """Same Apple identity as find_apple_entitlement, scoped to the JWT user."""
    return (
        await db.execute(
            select(BillingEntitlement).where(
                BillingEntitlement.user_id == user.id,
                BillingEntitlement.provider == PROVIDER_APPLE,
                BillingEntitlement.provider_subscription_id == original_transaction_id,
                BillingEntitlement.is_test_mode == is_sandbox,
            )
        )
    ).scalars().first()


async def opposite_environment_blocks_apple_verify(
    db: AsyncSession,
    *,
    original_transaction_id: str,
    is_sandbox: bool,
) -> bool:
    """Client verify must not create the opposite-environment row for the same OTID."""
    same = await find_apple_entitlement(
        db,
        original_transaction_id=original_transaction_id,
        is_sandbox=is_sandbox,
    )
    if same is not None:
        return False
    other = await find_apple_entitlement(
        db,
        original_transaction_id=original_transaction_id,
        is_sandbox=not is_sandbox,
    )
    return other is not None


def already_current_apple_verify(
    user: User,
    verified: AppleVerifiedTransaction,
    decision: AppleGrantDecision,
    row: Optional[BillingEntitlement],
) -> bool:
    """True when a stale client verify is the same live Apple subscription.

    Used only after upsert returns stale_notification. Does not mutate the row.
    """
    if row is None or user is None or verified is None or decision is None:
        return False
    if getattr(row, "provider", None) != PROVIDER_APPLE:
        return False
    if int(getattr(row, "user_id", 0) or 0) != int(getattr(user, "id", 0) or 0):
        return False
    if bool(row.is_test_mode) != bool(decision.is_sandbox):
        return False
    incoming_env = normalize_apple_environment(verified.environment or "")
    if incoming_env is None:
        return False
    if apple_environment_from_flag(bool(row.is_test_mode)) != incoming_env:
        return False
    if (row.provider_subscription_id or "") != (verified.original_transaction_id or ""):
        return False
    return apple_entitlement_is_live(row)


async def upsert_verified_apple_entitlement(
    db: AsyncSession,
    user: User,
    verified: AppleVerifiedTransaction,
    decision: AppleGrantDecision,
    *,
    status: str = STATUS_ACTIVE,
    reconcile: bool = True,
) -> tuple[Optional[BillingEntitlement], str]:
    """Insert or update the matching environment row only."""
    if not decision.allowed and status == STATUS_ACTIVE:
        return None, decision.reason
    if not verified.original_transaction_id:
        return None, "missing_original_transaction_id"
    is_sandbox = bool(decision.is_sandbox)
    existing = await find_apple_entitlement(
        db,
        original_transaction_id=verified.original_transaction_id,
        is_sandbox=is_sandbox,
    )
    if existing is not None:
        mutate = apple_lifecycle_may_mutate(
            existing,
            original_transaction_id=verified.original_transaction_id,
            environment=apple_environment_from_flag(is_sandbox),
        )
        if mutate != "ok":
            return existing, mutate
        if incoming_signed_is_stale(existing, verified.signed_date):
            return existing, "stale_notification"
    else:
        existing = BillingEntitlement(
            user_id=user.id,
            provider=PROVIDER_APPLE,
            provider_subscription_id=verified.original_transaction_id,
            checkout_reference=apple_checkout_reference(
                verified.original_transaction_id, is_sandbox,
            ),
            is_test_mode=is_sandbox,
            tier=decision.tier or "pro",
            billing_period=decision.billing_period or "monthly",
            status=STATUS_ACTIVE,
            paid_verified=False,
        )
        db.add(existing)
        await db.flush()

    product = get_apple_product(verified.product_id)
    existing.user_id = user.id
    existing.provider_plan_id = verified.product_id
    if product is not None:
        existing.tier = product.tier
        existing.billing_period = product.billing_period
    elif decision.tier:
        existing.tier = decision.tier
        existing.billing_period = decision.billing_period or existing.billing_period
    existing.status = status
    existing.paid_verified = True
    existing.is_test_mode = is_sandbox
    if verified.original_purchase_date and existing.started_at is None:
        existing.started_at = verified.original_purchase_date
    if verified.expires_at is not None:
        existing.current_period_end = verified.expires_at
    if verified.transaction_id:
        existing.last_successful_transaction_id = verified.transaction_id
    if status in {STATUS_REVOKED, STATUS_EXPIRED}:
        existing.canceled_at = existing.canceled_at or _now()
        if status == STATUS_REVOKED and verified.transaction_id:
            existing.last_refund_transaction_id = verified.transaction_id
    elif status == STATUS_ACTIVE:
        existing.canceled_at = None
    if verified.signed_date is not None:
        existing.last_provider_signed_at = verified.signed_date
    await db.flush()
    if reconcile:
        await reconcile_user_access(db, user.id)
    if status == STATUS_ACTIVE:
        await _set_compat_cancel_at_period_end(db, existing, False)
    logger.info(
        "apple entitlement upsert decision=%s env=%s product=%s original=%s txn=%s user_id=%s",
        status,
        apple_environment_from_flag(is_sandbox),
        verified.product_id,
        mask_apple_id(verified.original_transaction_id),
        mask_apple_id(verified.transaction_id),
        user.id,
    )
    return existing, "applied"


async def _set_compat_cancel_at_period_end(
    db: AsyncSession,
    row: BillingEntitlement,
    cancel_at_period_end: bool,
) -> None:
    """Persist Apple cancel-at-period-end on the non-Stripe compat subscription only."""
    if not row.compatibility_subscription_id:
        return
    compat = (
        await db.execute(
            select(Subscription).where(Subscription.id == row.compatibility_subscription_id)
        )
    ).scalars().first()
    if compat is None or compat.stripe_subscription_id:
        return
    compat.cancel_at_period_end = cancel_at_period_end
    await db.flush()


async def apply_apple_status_update(
    db: AsyncSession,
    row: BillingEntitlement,
    *,
    original_transaction_id: str,
    environment: str,
    status: str,
    signed_at: Optional[datetime] = None,
    product_id: Optional[str] = None,
    period_end: Optional[datetime] = None,
    transaction_id: Optional[str] = None,
    cancel_at_period_end: Optional[bool] = None,
    reconcile: bool = True,
) -> str:
    reason = apple_lifecycle_may_mutate(
        row,
        original_transaction_id=original_transaction_id,
        environment=environment,
    )
    if reason != "ok":
        return reason
    if incoming_signed_is_stale(row, signed_at):
        return "stale_notification"
    previous_test_mode = bool(row.is_test_mode)
    row.status = status
    if product_id:
        product = get_apple_product(product_id)
        if product is not None:
            row.provider_plan_id = product.product_id
            row.tier = product.tier
            row.billing_period = product.billing_period
    if period_end is not None:
        row.current_period_end = period_end
    if transaction_id:
        row.last_successful_transaction_id = transaction_id
        if status == STATUS_REVOKED:
            row.last_refund_transaction_id = transaction_id
    if status in {STATUS_REVOKED, STATUS_EXPIRED}:
        row.canceled_at = row.canceled_at or _now()
    elif status == STATUS_ACTIVE:
        row.canceled_at = None
    if signed_at is not None:
        row.last_provider_signed_at = signed_at
    row.is_test_mode = previous_test_mode
    await db.flush()
    if reconcile:
        await reconcile_user_access(db, row.user_id)
    if cancel_at_period_end is not None:
        await _set_compat_cancel_at_period_end(db, row, cancel_at_period_end)
    return "applied"
