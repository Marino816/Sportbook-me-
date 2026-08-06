import stripe
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models.domain import User, Subscription, StripeEvent, RevenueLog

# Fetch from environment (Production Safety)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Plan ID mapping (Default to test if not set)
PLAN_PRICE_MAP = {
    "Pro Arena": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_test"),
    "Pro Arena Annual": os.getenv("STRIPE_PRO_ANNUAL_PRICE_ID", "price_pro_annual_test"),
    "Elite Stack": os.getenv("STRIPE_ELITE_PRICE_ID", "price_elite_test"),
    "Elite Stack Annual": os.getenv("STRIPE_ELITE_ANNUAL_PRICE_ID", "price_elite_annual_test"),
}


class StripeService:
    @staticmethod
    def create_checkout_session(
        user_email: str, user_id: int, plan_name: str,
        success_url: str, cancel_url: str,
    ) -> str:
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
                metadata={"plan_name": plan_name, "user_id": str(user_id)},
                allow_promotion_codes=True,
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

        # Idempotency Check — StripeEvent.event_id has a UNIQUE constraint
        existing_event = db.query(StripeEvent).filter(
            StripeEvent.event_id == event['id']
        ).first()
        if existing_event:
            print(f"Duplicate Webhook: {event['id']}. Skipping.")
            return

        # Record Event (idempotency ledger)
        new_event = StripeEvent(event_id=event['id'], event_type=event['type'])
        db.add(new_event)
        db.flush()  # Flush to lock the ID before processing

        data_object = event['data']['object']

        if event['type'] == 'checkout.session.completed':
            StripeService._handle_checkout_completed(data_object, db)
        elif event['type'] in (
            'customer.subscription.updated',
            'customer.subscription.deleted',
        ):
            StripeService._handle_subscription_updated(data_object, db)
        elif event['type'] == 'invoice.payment_succeeded':
            StripeService._handle_payment_succeeded(data_object, db)
        elif event['type'] == 'invoice.payment_failed':
            StripeService._handle_payment_failed(data_object, db)

        db.commit()

    # ── Private event handlers ────────────────────────────────

    @staticmethod
    def _handle_checkout_completed(session: Dict[str, Any], db: Session):
        """Handle initial checkout and link user to stripe customer."""
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        email = session.get("customer_email") or session.get(
            "customer_details", {}
        ).get("email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        # Prefer user_id from metadata, fall back to email
        user = None
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None and email:
            user = db.query(User).filter(User.email == email).first()

        if user:
            user.stripe_customer_id = customer_id
            StripeService._sync_subscription(subscription_id, user, db)
            # Do NOT commit here — outer handler commits at end of webhook processing

    @staticmethod
    def _handle_subscription_updated(
        stripe_subscription: Dict[str, Any], db: Session
    ):
        """Update local subscription state when stripe changes."""
        subscription_id = stripe_subscription.get("id")
        customer_id = stripe_subscription.get("customer")

        user = db.query(User).filter(
            User.stripe_customer_id == customer_id
        ).first()
        if user:
            StripeService._sync_subscription(subscription_id, user, db)
            # Do NOT commit here — outer handler commits at end of webhook processing

    @staticmethod
    def _handle_payment_succeeded(invoice: Dict[str, Any], db: Session):
        """Handle successful payment — log revenue."""
        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid", 0) / 100
        invoice_id = invoice.get("id")
        subscription_id = invoice.get("subscription")

        user = db.query(User).filter(
            User.stripe_customer_id == customer_id
        ).first()
        if user:
            # Write to RevenueLog for analytics
            existing = db.query(RevenueLog).filter(
                RevenueLog.stripe_invoice_id == invoice_id
            ).first()
            if not existing:
                period_start_ts = invoice.get("period_start")
                period_end_ts = invoice.get("period_end")
                log = RevenueLog(
                    user_id=user.id,
                    subscription_id=user.active_subscription_id,  # May be None if checkout hasn't completed yet
                    amount=amount_paid,
                    currency=invoice.get("currency", "usd"),
                    stripe_invoice_id=invoice_id,
                    status="paid",
                    period_start=(
                        datetime.fromtimestamp(period_start_ts, tz=timezone.utc)
                        if period_start_ts else None
                    ),
                    period_end=(
                        datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
                        if period_end_ts else None
                    ),
                )
                db.add(log)

            print(f"REVENUE LOG: User {user.email} paid ${amount_paid}")

    @staticmethod
    def _handle_payment_failed(invoice: Dict[str, Any], db: Session):
        """Handle failed subscription payments - downgrade access."""
        customer_id = invoice.get("customer")
        user = db.query(User).filter(
            User.stripe_customer_id == customer_id
        ).first()
        if user:
            user.is_pro = False
            sub = db.query(Subscription).filter(
                Subscription.id == user.active_subscription_id
            ).first()
            if sub:
                sub.status = "past_due"
            print(
                f"PAYMENT FAILED: User {user.email} "
                f"(Customer {customer_id}) downgraded."
            )

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
            local_sub = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_id
            ).first()
            if not local_sub:
                local_sub = Subscription(
                    stripe_subscription_id=stripe_id, user_id=user.id
                )
                db.add(local_sub)

            local_sub.plan_name = plan_name
            local_sub.status = subscription['status']
            local_sub.cancel_at_period_end = subscription['cancel_at_period_end']
            local_sub.current_period_end = datetime.fromtimestamp(
                subscription['current_period_end'], tz=timezone.utc
            )
            local_sub.mrr_value = (
                subscription['items']['data'][0]['price']['unit_amount'] / 100
            )

            # Sync trial_end if present
            trial_end_ts = subscription.get('trial_end')
            if trial_end_ts:
                local_sub.trial_end = datetime.fromtimestamp(
                    trial_end_ts, tz=timezone.utc
                )

            # Update user relation
            user.active_subscription_id = local_sub.id
            user.is_pro = local_sub.status in ['active', 'trialing']

        except Exception as e:
            print(f"Subscription Sync Error: {e}")
            db.rollback()
            raise  # Re-raise so outer webhook handler rolls back entire transaction