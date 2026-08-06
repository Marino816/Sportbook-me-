"""
Stripe webhook regression tests for checkout.session.completed and invoice.payment_succeeded.

Run isolated: python -m pytest tests/test_stripe_webhooks.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone

from services.stripe_service import StripeService, PLAN_PRICE_MAP
from models.domain import User, Subscription, StripeEvent, RevenueLog


def _make_user(user_id=1, email="test@example.com", stripe_customer_id=None):
    u = User(id=user_id, email=email, role="user", is_active=True, is_pro=False)
    u.stripe_customer_id = stripe_customer_id
    u.active_subscription_id = None
    return u


def _make_db():
    """Create a mock sync DB session with query chaining."""
    db = MagicMock()

    def _filter_first(return_value):
        """Simulate db.query(...).filter(...).first()"""
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = return_value
        return q

    db.query.return_value = _filter_first(None)
    return db


class TestCheckoutCompleted:
    """Regression: checkout.session.completed was returning 500 due to double db.commit()."""

    def test_sets_customer_id_and_syncs_subscription(self):
        """User found via metadata.user_id — should set stripe_customer_id and sync."""
        with patch("services.stripe_service.stripe.Subscription.retrieve") as mock_retrieve:
            mock_retrieve.return_value = {
                "id": "sub_test123",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1735689600,
                "trial_end": None,
                "items": {
                    "data": [{"price": {"id": list(PLAN_PRICE_MAP.values())[0], "unit_amount": 3999}}]
                },
            }

            db = _make_db()
            user = _make_user(user_id=42)
            db.query().filter().first.return_value = user  # User lookup

            session = {
                "metadata": {"user_id": "42", "plan_name": "Pro Arena"},
                "customer": "cus_test123",
                "subscription": "sub_test123",
                "customer_email": "test@test.com",
            }

            # Should not raise
            StripeService._handle_checkout_completed(session, db)

            assert user.stripe_customer_id == "cus_test123"
            assert user.is_pro is True
            assert user.active_subscription_id is not None

    def test_no_double_commit(self):
        """Handler should NOT call db.commit() — that's done by the outer webhook handler."""
        with patch("services.stripe_service.stripe.Subscription.retrieve") as mock_retrieve:
            mock_retrieve.return_value = {
                "id": "sub_test",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1735689600,
                "trial_end": None,
                "items": {
                    "data": [{"price": {"id": list(PLAN_PRICE_MAP.values())[0], "unit_amount": 3999}}]
                },
            }

            db = _make_db()
            user = _make_user(user_id=42)
            db.query().filter().first.return_value = user

            session = {
                "metadata": {"user_id": "42"},
                "customer": "cus_test",
                "subscription": "sub_test",
                "customer_email": "test@test.com",
            }

            StripeService._handle_checkout_completed(session, db)

            # db.commit() must NOT be called — outer handler does it
            db.commit.assert_not_called()


class TestPaymentSucceeded:
    """Regression: invoice.payment_succeeded was returning 500 due to NOT NULL column failures."""

    def test_creates_revenue_log(self):
        """Normal case: user found, active_subscription_id set, all fields present."""
        db = _make_db()
        user = _make_user(user_id=42, stripe_customer_id="cus_test")
        user.active_subscription_id = 99

        # Mock user lookup
        db.query().filter().first.return_value = user

        # Mock RevenueLog dedup lookup (no existing)
        db.query().filter().first.side_effect = [user, None]

        invoice = {
            "customer": "cus_test",
            "amount_paid": 3999,
            "id": "inv_test123",
            "subscription": "sub_test123",
            "currency": "usd",
            "period_start": 1733097600,
            "period_end": 1735689600,
        }

        StripeService._handle_payment_succeeded(invoice, db)

        db.add.assert_called_once()
        added_log = db.add.call_args[0][0]
        assert isinstance(added_log, RevenueLog)
        assert added_log.amount == 39.99
        assert added_log.stripe_invoice_id == "inv_test123"
        assert added_log.status == "paid"

    def test_handles_missing_subscription_id(self):
        """RevenueLog should insert even when user.active_subscription_id is None."""
        db = _make_db()
        user = _make_user(user_id=42, stripe_customer_id="cus_test")
        user.active_subscription_id = None  # Checkout hasn't completed yet

        db.query().filter().first.side_effect = [user, None]

        invoice = {
            "customer": "cus_test",
            "amount_paid": 3999,
            "id": "inv_test456",
            "subscription": "sub_test456",
            "currency": "usd",
            "period_start": None,
            "period_end": None,
        }

        StripeService._handle_payment_succeeded(invoice, db)

        db.add.assert_called_once()
        added_log = db.add.call_args[0][0]
        assert added_log.subscription_id is None
        assert added_log.period_start is None
        assert added_log.period_end is None

    def test_no_double_commit(self):
        """Handler should NOT call db.commit()."""
        db = _make_db()
        user = _make_user(user_id=42, stripe_customer_id="cus_test")
        user.active_subscription_id = 99
        db.query().filter().first.side_effect = [user, None]

        invoice = {
            "customer": "cus_test",
            "amount_paid": 3999,
            "id": "inv_test",
            "subscription": "sub_test",
            "period_start": 1733097600,
            "period_end": 1735689600,
        }

        StripeService._handle_payment_succeeded(invoice, db)
        db.commit.assert_not_called()

    def test_ignores_duplicate_invoice(self):
        """Should skip if RevenueLog for this stripe_invoice_id already exists."""
        db = _make_db()
        user = _make_user(user_id=42, stripe_customer_id="cus_test")
        user.active_subscription_id = 99

        existing_log = RevenueLog(stripe_invoice_id="inv_test789")
        db.query().filter().first.side_effect = [user, existing_log]

        invoice = {
            "customer": "cus_test",
            "amount_paid": 3999,
            "id": "inv_test789",
            "subscription": "sub_test",
            "period_start": 1733097600,
            "period_end": 1735689600,
        }

        StripeService._handle_payment_succeeded(invoice, db)
        db.add.assert_not_called()  # No duplicate insert


class TestSubscriptionUpdated:
    """Regression: _handle_subscription_updated was also double-committing."""

    def test_no_double_commit(self):
        with patch("services.stripe_service.stripe.Subscription.retrieve") as mock_retrieve:
            mock_retrieve.return_value = {
                "id": "sub_test",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1735689600,
                "trial_end": None,
                "items": {
                    "data": [{"price": {"id": list(PLAN_PRICE_MAP.values())[0], "unit_amount": 3999}}]
                },
            }

            db = _make_db()
            user = _make_user(stripe_customer_id="cus_test")
            db.query().filter().first.return_value = user

            stripe_sub = {"id": "sub_test", "customer": "cus_test", "status": "active"}

            StripeService._handle_subscription_updated(stripe_sub, db)
            db.commit.assert_not_called()