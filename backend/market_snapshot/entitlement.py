"""Paid-plan entitlement for Market Tools internal routes.

Active or trialing status is not enough. The subscription plan must include
Market Tools. Existing paid SKUs are Pro Arena and Elite Stack (monthly/annual,
Stripe names, and PayKings plan IDs). Starter and unrecognized plans do not.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from models.database import get_db
from models.domain import Subscription, User
from services.paykings_plans import SBME_PLANS, get_plan

MARKET_TOOLS_PLAN_NAMES = frozenset({
    "Pro Arena",
    "Pro Arena Annual",
    "Elite Stack",
    "Elite Stack Annual",
})

MARKET_TOOLS_PLAN_IDS = frozenset(SBME_PLANS.keys())

PAID_STATUSES = frozenset({"active", "trialing"})


def _period_end(sub) -> datetime | None:
    if sub is None:
        return None
    end = getattr(sub, "current_period_end", None)
    if end is None:
        return None
    if isinstance(end, str):
        text = end.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            end = datetime.fromisoformat(text)
        except ValueError:
            return None
    if getattr(end, "tzinfo", None) is None:
        end = end.replace(tzinfo=timezone.utc)
    return end


def plan_includes_market_tools(plan_name: str | None) -> bool:
    """True only for catalog SKUs that include Market Tools. Unknown names stay out."""
    name = (plan_name or "").strip()
    if not name:
        return False
    if name in MARKET_TOOLS_PLAN_NAMES or name in MARKET_TOOLS_PLAN_IDS:
        return True
    if name.startswith("Pro Arena") or name.startswith("Elite Stack"):
        return True
    mapped = get_plan(name)
    return bool(mapped and mapped.tier in {"pro", "elite"})


async def plan_entitlement(user: User, db: AsyncSession) -> dict:
    plan = "Starter"
    entitled = False
    status_name = "free"
    feature = "market_tools"
    if (user.role or "") == "admin":
        entitled = True
        plan = "admin"
        status_name = "admin"
        return {
            "entitled": entitled,
            "plan": plan,
            "status": status_name,
            "user_id": user.id,
            "feature": feature,
            "plan_includes_market_tools": True,
            "cancel_at_period_end": False,
            "paid_through": True,
            "current_period_end": None,
        }

    sub = None
    if user.active_subscription_id:
        result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
        sub = result.scalars().first()
        if sub and sub.plan_name:
            plan = sub.plan_name
        if sub and sub.status:
            status_name = sub.status

    includes = plan_includes_market_tools(plan)
    period_end = _period_end(sub)
    paid_through = bool(period_end and period_end > datetime.now(timezone.utc))
    cancel_at_period_end = bool(sub and getattr(sub, "cancel_at_period_end", False))
    if includes and sub:
        if sub.status in PAID_STATUSES:
            entitled = True
        elif sub.status == "canceled" and paid_through:
            # Renewal canceled; access continues through the paid period. PayKings unchanged.
            entitled = True
    return {
        "entitled": entitled,
        "plan": plan,
        "status": status_name,
        "user_id": user.id,
        "feature": feature,
        "plan_includes_market_tools": includes,
        "cancel_at_period_end": cancel_at_period_end,
        "paid_through": paid_through,
        "current_period_end": period_end.isoformat() if period_end else None,
    }


async def require_market_tools_entitlement(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    info = await plan_entitlement(user, db)
    if info["entitled"]:
        user._mt_entitlement = info  # type: ignore[attr-defined]
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "unavailable": True,
            "entitled": False,
            "plan": info["plan"],
            "status": info["status"],
            "plan_includes_market_tools": info["plan_includes_market_tools"],
            "reason": (
                "Market Tools requires an active or paid-through Pro Arena or Elite Stack plan. "
                "Authentication, is_pro, or an unrelated active subscription is not enough. "
                "A canceled renewal keeps access only until current_period_end."
            ),
        },
    )
