"""Recursive Stripe SDK object → plain dict conversion.

Stripe Webhook.construct_event() returns StripeObject instances
which lack .get(), .keys(), and other dict methods. All Stripe
SDK types store their data in a _data dict attribute. This module
extracts that recursively.
"""

from typing import Any


def stripe_to_dict(obj: Any) -> Any:
    """Recursively convert Stripe SDK objects to plain dicts.

    All Stripe SDK types (StripeObject, ListObject, Session,
    Parent, SubscriptionDetails, etc.) store their data in a
    `_data` dict attribute. We extract that recursively.
    """
    # Stripe SDK object: has _data dict
    if hasattr(obj, "_data") and isinstance(obj._data, dict):
        return {k: stripe_to_dict(v) for k, v in obj._data.items()}

    # ListObject: has _data list
    if hasattr(obj, "_data") and isinstance(obj._data, list):
        return [stripe_to_dict(item) for item in obj._data]

    # Plain list
    if isinstance(obj, list):
        return [stripe_to_dict(item) for item in obj]

    # Plain dict
    if isinstance(obj, dict):
        return {k: stripe_to_dict(v) for k, v in obj.items()}

    # Scalar
    return obj