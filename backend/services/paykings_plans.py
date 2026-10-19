"""Authoritative Sportbook Me <-> PayKings plan mapping.

Tier and price are derived only from the PayKings plan ID.
Do not infer tier from amount or plan name.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class PayKingsPlan:
    plan_id: str
    tier: str
    billing_period: str
    expected_price: Decimal
    display_name: str


SBME_PLANS: dict[str, PayKingsPlan] = {
    "SBME_PRO_MONTHLY": PayKingsPlan(
        plan_id="SBME_PRO_MONTHLY",
        tier="pro",
        billing_period="monthly",
        expected_price=Decimal("49.99"),
        display_name="Pro Arena",
    ),
    "SBME_PRO_ANNUAL": PayKingsPlan(
        plan_id="SBME_PRO_ANNUAL",
        tier="pro",
        billing_period="annual",
        expected_price=Decimal("399.99"),
        display_name="Pro Arena Annual",
    ),
    "SBME_ELITE_MONTHLY": PayKingsPlan(
        plan_id="SBME_ELITE_MONTHLY",
        tier="elite",
        billing_period="monthly",
        expected_price=Decimal("89.99"),
        display_name="Elite Stack",
    ),
    "SBME_ELITE_ANNUAL": PayKingsPlan(
        plan_id="SBME_ELITE_ANNUAL",
        tier="elite",
        billing_period="annual",
        expected_price=Decimal("599.99"),
        display_name="Elite Stack Annual",
    ),
}

SBME_PLAN_IDS = {plan_id: plan.display_name for plan_id, plan in SBME_PLANS.items()}
PLANS_BY_DISPLAY_NAME = {plan.display_name: plan for plan in SBME_PLANS.values()}


def get_plan(plan_id: str) -> Optional[PayKingsPlan]:
    if not plan_id or not isinstance(plan_id, str):
        return None
    return SBME_PLANS.get(plan_id.strip())


def plan_from_display_name(name: str) -> Optional[PayKingsPlan]:
    if not name or not isinstance(name, str):
        return None
    return PLANS_BY_DISPLAY_NAME.get(name.strip())
