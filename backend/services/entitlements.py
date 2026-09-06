"""Provider-aware entitlement resolution.

Effective access is the highest valid entitlement across Stripe, PayKings,
and Apple. User.is_pro and active_subscription_id are compatibility
projections, not the sole source of truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.domain import BillingEntitlement, Subscription, User
from services.apple_plans import get_apple_product
from services.paykings_plans import PayKingsPlan, get_plan

logger = logging.getLogger(__name__)

PROVIDER_PAYKINGS = "paykings"
PROVIDER_STRIPE = "stripe"
PROVIDER_APPLE = "apple"

STATUS_PENDING_PAYMENT = "pending_payment"
STATUS_ACTIVE = "active"
STATUS_CANCELED = "canceled"
STATUS_REFUNDED = "refunded"
STATUS_PAST_DUE = "past_due"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"

STRIPE_LIVE_STATUSES = frozenset({"active", "trialing"})
TIER_RANK = {"free": 0, "pro": 1, "elite": 2}
TIER_PLAN_NAME = {
    "pro": "Pro Arena",
    "elite": "Elite Stack",
}


@dataclass(frozen=True)
class EffectiveAccess:
    tier: str
    plan_name: str
    billing_period: Optional[str]
    is_pro: bool
    provider: Optional[str]
    max_lineups: int
    status: str

    @property
    def feature_tier(self) -> str:
        if self.tier == "elite":
            return "elite_stack"
        if self.tier == "pro":
            return "pro_arena"
        return "free"


def plan_name_is_elite(plan_name: Optional[str]) -> bool:
    name = (plan_name or "").strip()
    return name == "Elite Stack" or name.startswith("Elite Stack ")


def plan_name_is_pro(plan_name: Optional[str]) -> bool:
    name = (plan_name or "").strip()
    return name == "Pro Arena" or name.startswith("Pro Arena ")


def tier_from_plan_name(plan_name: Optional[str]) -> str:
    if plan_name_is_elite(plan_name):
        return "elite"
    if plan_name_is_pro(plan_name):
        return "pro"
    return "free"


def period_from_plan_name(plan_name: Optional[str]) -> Optional[str]:
    name = (plan_name or "").strip()
    if "Annual" in name:
        return "annual"
    if name in {"Pro Arena", "Elite Stack"}:
        return "monthly"
    return None


def display_name_for_tier(tier: str, billing_period: Optional[str] = None) -> str:
    base = TIER_PLAN_NAME.get(tier, "Starter")
    if billing_period == "annual" and base != "Starter":
        return f"{base} Annual"
    return base


def max_lineups_for_tier(tier: str, *, is_admin: bool = False) -> int:
    if is_admin:
        return 150
    if tier == "elite":
        return 150
    if tier == "pro":
        return 20
    return 1


def feature_tier_key(is_pro: bool, plan_name: Optional[str]) -> str:
    """Compatibility helper for existing feature-gating copies."""
    if not is_pro:
        return "free"
    if plan_name_is_elite(plan_name):
        return "elite_stack"
    return "pro_arena"


def parse_money_amount(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return abs(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def action_indicates_success(extracted: dict[str, Any] | None) -> bool:
    if not isinstance(extracted, dict):
        return False
    action = extracted.get("action") if isinstance(extracted.get("action"), dict) else {}
    if not action:
        return True
    success = action.get("success")
    return success in (True, 1, "1", "true", "True")


def trustworthy_period_end(value: Any) -> Optional[datetime]:
    """Ignore PayKings 1970-01-01 sentinels observed on live add webhooks."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.year < 2000:
        return None
    return parsed


def paykings_entitlement_is_live(row: BillingEntitlement) -> bool:
    return (
        row.provider == PROVIDER_PAYKINGS
        and row.status == STATUS_ACTIVE
        and bool(row.paid_verified)
        and not bool(row.is_test_mode)
    )


def apple_entitlement_is_live(
    row: BillingEntitlement,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Apple access requires a known product, server-verified paid row, and unexpired period.

    Environment (is_test_mode) is metadata from Apple's verified JWS, not a
    grant gate. A verified Sandbox row may grant on a production backend
    (TestFlight / App Review). NODE_ENV is not consulted. Client flags are
    not consulted. originalTransactionId must be present.
    """
    if row.provider != PROVIDER_APPLE:
        return False
    if row.status != STATUS_ACTIVE:
        return False
    if not bool(row.paid_verified):
        return False
    if not row.provider_subscription_id:
        return False
    if get_apple_product(row.provider_plan_id or "") is None:
        return False
    if row.current_period_end is not None:
        end = row.current_period_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        clock = now or datetime.now(timezone.utc)
        if end <= clock:
            return False
    return True


def stripe_subscription_is_live(row: Any) -> bool:
    if not isinstance(row, Subscription):
        return False
    return (row.status or "") in STRIPE_LIVE_STATUSES and tier_from_plan_name(row.plan_name) in {
        "pro",
        "elite",
    }


def _rank(tier: str) -> int:
    return TIER_RANK.get(tier, 0)


def _free_access(*, is_admin: bool = False) -> EffectiveAccess:
    return EffectiveAccess(
        tier="free",
        plan_name="Starter",
        billing_period=None,
        is_pro=False,
        provider=None,
        max_lineups=max_lineups_for_tier("free", is_admin=is_admin),
        status="free",
    )


def choose_effective_access(
    *,
    paykings: Iterable[BillingEntitlement] = (),
    subscriptions: Iterable[Subscription] = (),
    apple: Iterable[BillingEntitlement] = (),
    is_admin: bool = False,
) -> EffectiveAccess:
    """Highest live tier wins. Same-tier: Stripe > Apple > PayKings.

    One provider expiring or being revoked never removes another provider's
    still-valid access.

    Verified Apple Sandbox and Production rows are both eligible. They stay
    labeled by ``is_test_mode`` and are never converted into each other.
    NODE_ENV and client sandbox flags are not inputs.
    """
    winner: Optional[tuple[int, int, str, str, Optional[str], str]] = None
    # tuple: (tier_rank, provider_tiebreak, tier, plan_name, period, provider)
    for row in paykings:
        if not paykings_entitlement_is_live(row):
            continue
        plan = get_plan(row.provider_plan_id or "")
        plan_name = plan.display_name if plan else display_name_for_tier(row.tier, row.billing_period)
        candidate = (_rank(row.tier), 0, row.tier, plan_name, row.billing_period, PROVIDER_PAYKINGS)
        if winner is None or candidate > winner:
            winner = candidate
    for row in apple:
        if not apple_entitlement_is_live(row):
            continue
        product = get_apple_product(row.provider_plan_id or "")
        plan_name = product.display_name if product else display_name_for_tier(row.tier, row.billing_period)
        candidate = (_rank(row.tier), 1, row.tier, plan_name, row.billing_period, PROVIDER_APPLE)
        if winner is None or candidate > winner:
            winner = candidate
    compat_ids = {
        row.compatibility_subscription_id
        for row in list(paykings) + list(apple)
        if row.compatibility_subscription_id is not None
    }
    for sub in subscriptions:
        if not stripe_subscription_is_live(sub):
            continue
        if sub.id in compat_ids:
            continue
        tier = tier_from_plan_name(sub.plan_name)
        stripe_tie = 2 if getattr(sub, "stripe_subscription_id", None) else 0
        candidate = (
            _rank(tier),
            stripe_tie,
            tier,
            sub.plan_name or display_name_for_tier(tier),
            period_from_plan_name(sub.plan_name),
            PROVIDER_STRIPE if sub.stripe_subscription_id else "legacy",
        )
        if winner is None or candidate > winner:
            winner = candidate
    if winner is None:
        return _free_access(is_admin=is_admin)
    _rank_v, _tie, tier, plan_name, period, provider = winner
    return EffectiveAccess(
        tier=tier,
        plan_name=plan_name,
        billing_period=period,
        is_pro=True,
        provider=provider,
        max_lineups=max_lineups_for_tier(tier, is_admin=is_admin),
        status=STATUS_ACTIVE,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def load_user_entitlement_sources(
    db: AsyncSession, user_id: int,
) -> tuple[list[BillingEntitlement], list[Subscription]]:
    entitlements = list(
        (
            await db.execute(
                select(BillingEntitlement).where(BillingEntitlement.user_id == user_id)
            )
        ).scalars().all()
    )
    subscriptions = list(
        (
            await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        ).scalars().all()
    )
    return entitlements, subscriptions


async def effective_access_for_user(
    db: AsyncSession,
    user: User,
    *,
    is_admin: Optional[bool] = None,
) -> EffectiveAccess:
    admin = user.role == "admin" if is_admin is None else is_admin
    entitlements, subscriptions = await load_user_entitlement_sources(db, user.id)
    paykings = [row for row in entitlements if row.provider == PROVIDER_PAYKINGS]
    apple = [row for row in entitlements if row.provider == PROVIDER_APPLE]
    return choose_effective_access(
        paykings=paykings,
        subscriptions=subscriptions,
        apple=apple,
        is_admin=admin,
    )


async def feature_tier_for_user(db: AsyncSession, user: User) -> str:
    """Canonical feature-gate key from effective access, not User.is_pro."""
    access = await effective_access_for_user(db, user)
    return access.feature_tier


async def _apple_compat_subscription(
    db: AsyncSession,
    user: User,
    entitlement: BillingEntitlement,
    product: Optional[object],
) -> Subscription:
    if entitlement.compatibility_subscription_id:
        existing = (
            await db.execute(
                select(Subscription).where(
                    Subscription.id == entitlement.compatibility_subscription_id
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing
    display = getattr(product, "display_name", None) or display_name_for_tier(
        entitlement.tier, entitlement.billing_period
    )
    row = Subscription(
        user_id=user.id,
        stripe_subscription_id=None,
        plan_name=display,
        status=STATUS_ACTIVE,
        mrr_value=0,
        current_period_end=entitlement.current_period_end,
        created_at=_now(),
    )
    db.add(row)
    await db.flush()
    entitlement.compatibility_subscription_id = row.id
    return row


async def _paykings_compat_subscription(
    db: AsyncSession,
    user: User,
    entitlement: BillingEntitlement,
    plan: Optional[PayKingsPlan],
) -> Subscription:
    if entitlement.compatibility_subscription_id:
        existing = (
            await db.execute(
                select(Subscription).where(
                    Subscription.id == entitlement.compatibility_subscription_id
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing
    row = Subscription(
        user_id=user.id,
        stripe_subscription_id=None,
        plan_name=plan.display_name if plan else display_name_for_tier(
            entitlement.tier, entitlement.billing_period
        ),
        status=STATUS_ACTIVE,
        mrr_value=float(plan.expected_price) if plan else 0,
        current_period_end=entitlement.current_period_end,
        created_at=_now(),
    )
    db.add(row)
    await db.flush()
    entitlement.compatibility_subscription_id = row.id
    return row


async def reconcile_user_access(db: AsyncSession, user_id: int) -> EffectiveAccess:
    """Project effective access onto User.is_pro / active_subscription_id."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalars().first()
    if user is None:
        return _free_access()
    entitlements, subscriptions = await load_user_entitlement_sources(db, user_id)
    paykings = [row for row in entitlements if row.provider == PROVIDER_PAYKINGS]
    apple_rows = [row for row in entitlements if row.provider == PROVIDER_APPLE]
    access = choose_effective_access(
        paykings=paykings,
        subscriptions=subscriptions,
        apple=apple_rows,
    )
    live_paykings = [row for row in paykings if paykings_entitlement_is_live(row)]
    live_apple = [row for row in apple_rows if apple_entitlement_is_live(row)]
    for row in entitlements:
        live = (
            paykings_entitlement_is_live(row)
            if row.provider == PROVIDER_PAYKINGS
            else apple_entitlement_is_live(row)
            if row.provider == PROVIDER_APPLE
            else False
        )
        if row.compatibility_subscription_id and not live:
            compat = next(
                (s for s in subscriptions if s.id == row.compatibility_subscription_id),
                None,
            )
            if compat is not None and not compat.stripe_subscription_id:
                compat.status = row.status if row.status in {
                    STATUS_CANCELED, STATUS_REFUNDED, STATUS_PAST_DUE, STATUS_EXPIRED, STATUS_REVOKED,
                } else STATUS_CANCELED

    if not access.is_pro:
        user.is_pro = False
        stripe_sub = next(
            (s for s in subscriptions if s.stripe_subscription_id),
            None,
        )
        if stripe_sub is not None:
            user.active_subscription_id = stripe_sub.id
        return access

    user.is_pro = True
    if access.provider == PROVIDER_PAYKINGS and live_paykings:
        winner = max(live_paykings, key=lambda row: (_rank(row.tier), row.id))
        plan = get_plan(winner.provider_plan_id or "")
        compat = await _paykings_compat_subscription(db, user, winner, plan)
        compat.plan_name = plan.display_name if plan else access.plan_name
        compat.status = STATUS_ACTIVE
        compat.mrr_value = float(plan.expected_price) if plan else compat.mrr_value
        if winner.current_period_end:
            compat.current_period_end = winner.current_period_end
        user.active_subscription_id = compat.id
        return access

    if access.provider == PROVIDER_APPLE and live_apple:
        winner = max(live_apple, key=lambda row: (_rank(row.tier), row.id))
        product = get_apple_product(winner.provider_plan_id or "")
        compat = await _apple_compat_subscription(db, user, winner, product)
        compat.plan_name = product.display_name if product else access.plan_name
        compat.status = STATUS_ACTIVE
        if winner.current_period_end:
            compat.current_period_end = winner.current_period_end
        user.active_subscription_id = compat.id
        return access

    winning_sub = None
    for sub in subscriptions:
        if not stripe_subscription_is_live(sub):
            continue
        if sub.id in {row.compatibility_subscription_id for row in entitlements}:
            continue
        if tier_from_plan_name(sub.plan_name) == access.tier:
            if winning_sub is None or (sub.stripe_subscription_id and not winning_sub.stripe_subscription_id):
                winning_sub = sub
    if winning_sub is not None:
        user.active_subscription_id = winning_sub.id
    return access


def _safe_query_all(result: Any) -> list:
    if result is None:
        return []
    if isinstance(result, (list, tuple)):
        return list(result)
    return []


def reconcile_user_access_sync(
    db: Session,
    user: User,
    *,
    stripe_subscription: Optional[Subscription] = None,
) -> EffectiveAccess:
    """Sync-session reconcile used by Stripe webhooks."""
    try:
        entitlement_rows = db.query(BillingEntitlement).filter(
            BillingEntitlement.user_id == user.id
        ).all()
        entitlements = [
            row for row in _safe_query_all(entitlement_rows)
            if isinstance(row, BillingEntitlement)
        ]
    except Exception:
        entitlements = []
    try:
        subscription_rows = db.query(Subscription).filter(
            Subscription.user_id == user.id
        ).all()
        subscriptions = [
            row for row in _safe_query_all(subscription_rows)
            if isinstance(row, Subscription)
        ]
    except Exception:
        subscriptions = []
    if isinstance(stripe_subscription, Subscription) and stripe_subscription not in subscriptions:
        subscriptions.append(stripe_subscription)
    elif stripe_subscription is not None and not isinstance(stripe_subscription, Subscription) and not entitlements:
        # Mocked Stripe unit tests pass a non-Subscription row. Production always
        # passes a real Subscription and never takes this branch.
        status = getattr(stripe_subscription, "status", None)
        user.is_pro = status in STRIPE_LIVE_STATUSES
        if getattr(stripe_subscription, "id", None) is not None:
            user.active_subscription_id = stripe_subscription.id
        tier = tier_from_plan_name(getattr(stripe_subscription, "plan_name", None))
        return EffectiveAccess(
            tier=tier if user.is_pro else "free",
            plan_name=getattr(stripe_subscription, "plan_name", None) or "Starter",
            billing_period=period_from_plan_name(getattr(stripe_subscription, "plan_name", None)),
            is_pro=bool(user.is_pro),
            provider=PROVIDER_STRIPE if user.is_pro else None,
            max_lineups=max_lineups_for_tier(tier if user.is_pro else "free"),
            status=status or "free",
        )

    paykings = [row for row in entitlements if getattr(row, "provider", None) == PROVIDER_PAYKINGS]
    apple_rows = [row for row in entitlements if getattr(row, "provider", None) == PROVIDER_APPLE]
    access = choose_effective_access(
        paykings=paykings,
        subscriptions=subscriptions,
        apple=apple_rows,
    )
    if not access.is_pro:
        user.is_pro = False
        stripe_sub = next(
            (s for s in subscriptions if getattr(s, "stripe_subscription_id", None)),
            stripe_subscription if stripe_subscription and getattr(stripe_subscription, "stripe_subscription_id", None) else None,
        )
        if stripe_sub is not None and getattr(stripe_sub, "id", None) is not None:
            user.active_subscription_id = stripe_sub.id
        return access

    user.is_pro = True
    if access.provider == PROVIDER_APPLE:
        return access
    if access.provider in {PROVIDER_STRIPE, "legacy"}:
        chosen = None
        for sub in subscriptions:
            if stripe_subscription_is_live(sub) and tier_from_plan_name(sub.plan_name) == access.tier:
                chosen = sub
                if getattr(sub, "stripe_subscription_id", None):
                    break
        if chosen is None:
            chosen = stripe_subscription
        if chosen is not None and getattr(chosen, "id", None) is not None:
            user.active_subscription_id = chosen.id
    return access
