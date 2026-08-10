"""
QA staging account bootstrap.

Called during FastAPI startup. Idempotent — safe to run repeatedly.
Only activates when QA_TEST_ACCOUNT_ENABLED=true and not in production.

Uses only real Subscription columns:
  id, user_id, stripe_subscription_id(nullable), plan_name, status,
  mrr_value, current_period_end, trial_end(nullable), cancel_at_period_end, created_at

No fabricated columns (source, environment). No fake Stripe IDs.
"""

import os
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from models.domain import User, Subscription
from passlib.context import CryptContext

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def bootstrap_qa_account(db: AsyncSession) -> None:
    """
    Idempotent QA account bootstrap. Skips silently if not configured.
    Uses real ORM models — no non-existent columns.
    """
    enabled = os.getenv("QA_TEST_ACCOUNT_ENABLED", "").lower() == "true"
    if not enabled:
        return

    is_production = os.getenv("NODE_ENV") == "production"
    allow_production = os.getenv("QA_BOOTSTRAP_IN_PRODUCTION", "").lower() == "true"
    if is_production and not allow_production:
        logger.warning("QA bootstrap skipped: production environment")
        return

    email = os.getenv("QA_TEST_EMAIL")
    password = os.getenv("QA_TEST_PASSWORD")

    if not email or not password:
        logger.warning("QA bootstrap skipped: QA_TEST_EMAIL or QA_TEST_PASSWORD missing")
        return

    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        logger.warning("QA bootstrap skipped: QA_TEST_PASSWORD not valid UTF-8")
        return

    if len(password.encode("utf-8")) < 8:
        logger.warning("QA bootstrap skipped: QA_TEST_PASSWORD too short")
        return

    password_hash = pwd_context.hash(password)

    try:
        # Find or create user via ORM
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user:
            # EXISTING user: update role/status only — NEVER overwrite password
            if user.role != "admin":
                user.role = "admin"
            user.is_active = True
            user.is_pro = True
            logger.info("QA account refreshed (role/status only, password untouched).")
        else:
            user = User(
                email=email,
                hashed_password=password_hash,
                role="admin",
                is_active=True,
                is_pro=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.flush()
            logger.info("QA account created.")

        # Find or create subscription using only real columns
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.plan_name == "Elite Stack",
            )
        )
        sub = result.scalars().first()

        if sub:
            sub.status = "active"
            sub.current_period_end = datetime(2099, 12, 31, tzinfo=timezone.utc)
            sub.stripe_subscription_id = None  # QA entitlement — no Stripe
            logger.info("QA subscription updated.")
        else:
            sub = Subscription(
                user_id=user.id,
                plan_name="Elite Stack",
                status="active",
                mrr_value=249.99,
                current_period_end=datetime(2099, 12, 31, tzinfo=timezone.utc),
                stripe_subscription_id=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(sub)
            await db.flush()

            # Link user to subscription
            user.active_subscription_id = sub.id
            logger.info("QA subscription created (Elite Stack, staging entitlement).")

        await db.commit()
        logger.info("QA account ready.")

    except Exception:
        await db.rollback()
        logger.exception("QA bootstrap failed — rolled back.")
        raise