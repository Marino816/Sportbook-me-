"""PayKings checkout binding, provider submit, and webhook correlation.

No entitlement writes (User.is_pro / Subscription / active_subscription_id).

orderid on transact.php = BillingCheckout.checkout_reference (pkchk_...).
recurring.subscription.add resolves event_body.order_id -> checkout_reference.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import BillingCheckout
from services.paykings_client import PayKingsClient, PayKingsProviderError, PayKingsTransactResponse
from services.paykings_plans import PayKingsPlan, get_plan, recognized_plan_id
from services.paykings_webhooks import (
    EVENT_RECURRING_CANCELED,
    EVENT_RECURRING_CREATED,
    EVENT_RECURRING_UPDATED,
)

logger = logging.getLogger(__name__)

PROVIDER = "paykings"
CHECKOUT_REFERENCE_PREFIX = "pkchk_"
STATUS_PENDING = "pending"
STATUS_SUBMITTED = "submitted"
STATUS_BOUND = "bound"
STATUS_UNRESOLVED = "unresolved"
STATUS_ERROR = "error"
STATUS_DELETE_RECORDED = "delete_recorded"

# Confirmed: merchant orderid is echoed as event_body.order_id on recurring webhooks.
ORDER_ID_RECURRING_CORRELATION_ENABLED = True


def new_checkout_reference() -> str:
    """Unguessable reference. Never encode the numeric user id."""
    return f"{CHECKOUT_REFERENCE_PREFIX}{uuid.uuid4().hex}"


def is_paykings_test_event(extracted: dict[str, Any] | None) -> bool:
    if not isinstance(extracted, dict):
        return False
    value = extracted.get("is_test_mode")
    features = extracted.get("features")
    if value is None and isinstance(features, dict):
        value = features.get("is_test_mode")
    return value in (True, 1, "1", "true", "True")


def reject_test_mode_for_production_entitlement(extracted: dict[str, Any] | None) -> bool:
    """Future entitlement writes must no-op when this returns True."""
    return is_paykings_test_event(extracted)


async def create_pending_checkout(db: AsyncSession, user_id: int, plan_id: str) -> BillingCheckout:
    plan = get_plan(plan_id)
    if plan is None:
        raise ValueError("unsupported_plan_id")
    for _ in range(5):
        row = BillingCheckout(
            user_id=user_id,
            provider=PROVIDER,
            checkout_reference=new_checkout_reference(),
            provider_plan_id=plan.plan_id,
            tier=plan.tier,
            billing_period=plan.billing_period,
            status=STATUS_PENDING,
        )
        db.add(row)
        try:
            await db.flush()
            await db.commit()
            await db.refresh(row)
            return row
        except IntegrityError:
            await db.rollback()
    raise RuntimeError("checkout_reference_collision")


def checkout_public_payload(row: BillingCheckout, plan: PayKingsPlan) -> dict[str, Any]:
    return {
        "checkout_reference": row.checkout_reference,
        "provider": row.provider,
        "plan_id": plan.plan_id,
        "tier": plan.tier,
        "billing_period": plan.billing_period,
        "expected_price": float(plan.expected_price),
        "status": row.status,
    }


async def load_checkout_for_user(
    db: AsyncSession, user_id: int, checkout_reference: str,
) -> Optional[BillingCheckout]:
    return (
        await db.execute(
            select(BillingCheckout).where(
                BillingCheckout.provider == PROVIDER,
                BillingCheckout.checkout_reference == checkout_reference,
                BillingCheckout.user_id == user_id,
            )
        )
    ).scalars().first()


def _apply_provider_response(row: BillingCheckout, parsed: PayKingsTransactResponse) -> None:
    if parsed.transactionid:
        row.provider_transaction_id = parsed.transactionid
    if parsed.customer_vault_id:
        row.provider_customer_id = parsed.customer_vault_id
    if parsed.subscription_id:
        row.provider_subscription_id = parsed.subscription_id
        row.status = STATUS_BOUND
    else:
        row.status = STATUS_SUBMITTED
    row.updated_at = datetime.now(timezone.utc)


async def submit_add_subscription(
    db: AsyncSession,
    user_id: int,
    plan_id: str,
    payment_token: str,
    *,
    checkout_reference: Optional[str] = None,
    client: Optional[PayKingsClient] = None,
) -> tuple[BillingCheckout, PayKingsTransactResponse]:
    """Persist checkout_reference first, then POST add_subscription.

    orderid is always the server checkout_reference. payment_token is not stored.
    """
    plan = get_plan(plan_id)
    if plan is None:
        raise ValueError("unsupported_plan_id")
    token = (payment_token or "").strip()
    if not token:
        raise ValueError("payment_token_required")

    if checkout_reference:
        row = await load_checkout_for_user(db, user_id, checkout_reference.strip())
        if row is None:
            raise ValueError("checkout_not_found")
        if row.provider_plan_id != plan.plan_id:
            raise ValueError("plan_mismatch")
    else:
        row = await create_pending_checkout(db, user_id, plan.plan_id)

    client = client or PayKingsClient()
    try:
        parsed = await client.create_subscription(
            plan_id=plan.plan_id,
            payment_token=token,
            order_id=row.checkout_reference,
        )
    except PayKingsProviderError:
        row.status = STATUS_ERROR
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise
    _apply_provider_response(row, parsed)
    await db.commit()
    await db.refresh(row)
    return row, parsed


async def resolve_billing_checkout(
    db: AsyncSession,
    *,
    provider_subscription_id: Optional[str] = None,
    checkout_reference: Optional[str] = None,
    provider_customer_id: Optional[str] = None,
    allow_order_id_correlation: bool = ORDER_ID_RECURRING_CORRELATION_ENABLED,
) -> Optional[BillingCheckout]:
    """A. provider_subscription_id  B. checkout_reference  C. provider_customer_id."""
    if provider_subscription_id:
        row = (
            await db.execute(
                select(BillingCheckout).where(
                    BillingCheckout.provider == PROVIDER,
                    BillingCheckout.provider_subscription_id == str(provider_subscription_id),
                )
            )
        ).scalars().all()
        if len(row) == 1:
            return row[0]
        if len(row) > 1:
            logger.error("paykings resolve: multiple rows for provider_subscription_id")
            return None
        return None

    if allow_order_id_correlation and checkout_reference:
        matches = (
            await db.execute(
                select(BillingCheckout).where(
                    BillingCheckout.provider == PROVIDER,
                    BillingCheckout.checkout_reference == str(checkout_reference),
                )
            )
        ).scalars().all()
        if len(matches) == 1:
            return matches[0]
        return None

    if provider_customer_id:
        matches = (
            await db.execute(
                select(BillingCheckout).where(
                    BillingCheckout.provider == PROVIDER,
                    BillingCheckout.provider_customer_id == str(provider_customer_id),
                )
            )
        ).scalars().all()
        if len(matches) == 1:
            return matches[0]
        return None

    return None


async def resolve_for_cancellation(
    db: AsyncSession,
    provider_subscription_id: Optional[str],
) -> Optional[BillingCheckout]:
    if not provider_subscription_id:
        return None
    return await resolve_billing_checkout(
        db, provider_subscription_id=provider_subscription_id,
    )


async def attach_provider_identifiers(
    db: AsyncSession,
    checkout: BillingCheckout,
    *,
    provider_subscription_id: Optional[str] = None,
    provider_customer_id: Optional[str] = None,
    provider_transaction_id: Optional[str] = None,
) -> BillingCheckout:
    if provider_subscription_id:
        checkout.provider_subscription_id = str(provider_subscription_id)
    if provider_customer_id:
        checkout.provider_customer_id = str(provider_customer_id)
    if provider_transaction_id:
        checkout.provider_transaction_id = str(provider_transaction_id)
    checkout.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(checkout)
    return checkout


def _webhook_plan_id(extracted: dict[str, Any]) -> Optional[str]:
    plan = extracted.get("plan") if isinstance(extracted.get("plan"), dict) else {}
    return str(plan["id"]).strip() if plan.get("id") is not None else None


async def bind_recurring_add(db: AsyncSession, extracted: dict[str, Any]) -> str:
    """Bind recurring.subscription.add. Does not grant entitlements."""
    order_id = extracted.get("order_id")
    subscription_id = extracted.get("subscription_id")
    plan_id = _webhook_plan_id(extracted)
    if not order_id:
        logger.info("paykings add unresolved: missing order_id")
        return STATUS_UNRESOLVED
    checkout = await resolve_billing_checkout(db, checkout_reference=str(order_id))
    if checkout is None:
        logger.info("paykings add unresolved: unknown order_id")
        return STATUS_UNRESOLVED
    if not plan_id or recognized_plan_id(plan_id) is None:
        logger.info("paykings add error: unknown plan.id")
        checkout.status = STATUS_ERROR
        await db.flush()
        return STATUS_ERROR
    if checkout.provider_plan_id != plan_id:
        logger.info(
            "paykings add error: plan mismatch checkout=%s webhook=%s",
            checkout.provider_plan_id,
            plan_id,
        )
        checkout.status = STATUS_ERROR
        await db.flush()
        return STATUS_ERROR
    if not subscription_id:
        logger.info("paykings add unresolved: missing subscription_id")
        return STATUS_UNRESOLVED
    if checkout.provider_subscription_id and checkout.provider_subscription_id != str(subscription_id):
        logger.info("paykings add error: checkout already bound to a different subscription")
        return STATUS_ERROR
    other = await resolve_billing_checkout(db, provider_subscription_id=str(subscription_id))
    if other is not None and other.id != checkout.id:
        logger.info("paykings add error: duplicate provider_subscription_id")
        return STATUS_ERROR
    checkout.provider_subscription_id = str(subscription_id)
    checkout.status = STATUS_BOUND
    checkout.updated_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info(
        "paykings add bound checkout=%s subscription_id=%s test_mode=%s (no entitlement write)",
        checkout.checkout_reference,
        subscription_id,
        is_paykings_test_event(extracted),
    )
    return "processed"


async def record_recurring_update(db: AsyncSession, extracted: dict[str, Any]) -> str:
    subscription_id = extracted.get("subscription_id")
    checkout = await resolve_billing_checkout(db, provider_subscription_id=subscription_id)
    if checkout is None:
        logger.info("paykings update unresolved: unknown subscription_id")
        return STATUS_UNRESOLVED
    logger.info(
        "paykings update recorded subscription_id=%s user_id=%s (no entitlement write)",
        subscription_id,
        checkout.user_id,
    )
    return "processed"


async def record_recurring_delete(db: AsyncSession, extracted: dict[str, Any]) -> str:
    subscription_id = extracted.get("subscription_id")
    checkout = await resolve_for_cancellation(db, subscription_id)
    if checkout is None:
        logger.info("paykings delete unresolved: unknown subscription_id (no revoke)")
        return STATUS_UNRESOLVED
    checkout.status = STATUS_DELETE_RECORDED
    checkout.updated_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info(
        "paykings delete recorded subscription_id=%s user_id=%s (no entitlement revoke)",
        subscription_id,
        checkout.user_id,
    )
    return "processed"


async def apply_recurring_webhook(
    db: AsyncSession, event_type: Optional[str], extracted: dict[str, Any],
) -> str:
    if event_type == EVENT_RECURRING_CREATED:
        return await bind_recurring_add(db, extracted)
    if event_type == EVENT_RECURRING_UPDATED:
        return await record_recurring_update(db, extracted)
    if event_type == EVENT_RECURRING_CANCELED:
        return await record_recurring_delete(db, extracted)
    # sale.unknown, refund.*, and acu.summary.* are record-only.
    return "processed"
