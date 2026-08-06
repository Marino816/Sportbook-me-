"""Stripe StripeObject dict normalization regression tests."""

import stripe
import pytest
from unittest.mock import MagicMock, patch
from services.stripe_service import StripeService
from services.stripe_convert import stripe_to_dict


def _make_checkout_stripeobject():
    return stripe.convert_to_stripe_object({
        "id": "evt_test_cs",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_123",
            "object": "checkout.session",
            "metadata": {"user_id": "4", "plan_name": "Pro Arena"},
            "customer": "cus_TEST",
            "subscription": "sub_TEST",
            "customer_email": "qa@sportbookme.ai",
            "status": "complete",
        }}
    })


def _make_invoice_stripeobject():
    return stripe.convert_to_stripe_object({
        "id": "evt_test_inv",
        "type": "invoice.payment_succeeded",
        "data": {"object": {
            "id": "in_test_123",
            "object": "invoice",
            "customer": "cus_TEST",
            "amount_paid": 3999,
            "currency": "usd",
            "parent": {"subscription_details": {"subscription": "sub_TEST"}},
            "lines": {"data": [{"period": {"start": 1733097600, "end": 1735689600}}]},
        }}
    })


class TestStripeToDict:
    def test_top_level_is_dict(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert isinstance(d, dict)

    def test_data_object_is_dict(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert isinstance(d["data"]["object"], dict)

    def test_metadata_is_dict_with_get(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        meta = d["data"]["object"]["metadata"]
        assert hasattr(meta, "get")
        assert meta.get("user_id") == "4"

    def test_customer_extracted(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert d["data"]["object"].get("customer") == "cus_TEST"

    def test_invoice_lines_is_dict(self):
        d = stripe_to_dict(_make_invoice_stripeobject())
        lines = d["data"]["object"]["lines"]
        assert isinstance(lines, dict)
        assert hasattr(lines, "get")

    def test_invoice_parent_is_dict(self):
        d = stripe_to_dict(_make_invoice_stripeobject())
        parent = d["data"]["object"]["parent"]
        assert isinstance(parent, dict)
        assert parent["subscription_details"]["subscription"] == "sub_TEST"

    def test_invoice_period_accessible(self):
        d = stripe_to_dict(_make_invoice_stripeobject())
        period = d["data"]["object"]["lines"]["data"][0]["period"]
        assert period["start"] == 1733097600

    def test_deeply_nested_all_dicts(self):
        d = stripe_to_dict(_make_invoice_stripeobject())
        obj = d["data"]["object"]
        assert isinstance(obj["parent"]["subscription_details"], dict)
        assert isinstance(obj["lines"]["data"][0]["period"], dict)


class TestStripeObjectHasNoGet:
    def test_raw_stripeobject_lacks_get(self):
        obj = _make_checkout_stripeobject()
        assert not hasattr(obj.data.object, "get")
        assert not hasattr(obj.data.object.metadata, "get")

    def test_converted_dict_has_get(self):
        d = stripe_to_dict(_make_checkout_stripeobject())
        assert hasattr(d["data"]["object"], "get")
        assert d["data"]["object"].get("customer") == "cus_TEST"


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
        # side_effect: [StripeEvent→None, User→user, Subscription→None]
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
