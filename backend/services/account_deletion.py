"""Permanent deletion of the authenticated Sportbook Me account.

Identity is taken only from the verified JWT user. Client-supplied
user_id / email values are never used as the deletion target.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from assistant.models import AssistantConversation, AssistantMessage, AssistantPreference
from builder.models import BuilderExposureRule, BuilderLineup, BuilderPortfolio, BuilderRun
from coach.models import (
    CoachFinding,
    CoachMetric,
    CoachRecommendation,
    CoachSession,
    ContestResult,
    LineupResult,
)
from mission_control.models import MCPreference, MCSnapshot
from models.ai_models import AIAuditLog, AIChatLog
from models.domain import Lineup, LineupHistory, RevenueLog, Subscription, User
from scout.models import ScoutAlert

logger = logging.getLogger(__name__)

# Production may have these tables from later billing migrations. They are
# not modeled on origin/main; clean them with SQL when present.
_OPTIONAL_DELETE = (
    "user_oauth_identities",
    "apple_account_bindings",
    "billing_entitlements",
)
_OPTIONAL_NULL_USER_ID = ("billing_checkouts",)


async def _keys(db: AsyncSession, stmt) -> list:
    return list((await db.execute(stmt)).scalars().all())


async def _table_names(db: AsyncSession) -> set[str]:
    def names(sync_session):
        bind = sync_session.get_bind()
        return set(inspect(bind).get_table_names())

    return await db.run_sync(names)


async def delete_authenticated_user_account(db: AsyncSession, user: User) -> int:
    """Delete the current user's account and user-owned app data.

    Returns the deleted user id. Must be committed by the caller.
    On exception the caller must roll back so a partial delete is not persisted.
    """
    uid = int(user.id)

    user.active_subscription_id = None
    user.stripe_customer_id = None
    await db.flush()

    conv_keys = await _keys(
        db,
        select(AssistantConversation.conversation_id).where(AssistantConversation.user_id == uid),
    )
    if conv_keys:
        await db.execute(delete(AssistantMessage).where(AssistantMessage.conversation_id.in_(conv_keys)))

    run_keys = await _keys(db, select(BuilderRun.run_id).where(BuilderRun.user_id == uid))
    if run_keys:
        await db.execute(delete(BuilderExposureRule).where(BuilderExposureRule.run_id.in_(run_keys)))
        await db.execute(delete(BuilderLineup).where(BuilderLineup.run_id.in_(run_keys)))
        await db.execute(delete(BuilderPortfolio).where(BuilderPortfolio.run_id.in_(run_keys)))

    session_keys = await _keys(
        db, select(CoachSession.session_id).where(CoachSession.user_id == uid)
    )
    if session_keys:
        await db.execute(delete(CoachMetric).where(CoachMetric.session_id.in_(session_keys)))
        await db.execute(delete(CoachFinding).where(CoachFinding.session_id.in_(session_keys)))
        await db.execute(
            delete(CoachRecommendation).where(CoachRecommendation.session_id.in_(session_keys))
        )

    contest_keys = await _keys(
        db, select(ContestResult.contest_id).where(ContestResult.user_id == uid)
    )
    if contest_keys:
        await db.execute(delete(LineupResult).where(LineupResult.contest_id.in_(contest_keys)))

    await db.execute(delete(AssistantConversation).where(AssistantConversation.user_id == uid))
    await db.execute(delete(AssistantPreference).where(AssistantPreference.user_id == uid))
    await db.execute(delete(BuilderRun).where(BuilderRun.user_id == uid))
    await db.execute(delete(CoachSession).where(CoachSession.user_id == uid))
    await db.execute(delete(ContestResult).where(ContestResult.user_id == uid))
    await db.execute(delete(LineupResult).where(LineupResult.user_id == uid))
    await db.execute(delete(ScoutAlert).where(ScoutAlert.user_id == uid))
    await db.execute(delete(MCPreference).where(MCPreference.user_id == uid))
    await db.execute(delete(MCSnapshot).where(MCSnapshot.user_id == uid))
    await db.execute(delete(Lineup).where(Lineup.user_id == uid))
    await db.execute(delete(LineupHistory).where(LineupHistory.user_id == uid))

    tables = await _table_names(db)
    for table in _OPTIONAL_DELETE:
        if table in tables:
            await db.execute(text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": uid})
    for table in _OPTIONAL_NULL_USER_ID:
        if table in tables:
            await db.execute(
                text(f"UPDATE {table} SET user_id = NULL WHERE user_id = :uid"),
                {"uid": uid},
            )

    await db.execute(update(Subscription).where(Subscription.user_id == uid).values(user_id=None))
    await db.execute(update(RevenueLog).where(RevenueLog.user_id == uid).values(user_id=None))

    # Chat transcripts live in assistant_messages (deleted above). AIChatLog still
    # stores conversation_id, tools_invoked, and error text for that account —
    # delete those rows instead of nulling user_id.
    await db.execute(delete(AIChatLog).where(AIChatLog.user_id == uid))

    # AIAuditLog stores SHA-256 hashes of request/response bodies, token/cost
    # counters, endpoint name, and an optional plaintext error. Hashes and
    # usage counters are retained for cost accounting and security monitoring
    # after the user identifier and plaintext error are removed.
    await db.execute(
        update(AIAuditLog).where(AIAuditLog.user_id == uid).values(user_id=None, error=None)
    )

    await db.execute(delete(User).where(User.id == uid))
    logger.info("account_deleted user_id=%s", uid)
    return uid
