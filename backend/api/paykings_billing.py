"""Authenticated PayKings checkout initialization.

POST /api/billing/paykings/checkout

Creates a pending BillingCheckout bound to the JWT user and a known plan ID.
Does not call PayKings and does not change entitlements.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.utils import wrap_data
from models.database import get_db
from models.domain import User
from services.paykings_billing import checkout_public_payload, create_pending_checkout, submit_add_subscription
from services.paykings_client import PayKingsNotConfigured, PayKingsProviderError
from services.paykings_plans import get_plan

router = APIRouter(tags=["Billing"])


class PayKingsCheckoutRequest(BaseModel):
    plan_id: str
    model_config = ConfigDict(extra="ignore")


class PayKingsSubscribeRequest(BaseModel):
    plan_id: str
    payment_token: str
    checkout_reference: str | None = None
    model_config = ConfigDict(extra="ignore")


@router.post("/paykings/checkout")
async def create_paykings_checkout(
    body: PayKingsCheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = get_plan(body.plan_id)
    if plan is None:
        raise HTTPException(status_code=400, detail="Unsupported plan_id")
    row = await create_pending_checkout(db, user.id, plan.plan_id)
    return wrap_data(checkout_public_payload(row, plan), source="live")


@router.post("/paykings/subscribe")
async def subscribe_paykings_checkout(
    body: PayKingsSubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create/reuse a pending checkout, then add_subscription via Collect.js token.

    Frontend cannot set orderid, user_id, price, or tier. payment_token is not stored.
    """
    plan = get_plan(body.plan_id)
    if plan is None:
        raise HTTPException(status_code=400, detail="Unsupported plan_id")
    try:
        row, parsed = await submit_add_subscription(
            db,
            user.id,
            plan.plan_id,
            body.payment_token,
            checkout_reference=body.checkout_reference,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "unsupported_plan_id":
            raise HTTPException(status_code=400, detail="Unsupported plan_id") from exc
        if code == "payment_token_required":
            raise HTTPException(status_code=400, detail="payment_token is required") from exc
        if code == "checkout_not_found":
            raise HTTPException(status_code=404, detail="Checkout not found") from exc
        if code == "plan_mismatch":
            raise HTTPException(status_code=400, detail="Checkout plan mismatch") from exc
        raise HTTPException(status_code=400, detail="Invalid subscribe request") from exc
    except PayKingsNotConfigured as exc:
        raise HTTPException(status_code=503, detail="PayKings is not configured") from exc
    except PayKingsProviderError as exc:
        raise HTTPException(status_code=502, detail="PayKings subscription request failed") from exc
    payload = checkout_public_payload(row, plan)
    payload["provider_approved"] = parsed.approved
    return wrap_data(payload, source="live")
