import stripe
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models.domain import User, Subscription, StripeEvent

# Fetch from environment (Production Safety)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Plan ID mapping (Default to test if not set)
PLAN_PRICE_MAP = {
    "Pro Arena": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_test"),
    "Elite Stack": os.getenv("STRIPE_ELITE_PRICE_ID", "price_elite_test"),
}

class StripeService:
    @staticmethod
    def create_checkout_session(user_email: str, plan_name: str, success_url: str, cancel_url: str) -> str:
        """Create a Stripe Checkout Session for a subscription."""
        try:
            price_id = PLAN_PRICE_MAP.get(plan_name)
            if not price_id:
                raise ValueError(f"Invalid plan name: {plan_name}")

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                customer_email=user_email,
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata={"plan_name": plan_name}
            )
            return session.url
        except Exception as e:
            print(f"Stripe Checkout Error: {e}")
            raise

    @staticmethod
    def create_portal_session(stripe_customer_id: str, return_url: str) -> str:
        """Create a Stripe Customer Portal session."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=return_url,
            )
            return session.url
        except Exception as e:
            print(f"Stripe Portal Error: {e}")
            raise

    @staticmethod
    def handle_webhook_event(payload: bytes, sig_header: str, db: Session):
        """Construct and handle Stripe webhook events with signature verification and idempotency."""
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            raise ValueError(f"Invalid Webhook: {e}")

        # Idempotency Check
        existing_event = db.query(StripeEvent).filter(StripeEvent.event_id == event['id']).first()
        if existing_event:
            print(f"Duplicate Webhook: {event['id']}. Skipping.")
            return

        # Record Event
        new_event = StripeEvent(event_id=event['id'], event_type=event['type'])
        db.add(new_event)
        db.flush() # Flush to lock the ID

        data_object = event['data']['object']
        
        if event['type'] == 'checkout.session.completed':
            StripeService._handle_checkout_completed(data_object, db)
        elif event['type'] in ['customer.subscription.updated', 'customer.subscription.deleted']:
            StripeService._handle_subscription_updated(data_object, db)
        elif event['type'] == 'invoice.payment_succeeded':
            StripeService._handle_payment_succeeded(data_object, db)
        elif event['type'] == 'invoice.payment_failed':
            StripeService._handle_payment_failed(data_object, db)

        db.commit()

    @staticmethod
    def _handle_payment_failed(invoice: Dict[str, Any], db: Session):
        """Handle failed subscription payments - downgrade access."""
        customer_id = invoice.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            # Downgrade immediately on failure (Production Strictness)
            user.is_pro = False
            if user.subscription:
                user.subscription.status = "past_due"
            print(f"PAYMENT FAILED: User {user.email} (Customer {customer_id}) downgraded.")

    @staticmethod
    def _handle_payment_succeeded(invoice: Dict[str, Any], db: Session):
        """Handle successful payment - log revenue."""
        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid", 0) / 100
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            print(f"REVENUE LOG: User {user.email} paid ${amount_paid}")
            # Optionally add to a dedicated Revenue table if requested later
    @staticmethod
    def _handle_checkout_completed(session: Dict[str, Any], db: Session):
        """Handle initial checkout and link user to stripe customer."""
        email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.stripe_customer_id = customer_id
            # Sync subscription status
            StripeService._sync_subscription(subscription_id, user, db)
            db.commit()

    @staticmethod
    def _handle_subscription_updated(stripe_subscription: Dict[str, Any], db: Session):
        """Update local subscription state when stripe changes."""
        subscription_id = stripe_subscription.get("id")
        customer_id = stripe_subscription.get("customer")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            StripeService._sync_subscription(subscription_id, user, db)
            db.commit()

    @staticmethod
    def _sync_subscription(stripe_id: str, user: User, db: Session):
        """Core sync logic: Map Stripe subscription data to our database."""
        try:
            subscription = stripe.Subscription.retrieve(stripe_id)
            plan_id = subscription['items']['data'][0]['price']['id']
            
            # Map back price ID to our plan names
            plan_name = "Starter"
            for name, pid in PLAN_PRICE_MAP.items():
                if pid == plan_id:
                    plan_name = name
                    break

            # Find or create local subscription
            local_sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_id).first()
            if not local_sub:
                local_sub = Subscription(stripe_subscription_id=stripe_id, user_id=user.id)
                db.add(local_sub)
            
            local_sub.plan_name = plan_name
            local_sub.status = subscription['status']
            local_sub.cancel_at_period_end = subscription['cancel_at_period_end']
            local_sub.current_period_end = datetime.fromtimestamp(subscription['current_period_end'], tz=timezone.utc)
            local_sub.mrr_value = subscription['items']['data'][0]['price']['unit_amount'] / 100
            
            # Update user relation
            user.active_subscription_id = local_sub.id
            user.is_pro = local_sub.status in ['active', 'trialing']
        except Exception as e:
            print(f"Subscription Sync Error: {e}")
            db.rollback()
