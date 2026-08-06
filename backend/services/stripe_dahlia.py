"""
Stripe API 2026-03-25.dahlia safe extraction helpers.

In the dahlia API version, several fields moved from top-level
objects into nested structures. These helpers extract values
safely regardless of API version.
"""

from typing import Dict, Any, Optional


def invoice_subscription_id(invoice: Dict[str, Any]) -> Optional[str]:
    """Extract subscription ID from an invoice in dahlia API format.

    dahlia: invoice.parent.subscription_details.subscription
    pre-dahlia: invoice.subscription
    """
    # Pre-dahlia: top-level
    sub = invoice.get("subscription")
    if sub:
        return sub

    # dahlia: parent.subscription_details.subscription
    parent = invoice.get("parent", {})
    if isinstance(parent, dict):
        details = parent.get("subscription_details", {})
        if isinstance(details, dict):
            return details.get("subscription")

    # dahlia fallback: first line item
    lines = invoice.get("lines", {})
    if isinstance(lines, dict):
        data = lines.get("data", [])
        if data and isinstance(data[0], dict):
            line_parent = data[0].get("parent", {})
            if isinstance(line_parent, dict):
                si_details = line_parent.get("subscription_item_details", {})
                if isinstance(si_details, dict):
                    return si_details.get("subscription")

    return None


def invoice_period_start(invoice: Dict[str, Any]) -> Optional[int]:
    """Extract period_start from an invoice in dahlia API format.

    dahlia: invoice.lines.data[0].period.start
    pre-dahlia: invoice.period_start
    """
    ts = invoice.get("period_start")
    if ts:
        return ts
    lines = invoice.get("lines", {})
    if isinstance(lines, dict):
        data = lines.get("data", [])
        if data and isinstance(data[0], dict):
            period = data[0].get("period", {})
            if isinstance(period, dict):
                return period.get("start")
    return None


def invoice_period_end(invoice: Dict[str, Any]) -> Optional[int]:
    """Extract period_end from an invoice in dahlia API format.

    dahlia: invoice.lines.data[0].period.end
    pre-dahlia: invoice.period_end
    """
    ts = invoice.get("period_end")
    if ts:
        return ts
    lines = invoice.get("lines", {})
    if isinstance(lines, dict):
        data = lines.get("data", [])
        if data and isinstance(data[0], dict):
            period = data[0].get("period", {})
            if isinstance(period, dict):
                return period.get("end")
    return None


def subscription_price_id(subscription: Dict[str, Any]) -> Optional[str]:
    """Extract price ID from a Stripe Subscription object.

    Works across API versions.
    """
    items = subscription.get("items", {})
    if isinstance(items, dict):
        data = items.get("data", [])
        if data and isinstance(data[0], dict):
            price = data[0].get("price", {})
            if isinstance(price, dict):
                return price.get("id")
    return None


def subscription_price_unit_amount(subscription: Dict[str, Any]) -> Optional[int]:
    """Extract unit_amount from a Stripe Subscription's price."""
    items = subscription.get("items", {})
    if isinstance(items, dict):
        data = items.get("data", [])
        if data and isinstance(data[0], dict):
            price = data[0].get("price", {})
            if isinstance(price, dict):
                return price.get("unit_amount")
    return None