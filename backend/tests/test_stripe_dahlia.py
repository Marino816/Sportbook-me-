"""
Stripe API 2026-03-25.dahlia regression tests.

Tests exact payload structures from the failing webhook events.
"""

import pytest
from services.stripe_dahlia import (
    invoice_subscription_id,
    invoice_period_start,
    invoice_period_end,
    subscription_price_id,
    subscription_price_unit_amount,
    subscription_current_period_end,
)


# Exact dahlia invoice payload (from evt_1U1Dvo2IjsjgdZmbGHPbMAkx)
DAHLIA_INVOICE = {
    "id": "in_1U1Dvo2IjsjgdZmQ8nNQRkMa",
    "object": "invoice",
    "customer": "cus_V1GSHRscoS5cmE",
    "amount_paid": 3999,
    "currency": "usd",
    "status": "paid",
    # NOTE: no top-level "subscription" field in dahlia
    # NOTE: no top-level "period_start" / "period_end" in dahlia
    "parent": {
        "subscription_details": {
            "subscription": "sub_1U1Dvm2IjsjgdZmb4hR0z28t",
        }
    },
    "lines": {
        "data": [
            {
                "period": {
                    "start": 1733097600,
                    "end": 1735689600,
                },
                "parent": {
                    "subscription_item_details": {
                        "subscription": "sub_1U1Dvm2IjsjgdZmb4hR0z28t",
                    }
                },
                "pricing": {
                    "price_details": {
                        "price": "price_1U1Due2IjsjgdZm3qVMJh8Gh",
                    }
                },
            }
        ]
    },
}

# Pre-dahlia invoice payload (for backward compatibility)
PRE_DAHLIA_INVOICE = {
    "id": "in_old123",
    "customer": "cus_old",
    "amount_paid": 3999,
    "subscription": "sub_old123",
    "period_start": 1733097600,
    "period_end": 1735689600,
}

# dahlia subscription payload
DAHLIA_SUBSCRIPTION = {
    "id": "sub_1U1Dvm2IjsjgdZmb4hR0z28t",
    "status": "active",
    "cancel_at_period_end": False,
    "current_period_end": 1767225600,
    "trial_end": None,
    "items": {
        "data": [
            {
                "price": {
                    "id": "price_ProTest",
                    "unit_amount": 3999,
                }
            }
        ]
    },
}


class TestDahliaInvoiceExtraction:
    def test_subscription_from_parent(self):
        sub = invoice_subscription_id(DAHLIA_INVOICE)
        assert sub == "sub_1U1Dvm2IjsjgdZmb4hR0z28t"

    def test_period_start_from_lines(self):
        ts = invoice_period_start(DAHLIA_INVOICE)
        assert ts == 1733097600

    def test_period_end_from_lines(self):
        ts = invoice_period_end(DAHLIA_INVOICE)
        assert ts == 1735689600


class TestPreDahliaInvoiceExtraction:
    def test_subscription_from_top_level(self):
        sub = invoice_subscription_id(PRE_DAHLIA_INVOICE)
        assert sub == "sub_old123"

    def test_period_start_top_level(self):
        ts = invoice_period_start(PRE_DAHLIA_INVOICE)
        assert ts == 1733097600

    def test_period_end_top_level(self):
        ts = invoice_period_end(PRE_DAHLIA_INVOICE)
        assert ts == 1735689600


class TestDahliaSubscriptionExtraction:
    def test_price_id(self):
        pid = subscription_price_id(DAHLIA_SUBSCRIPTION)
        assert pid == "price_ProTest"

    def test_unit_amount(self):
        amt = subscription_price_unit_amount(DAHLIA_SUBSCRIPTION)
        assert amt == 3999

    def test_current_period_end_top_level(self):
        ts = subscription_current_period_end(DAHLIA_SUBSCRIPTION)
        assert ts == 1767225600

    def test_current_period_end_nested_dahlia(self):
        """dahlia: period is at items.data[0].current_period_end"""
        sub = {
            "items": {"data": [{"current_period_end": 1788649740}]}
        }
        assert subscription_current_period_end(sub) == 1788649740

    def test_current_period_end_prefers_top_level(self):
        sub = {
            "current_period_end": 1767225600,
            "items": {"data": [{"current_period_end": 9999999999}]},
        }
        assert subscription_current_period_end(sub) == 1767225600

    def test_current_period_end_missing(self):
        assert subscription_current_period_end({}) is None


class TestEdgeCases:
    def test_empty_invoice_returns_none(self):
        assert invoice_subscription_id({}) is None
        assert invoice_period_start({}) is None
        assert invoice_period_end({}) is None

    def test_missing_items_returns_none(self):
        sub = {"id": "sub", "status": "active"}
        assert subscription_price_id(sub) is None
        assert subscription_price_unit_amount(sub) is None

    def test_half_constructed_dahlia(self):
        """Only has parent.subscription_details — no lines."""
        inv = {
            "parent": {
                "subscription_details": {"subscription": "sub_test"},
            }
        }
        assert invoice_subscription_id(inv) == "sub_test"
        assert invoice_period_start(inv) is None  # No lines.data
        assert invoice_period_end(inv) is None

    def test_lines_period_preferred_over_top_level(self):
        """Top-level period is invoice timestamp (start==end). Line-item is billing period."""
        inv = {
            "period_start": 1785971340,
            "period_end": 1785971340,  # Same as start — invoice timestamp, not billing
            "lines": {
                "data": [{
                    "period": {"start": 1785971340, "end": 1788649740},  # Billing period (~31 days)
                }]
            }
        }
        assert invoice_period_start(inv) == 1785971340
        assert invoice_period_end(inv) == 1788649740  # Should be line-item end, not top-level