"""Account billing status and processor-backed cancellation."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import BillingEntitlement, Subscription, User
from services.paykings_plans import get_plan, plan_from_display_name
from services.paykings_recurring import (
    PayKingsNotConfigured,
    PayKingsProviderError,
    PayKingsRecurringClient,
)

logger = logging.getLogger(__name__)

PROVIDER_PAYKINGS = "paykings"
PROVIDER_STRIPE = "stripe"
PROVIDER_NONE = "none"
PURCHASES_PAUSED_DETAIL = "New purchases and upgrades are paused."


class BillingCancelError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def purchases_paused() -> bool:
    raw = os.getenv("BILLING_PURCHASES_PAUSED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    moment = _as_utc(value)
    return moment.isoformat() if moment else None


def _amount_number(value: Optional[Decimal | float | str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except Exception:
        return None


async def load_paykings_entitlement(db: AsyncSession, user_id: int) -> Optional[BillingEntitlement]:
    rows = (
        await db.execute(
            select(BillingEntitlement).where(
                BillingEntitlement.user_id == user_id,
                BillingEntitlement.provider == PROVIDER_PAYKINGS,
                BillingEntitlement.paid_verified.is_(True),
                BillingEntitlement.provider_subscription_id.isnot(None),
            )
        )
    ).scalars().all()
    if not rows:
        return None
    live = [row for row in rows if (row.status or "") == "active"]
    pool = live or list(rows)
    return max(pool, key=lambda row: row.id or 0)


async def load_subscription(db: AsyncSession, user: User) -> Optional[Subscription]:
    if not user.active_subscription_id:
        return None
    result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
    return result.scalars().first()


def _plan_facts(sub: Optional[Subscription], entitlement: Optional[BillingEntitlement]) -> dict[str, Any]:
    plan = get_plan((entitlement.provider_plan_id if entitlement else None) or "")
    if plan is None and sub is not None:
        plan = plan_from_display_name(sub.plan_name or "")
    amount = _amount_number(plan.expected_price) if plan else None
    if amount is None and sub is not None:
        amount = _amount_number(sub.mrr_value)
    interval = None
    if plan is not None:
        interval = plan.billing_period
    elif entitlement is not None:
        interval = entitlement.billing_period
    elif sub is not None and "annual" in (sub.plan_name or "").lower():
        interval = "annual"
    elif sub is not None and sub.plan_name and sub.plan_name != "Starter":
        interval = "monthly"
    display_name = plan.display_name if plan else None
    if not display_name and sub is not None:
        display_name = sub.plan_name
    return {
        "plan": display_name or "Starter",
        "amount": amount,
        "billing_interval": interval,
        "plan_id": plan.plan_id if plan else (entitlement.provider_plan_id if entitlement else None),
    }


def build_status_payload(
    user: User,
    sub: Optional[Subscription],
    entitlement: Optional[BillingEntitlement],
    *,
    now: Optional[datetime] = None,
    processor_confirmed: Optional[bool] = None,
    processor_message: Optional[str] = None,
) -> dict[str, Any]:
    moment = _as_utc(now) or datetime.now(timezone.utc)
    facts = _plan_facts(sub, entitlement)
    provider = PROVIDER_NONE
    if entitlement is not None:
        provider = PROVIDER_PAYKINGS
    elif sub is not None and sub.stripe_subscription_id:
        provider = PROVIDER_STRIPE
    elif sub is not None and (sub.plan_name or "Starter") != "Starter":
        provider = PROVIDER_STRIPE if user.stripe_customer_id else PROVIDER_PAYKINGS

    paid_through = None
    if entitlement is not None:
        paid_through = _as_utc(entitlement.current_period_end)
    if paid_through is None and sub is not None:
        paid_through = _as_utc(sub.current_period_end)

    is_canceled = False
    if entitlement is not None and entitlement.canceled_at is not None:
        is_canceled = True
    if sub is not None and bool(sub.cancel_at_period_end):
        is_canceled = True
    if sub is not None and (sub.status or "") == "canceled":
        is_canceled = True

    status_name = "free"
    has_access = False
    if sub is not None and (sub.status or "") in {"active", "trialing"}:
        status_name = sub.status
        has_access = paid_through is None or paid_through >= moment
    elif entitlement is not None and (entitlement.status or "") == "active" and entitlement.paid_verified:
        status_name = "active"
        has_access = paid_through is None or paid_through >= moment
    if facts["plan"] == "Starter":
        status_name = "free"
        has_access = False
        provider = PROVIDER_NONE
        is_canceled = False
        paid_through = None

    renewal_status = "none"
    if facts["plan"] != "Starter":
        renewal_status = "canceled" if is_canceled else "renewing"

    next_billing = None if is_canceled else _iso(paid_through)
    payload = {
        "plan": facts["plan"],
        "status": status_name,
        "provider": provider,
        "provider_display": "PayKings" if provider == PROVIDER_PAYKINGS else ("Stripe" if provider == PROVIDER_STRIPE else None),
        "amount": facts["amount"],
        "billing_interval": facts["billing_interval"],
        "plan_id": facts["plan_id"],
        "next_billing": next_billing,
        "paid_through": _iso(paid_through),
        "trial_end": _iso(sub.trial_end) if sub else None,
        "is_canceled": is_canceled,
        "renewal_status": renewal_status,
        "has_access": has_access,
        "can_cancel": bool(facts["plan"] != "Starter" and not is_canceled),
        "purchases_paused": purchases_paused(),
    }
    if processor_confirmed is not None:
        payload["processor_confirmed"] = processor_confirmed
    if processor_message:
        payload["processor_message"] = processor_message
    return payload


async def subscription_status(db: AsyncSession, user: User) -> dict[str, Any]:
    sub = await load_subscription(db, user)
    entitlement = await load_paykings_entitlement(db, user.id)
    return build_status_payload(user, sub, entitlement)


async def cancel_user_subscription(db: AsyncSession, user: User) -> dict[str, Any]:
    sub = await load_subscription(db, user)
    entitlement = await load_paykings_entitlement(db, user.id)
    current = build_status_payload(user, sub, entitlement)
    if current["plan"] == "Starter":
        raise BillingCancelError("No cancelable subscription", status_code=400)
    if current["is_canceled"] and current["provider"] == PROVIDER_PAYKINGS:
        client = PayKingsRecurringClient()
        sub_id = (entitlement.provider_subscription_id if entitlement else "") or ""
        if sub_id:
            try:
                remaining = await client.query_subscription(sub_id)
            except PayKingsNotConfigured as exc:
                raise BillingCancelError(str(exc), status_code=503) from exc
            except PayKingsProviderError as exc:
                raise BillingCancelError("Processor did not confirm cancellation", status_code=502) from exc
            if remaining is not None:
                parsed = await _delete_paykings(client, sub_id)
                await _mark_canceled(db, sub, entitlement, paid_through=entitlement.current_period_end if entitlement else None)
                return build_status_payload(
                    user,
                    sub,
                    entitlement,
                    processor_confirmed=True,
                    processor_message=parsed.responsetext,
                )
        return build_status_payload(
            user,
            sub,
            entitlement,
            processor_confirmed=True,
            processor_message="Cancellation already confirmed with the processor",
        )

    if current["provider"] == PROVIDER_PAYKINGS:
        sub_id = (entitlement.provider_subscription_id if entitlement else "") or ""
        if not sub_id:
            raise BillingCancelError("No PayKings subscription id on file", status_code=400)
        client = PayKingsRecurringClient()
        parsed = await _delete_paykings(client, sub_id)
        paid_through = entitlement.current_period_end if entitlement else (sub.current_period_end if sub else None)
        await _mark_canceled(db, sub, entitlement, paid_through=paid_through)
        await db.flush()
        return build_status_payload(
            user,
            sub,
            entitlement,
            processor_confirmed=True,
            processor_message=parsed.responsetext,
        )

    if current["provider"] == PROVIDER_STRIPE:
        if not sub or not sub.stripe_subscription_id:
            raise BillingCancelError("No Stripe subscription found", status_code=400)
        try:
            import stripe

            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
        except Exception as exc:
            logger.info("stripe cancel failed: %s", type(exc).__name__)
            raise BillingCancelError("Processor did not confirm cancellation", status_code=502) from exc
        await _mark_canceled(db, sub, None, paid_through=sub.current_period_end)
        await db.flush()
        return build_status_payload(
            user,
            sub,
            entitlement,
            processor_confirmed=True,
            processor_message="Stripe renewal set to cancel at period end",
        )

    raise BillingCancelError("No cancelable subscription", status_code=400)


async def _delete_paykings(client: PayKingsRecurringClient, subscription_id: str):
    try:
        return await client.delete_subscription(subscription_id)
    except PayKingsNotConfigured as exc:
        raise BillingCancelError(str(exc), status_code=503) from exc
    except PayKingsProviderError as exc:
        raise BillingCancelError("Processor did not confirm cancellation", status_code=502) from exc


async def _mark_canceled(
    db: AsyncSession,
    sub: Optional[Subscription],
    entitlement: Optional[BillingEntitlement],
    *,
    paid_through: Optional[datetime],
) -> None:
    now = datetime.now(timezone.utc)
    if sub is not None:
        sub.cancel_at_period_end = True
        if paid_through is not None:
            sub.current_period_end = paid_through
        if (sub.status or "") not in {"active", "trialing"}:
            sub.status = "active"
    if entitlement is not None:
        entitlement.canceled_at = entitlement.canceled_at or now
        entitlement.updated_at = now
        if paid_through is not None:
            entitlement.current_period_end = paid_through
        if entitlement.status != "active":
            entitlement.status = "active"
    await db.flush()
