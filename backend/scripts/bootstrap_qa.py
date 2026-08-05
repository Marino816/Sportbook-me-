"""
QA staging account bootstrap.

Called during FastAPI startup. Idempotent — safe to run repeatedly.
Only activates when QA_TEST_ACCOUNT_ENABLED=true and not in production.
"""

import os
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from passlib.context import CryptContext

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def bootstrap_qa_account(db: AsyncSession) -> None:
    """
    Idempotent QA account bootstrap. Skips silently if not configured.
    
    Required env vars:
        QA_TEST_ACCOUNT_ENABLED=true
        QA_TEST_EMAIL=qa@sportbookme.ai
        QA_TEST_PASSWORD=<secure value>
        NODE_ENV != production (unless QA_BOOTSTRAP_IN_PRODUCTION=true)
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

    # Check for existing user
    result = await db.execute(
        text("SELECT id, email, role, is_pro FROM users WHERE email = :email"),
        {"email": email},
    )
    row = result.fetchone()

    if row:
        await db.execute(
            text("""
                UPDATE users SET
                    hashed_password = :hash,
                    is_active = true,
                    is_pro = true,
                    role = 'admin'
                WHERE email = :email
            """),
            {"hash": password_hash, "email": email},
        )
        logger.info("QA account updated (existing).")
    else:
        await db.execute(
            text("""
                INSERT INTO users (email, hashed_password, role, is_active, is_pro, created_at)
                VALUES (:email, :hash, 'admin', true, true, :now)
            """),
            {"email": email, "hash": password_hash, "now": datetime.now(timezone.utc)},
        )
        logger.info("QA account created.")

    # Elite Stack entitlement
    result = await db.execute(
        text("SELECT id FROM subscriptions WHERE user_id = (SELECT id FROM users WHERE email = :email) AND source = 'qa_seed'"),
        {"email": email},
    )
    sub = await result.fetchone()

    if sub:
        await db.execute(
            text("""
                UPDATE subscriptions SET
                    plan_name = 'Elite Stack',
                    status = 'active',
                    current_period_end = :period_end
                WHERE id = :id
            """),
            {"period_end": datetime(2099, 12, 31, tzinfo=timezone.utc), "id": sub[0]},
        )
    else:
        await db.execute(
            text("""
                INSERT INTO subscriptions (user_id, plan_name, status, source, environment, current_period_end, created_at)
                SELECT id, 'Elite Stack', 'active', 'qa_seed', 'staging', :period_end, :now
                FROM users WHERE email = :email
            """),
            {"period_end": datetime(2099, 12, 31, tzinfo=timezone.utc), "now": datetime.now(timezone.utc), "email": email},
        )

    await db.commit()
    logger.info("QA account ready.")