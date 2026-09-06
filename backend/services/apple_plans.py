"""Authoritative Apple IAP product mapping.

Tier and lineup limits are derived only from the Apple product ID.
Do not infer entitlement from price, display name, or client claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


APPLE_BUNDLE_ID = "com.sportbookme.app"
APPLE_APP_APPLE_ID = 6808706342

# SignedDataVerifier instances (app-store-server-library==3.1.2):
#   Production → Environment.PRODUCTION + APPLE_APP_APPLE_ID
#   Sandbox    → Environment.SANDBOX
# Persist verified.environment as BillingEntitlement.is_test_mode
# (Sandbox=True, Production=False). NODE_ENV is not an eligibility input.
# Writer identity: (apple, originalTransactionId, is_test_mode).


@dataclass(frozen=True)
class AppleProduct:
    product_id: str
    tier: str
    billing_period: str
    max_lineups: int
    display_name: str


APPLE_PRODUCTS: dict[str, AppleProduct] = {
    "com.sportbookme.app.pro.monthly": AppleProduct(
        product_id="com.sportbookme.app.pro.monthly",
        tier="pro",
        billing_period="monthly",
        max_lineups=20,
        display_name="Pro Arena",
    ),
    "com.sportbookme.app.pro.annual": AppleProduct(
        product_id="com.sportbookme.app.pro.annual",
        tier="pro",
        billing_period="annual",
        max_lineups=20,
        display_name="Pro Arena Annual",
    ),
    "com.sportbookme.app.elite.monthly": AppleProduct(
        product_id="com.sportbookme.app.elite.monthly",
        tier="elite",
        billing_period="monthly",
        max_lineups=150,
        display_name="Elite Stack",
    ),
    "com.sportbookme.app.elite.annual": AppleProduct(
        product_id="com.sportbookme.app.elite.annual",
        tier="elite",
        billing_period="annual",
        max_lineups=150,
        display_name="Elite Stack Annual",
    ),
}


def get_apple_product(product_id: str) -> Optional[AppleProduct]:
    if not product_id or not isinstance(product_id, str):
        return None
    return APPLE_PRODUCTS.get(product_id.strip())


def recognized_apple_product_id(product_id: object) -> Optional[str]:
    if product_id is None:
        return None
    product = get_apple_product(str(product_id).strip())
    return product.product_id if product else None
