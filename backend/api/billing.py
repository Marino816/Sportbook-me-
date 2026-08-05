from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from pydantic import BaseModel
import os
import json

from models.database import get_db, SyncSessionLocal
from models.domain import User, Subscription
from services.stripe_service import StripeService
from api.utils import wrap_data
from api.auth import get_current_user, require_admin

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """Initiate a Stripe Checkout session for a chosen plan."""
    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        success_url = f"{frontend_url}/billing?success=true"
        cancel_url = f"{frontend_url}/billing?canceled=true"
        
        session_url = StripeService.create_checkout_session(
            user.email, user.id, body.plan, success_url, cancel_url
        )
        return wrap_data({"url": session_url})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/portal")
async def create_portal(
    user: User = Depends(get_current_user)
):
    """Generate a link for the Stripe Customer Portal."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active Stripe customer found.")
        
    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return_url = f"{frontend_url}/billing"
        portal_url = StripeService.create_portal_session(user.stripe_customer_id, return_url)
        return wrap_data({"url": portal_url})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None)
):
    """Handle incoming Stripe events (subscriptions, payments)."""
    payload = await request.body()
    
    # We use a sync session here because StripeService logic is sync
    db = SyncSessionLocal()
    try:
        StripeService.handle_webhook_event(payload, stripe_signature, db)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.get("/status")
async def get_subscription_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current user's subscription and plan status."""
    if not user.active_subscription_id:
        return wrap_data({
            "plan": "Starter",
            "status": "free",
            "next_billing": None,
            "trial_end": None,
            "has_access": False
        }, source="live")
        
    result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
    sub = result.scalars().first()
    
    return wrap_data({
        "plan": sub.plan_name,
        "status": sub.status,
        "next_billing": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "is_canceled": sub.cancel_at_period_end,
        "has_access": sub.status in ['active', 'trialing']
    }, source="live")


# ── Admin / Self-service: force sync ─────────────────────────

@router.post("/sync")
async def force_sync_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force a re-sync of the current user's subscription from Stripe."""
    if not user.active_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription to sync.")

    result = await db.execute(
        select(Subscription).where(Subscription.id == user.active_subscription_id)
    )
    sub = result.scalars().first()
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No Stripe subscription found.")

    # Run sync in a sync session (StripeService uses sync SQLAlchemy)
    sync_db = SyncSessionLocal()
    try:
        StripeService._sync_subscription(sub.stripe_subscription_id, user, sync_db)
        sync_db.commit()
        return wrap_data({"status": "synced"}, source="stripe")
    except Exception as e:
        sync_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        sync_db.close()