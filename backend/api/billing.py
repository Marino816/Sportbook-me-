from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from pydantic import BaseModel
import os
import json

from models.database import get_db, SyncSessionLocal
from models.domain import User, Subscription
from services.entitlements import effective_access_for_user
from services.stripe_service import StripeService
from api.utils import wrap_data
from api.auth import get_current_user, require_admin

router = APIRouter()


def _get_canonical_frontend_url() -> str:
    """Return a single canonical frontend URL for Stripe redirects.
    
    Uses PUBLIC_FRONTEND_URL if set, otherwise extracts the first origin
    from the comma-separated CORS FRONTEND_URL allowlist.
    """
    canonical = os.getenv("PUBLIC_FRONTEND_URL", "").strip()
    if canonical:
        return canonical
    raw = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return raw.split(",")[0].strip()


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
        frontend_url = _get_canonical_frontend_url()
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
        frontend_url = _get_canonical_frontend_url()
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
    access = await effective_access_for_user(db, user)
    sub = None
    if user.active_subscription_id:
        result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
        sub = result.scalars().first()
    return wrap_data({
        "plan": access.plan_name,
        "status": access.status,
        "next_billing": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "trial_end": sub.trial_end.isoformat() if sub and sub.trial_end else None,
        "is_canceled": bool(sub.cancel_at_period_end) if sub else False,
        "has_access": access.is_pro,
        "provider": access.provider,
    }, source="live")


# ── Admin / Self-service: force sync ─────────────────────────

@router.post("/sync")
async def force_sync_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force a re-sync of the current user's Stripe subscription."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.stripe_subscription_id.isnot(None),
        )
    )
    sub = result.scalars().first()
    if sub is None and user.active_subscription_id:
        fallback = await db.execute(
            select(Subscription).where(Subscription.id == user.active_subscription_id)
        )
        candidate = fallback.scalars().first()
        if candidate and candidate.stripe_subscription_id:
            sub = candidate
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