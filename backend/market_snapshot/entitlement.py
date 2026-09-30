"""Paid-plan entitlement for Market Tools internal routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from models.database import get_db
from models.domain import Subscription, User


async def plan_entitlement(user: User, db: AsyncSession) -> dict:
    plan = "Starter"
    entitled = False
    status_name = "free"
    if (user.role or "") == "admin":
        entitled = True
        plan = "admin"
        status_name = "admin"
    elif user.is_pro:
        entitled = True
        plan = "pro_flag"
        status_name = "active"
    elif user.active_subscription_id:
        result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
        sub = result.scalars().first()
        if sub and sub.plan_name:
            plan = sub.plan_name
        if sub and sub.status in {"active", "trialing"}:
            entitled = True
            status_name = sub.status
    return {"entitled": entitled, "plan": plan, "status": status_name, "user_id": user.id}


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
            "reason": "Market Tools requires an active paid plan. Authentication alone is not enough.",
        },
    )
