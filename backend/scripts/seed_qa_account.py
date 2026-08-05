"""
QA staging account seeder for Sportsbook Me DFS AI.

Usage:
    python -m scripts.seed_qa_account

Required env vars:
    QA_TEST_EMAIL — email for the QA account
    QA_TEST_PASSWORD — password for the QA account
    QA_TEST_ACCOUNT_ENABLED — must be "true"
    DATABASE_URL — PostgreSQL connection string

Safety:
    - Refuses to run if NODE_ENV=production
    - Refuses to run unless QA_TEST_ACCOUNT_ENABLED=true
    - Never logs the password or hash
    - Idempotent: safe to run repeatedly
"""

import asyncio
import os
import sys
import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from passlib.context import CryptContext
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REQUIRED_ENV = ["QA_TEST_EMAIL", "QA_TEST_PASSWORD", "QA_TEST_ACCOUNT_ENABLED", "DATABASE_URL"]

# ── Validation ─────────────────────────────────────────────────


def _validate():
    errors = []
    if os.getenv("NODE_ENV") == "production":
        errors.append("REFUSED: NODE_ENV is 'production'. This script is staging-only.")
    if os.getenv("QA_TEST_ACCOUNT_ENABLED") != "true":
        errors.append("REFUSED: QA_TEST_ACCOUNT_ENABLED is not 'true'.")
    for var in REQUIRED_ENV:
        if not os.getenv(var):
            errors.append(f"REFUSED: {var} is not set.")
    password = os.getenv("QA_TEST_PASSWORD", "")
    if password:
        try:
            password.encode("utf-8")
        except UnicodeEncodeError:
            errors.append("REFUSED: QA_TEST_PASSWORD is not valid UTF-8.")
        if len(password.encode("utf-8")) < 8:
            errors.append("REFUSED: QA_TEST_PASSWORD must be at least 8 bytes (UTF-8).")
    if errors:
        for e in errors:
            logger.error(e)
        sys.exit(1)


# ── Seed ──────────────────────────────────────────────────────


async def _seed():
    _validate()

    email = os.getenv("QA_TEST_EMAIL")
    password = os.getenv("QA_TEST_PASSWORD")

    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url or "", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            # Look up existing user
            result = await db.execute(select(text("*")).select_from(text("users")).where(text("users.email = :email")).params(email=email))
            row = result.fetchone()

            password_hash = pwd_context.hash(password)

            if row:
                user_id = row[0] if isinstance(row, tuple) else row.id
                await db.execute(
                    text("""
                        UPDATE users SET
                            hashed_password = :hash,
                            is_active = true,
                            is_pro = true,
                            role = 'admin'
                        WHERE id = :id
                    """),
                    {"hash": password_hash, "id": user_id},
                )
                logger.info("QA account UPDATED (existing user). id=%s email=%s", user_id, email[:6] + "...")
            else:
                result = await db.execute(
                    text("""
                        INSERT INTO users (email, hashed_password, role, is_active, is_pro, created_at)
                        VALUES (:email, :hash, 'admin', true, true, :now)
                        RETURNING id
                    """),
                    {"email": email, "hash": password_hash, "now": datetime.now(timezone.utc)},
                )
                user_id = result.fetchone()[0]
                logger.info("QA account CREATED. id=%s email=%s", user_id, email[:6] + "...")

            # Ensure subscription entitlement (Elite Stack, staging-only)
            sub_result = await db.execute(
                text("SELECT id FROM subscriptions WHERE user_id = :uid AND source = 'qa_seed'"),
                {"uid": user_id},
            )
            sub_row = sub_result.fetchone()

            if sub_row:
                sub_id = sub_row[0] if isinstance(sub_row, tuple) else sub_row.id
                await db.execute(
                    text("""
                        UPDATE subscriptions SET
                            plan_name = 'Elite Stack',
                            status = 'active',
                            source = 'qa_seed',
                            environment = 'staging',
                            current_period_end = :period_end
                        WHERE id = :id
                    """),
                    {"period_end": datetime(2099, 12, 31, tzinfo=timezone.utc), "id": sub_id},
                )
                logger.info("QA subscription UPDATED (existing). plan=Elite Stack")
            else:
                await db.execute(
                    text("""
                        INSERT INTO subscriptions (user_id, plan_name, status, source, environment, current_period_end, created_at)
                        VALUES (:uid, 'Elite Stack', 'active', 'qa_seed', 'staging', :period_end, :now)
                    """),
                    {"uid": user_id, "period_end": datetime(2099, 12, 31, tzinfo=timezone.utc), "now": datetime.now(timezone.utc)},
                )
                logger.info("QA subscription CREATED. plan=Elite Stack source=qa_seed")

            await db.commit()
            logger.info("COMMIT — QA account ready.")

        except Exception:
            await db.rollback()
            logger.exception("ROLLBACK — QA account seeding failed.")
            raise
        finally:
            await engine.dispose()


# ── Entry Point ───────────────────────────────────────────────


def main():
    asyncio.run(_seed())


if __name__ == "__main__":
    main()