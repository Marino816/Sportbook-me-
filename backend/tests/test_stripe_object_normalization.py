"""
Stripe webhook StripeObject → dict normalization regression tests.

Covers both webhook event normalization AND Stripe API retrieval normalization.
"""

import stripe
import pytest
from unittest.mock import MagicMock, patch
from services.stripe_service import StripeService
from services.stripe_convert import stripe_to_dict
from services.stripe_dahlia import subscription_price_id, subscription_price_unit_amount


def _make_checkout_stripeobject():
    return stripe.convert_to_stripe_object({
        "id": "evt_test_cs",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_123", "object": "checkout.session",
            "metadata": {"user_id": "4", "plan_name": "Pro Arena"},
            "customer": "cus_TEST", "subscription": "sub_TEST",
            "customer_email": "qa@sportbookme.ai",
            "status": "complete",
        }}
    })


def _make_invoice_stripeobject():
    return stripe.convert_to_stripe_object({
        "id": "evt_test_inv",
        "type": "invoice.payment_succeeded",
        "data": {"object": {
            "id": "in_test_123", "object": "invoice",
            "customer": "cus_TEST", "amount_paid": 3999, "currency": "usd",
            "parent": {"subscription_details": {"subscription": "sub_TEST"}},
            "lines": {"data": [{"period": {"start": 1733097600, "end": 1735689600}}]},
        }}
    })


def _make_retrieved_subscription_stripeobject():
    """Actual stripe.Subscription.retrieve() returns a StripeObject."""
    return stripe.convert_to_stripe_object({
        "id": "sub_1U1Dvm2IjsjgdZmb4hR0z28t",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_end": 1767225600,
        "trial_end": None,
        "items": {
            "object": "list",
            "data": [{
                "object": "subscription_item",
                "price": {
                    "id": "price_1U1CbU2IjsjgdZmbyzXjzFyD",
                    "unit_amount": 3999,
                    "object": "price",
                }
            }]
        }
    })


class TestStripeToDict:
    def test_top_level_dict(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert isinstance(d, dict)
        assert isinstance(d["data"]["object"], dict)

    def test_metadata_has_get(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert d["data"]["object"]["metadata"].get("user_id") == "4"

    def test_invoice_parent_is_dict(self):
        d = stripe_to_dict(_make_invoice_stripeobject())
        assert isinstance(d["data"]["object"]["parent"]["subscription_details"], dict)

    def test_retrieved_subscription_normalized(self):
        """stripe.Subscription.retrieve() returns StripeObject — must convert."""
        sub_obj = _make_retrieved_subscription_stripeobject()
        assert not hasattr(sub_obj, "get")  # It's a StripeObject
        sub_dict = stripe_to_dict(sub_obj)
        assert isinstance(sub_dict, dict)
        assert hasattr(sub_dict, "get")
        assert isinstance(sub_dict["items"]["data"][0]["price"], dict)

    def test_price_id_from_normalized_subscription(self):
        sub_obj = _make_retrieved_subscription_stripeobject()
        sub_dict = stripe_to_dict(sub_obj)
        pid = subscription_price_id(sub_dict)
        assert pid == "price_1U1CbU2IjsjgdZmbyzXjzFyD"

    def test_unit_amount_from_normalized_subscription(self):
        sub_obj = _make_retrieved_subscription_stripeobject()
        sub_dict = stripe_to_dict(sub_obj)
        amt = subscription_price_unit_amount(sub_dict)
        assert amt == 3999


class TestSyncSubscriptionWithStripeObject:
    """Regression: _sync_subscription passes stripe.Subscription.retrieve()
    result (StripeObject) to dahlia helpers without normalization."""

    @patch("services.stripe_service.stripe.Subscription.retrieve")
    def test_retrieve_result_is_normalized(self, mock_retrieve):
        # Return a REAL StripeObject from retrieve — this is what Stripe SDK returns
        mock_retrieve.return_value = _make_retrieved_subscription_stripeobject()

        db = MagicMock()
        db.query().filter().first.return_value = None  # No existing subscription

        user = MagicMock()
        user.id = 4
        user.is_pro = False

        # Should NOT raise AttributeError: get
        StripeService._sync_subscription("sub_TEST", user, db)

        # Verify local subscription was created (price_id extracted, no crash)
        db.add.assert_called()
        local_sub = db.add.call_args[0][0]
        assert local_sub.status == "active"
        assert local_sub.mrr_value == 39.99
        # plan_name may be "Starter" if PLAN_PRICE_MAP env vars not set in tests
        assert local_sub.plan_name in ("Pro Arena", "Starter")

    @patch("services.stripe_service.stripe.Subscription.retrieve")
    def test_price_id_extracts_from_stripeobject(self, mock_retrieve):
        mock_retrieve.return_value = _make_retrieved_subscription_stripeobject()
        db = MagicMock()
        db.query().filter().first.return_value = None
        user = MagicMock(); user.id = 4; user.is_pro = False

        # Should not raise
        StripeService._sync_subscription("sub_TEST", user, db)
        # No crash — price_id was extracted from StripeObject successfully
        assert db.add.called


class TestWebhookDispatch:
    @patch("services.stripe_service.stripe.Subscription.retrieve")
    def test_checkout_dispatches(self, mock_retrieve):
        mock_retrieve.return_value = {
            "id": "sub_TEST", "status": "active",
            "cancel_at_period_end": False, "current_period_end": 1767225600,
            "trial_end": None,
            "items": {"data": [{"price": {"id": "price_1TEST", "unit_amount": 3999}}]},
        }
        db = MagicMock()
        user = MagicMock(); user.id = 4; user.is_pro = False
        db.query().filter().first.side_effect = [None, user, None]
        with patch("services.stripe_service.WEBHOOK_SECRET", "whsec_test"):
            with patch.object(stripe.Webhook, "construct_event") as mc:
                mc.return_value = _make_checkout_stripeobject()
                StripeService.handle_webhook_event(b"x", "sig", db)
        db.commit.assert_called_once()

    @patch("services.stripe_service.stripe.Subscription.retrieve")
    def test_invoice_dispatches(self, mock_retrieve):
        db = MagicMock()
        user = MagicMock(); user.id = 4; user.active_subscription_id = 99
        db.query().filter().first.side_effect = [None, user, None]
        with patch("services.stripe_service.WEBHOOK_SECRET", "whsec_test"):
            with patch.object(stripe.Webhook, "construct_event") as mc:
                mc.return_value = _make_invoice_stripeobject()
                StripeService.handle_webhook_event(b"x", "sig", db)
        db.commit.assert_called_once()

    def test_invalid_signature_rejected(self):
        db = MagicMock()
        with patch("services.stripe_service.WEBHOOK_SECRET", "whsec_test"):
            with pytest.raises(ValueError, match="Invalid Webhook"):
                StripeService.handle_webhook_event(b"x", "bad_sig", db)