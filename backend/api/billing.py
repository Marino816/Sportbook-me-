from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any
import os
import json

from models.database import get_db, SessionLocal
from models.domain import User, Subscription
from services.stripe_service import StripeService
from api.utils import wrap_data

router = APIRouter()

# Authentication dependency (Simulated for this demo architecture)
# In production, this would use a JWT token and set the current_user.
async def get_current_user(db: Session = Depends(get_db)):
    """Retrieve the current logged-in user from the database."""
    # For now, we'll fetch a default user for local testing
    result = await db.execute(select(User))
    user = result.scalars().first()
    if not user:
        # Create a default user in dev if none exists
        user = User(email="shark@apexdfs.io", is_pro=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

@router.post("/checkout")
async def create_checkout(
    plan: str, 
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Initiate a Stripe Checkout session for a chosen plan."""
    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        success_url = f"{frontend_url}/billing?success=true"
        cancel_url = f"{frontend_url}/billing?canceled=true"
        
        session_url = StripeService.create_checkout_session(
            user.email, plan, success_url, cancel_url
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
        return_url = "http://localhost:3000/billing"
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
    
    # We use a sync session here because StripeService logic is primarily sync
    db = SessionLocal()
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
    db: Session = Depends(get_db)
):
    """Get the current user's subscription and plan status."""
    if not user.active_subscription_id:
        return wrap_data({
            "plan": "Starter",
            "status": "free",
            "next_billing": None,
            "has_access": False
        }, source="live")
        
    result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
    sub = result.scalars().first()
    
    return wrap_data({
        "plan": sub.plan_name,
        "status": sub.status,
        "next_billing": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "is_canceled": sub.cancel_at_period_end,
        "has_access": sub.status in ['active', 'trialing']
    }, source="live")
