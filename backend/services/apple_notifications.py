"""App Store Server Notifications V2 — verified lifecycle.

POST /api/webhooks/apple requires Apple's signedPayload.
Outer notification, signedTransactionInfo, and signedRenewalInfo are
each verified with SignedDataVerifier. Unsigned JSON never grants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import AppleNotificationEvent, User
from services.apple_account_token import lookup_user_id_for_apple_account_token
from services.apple_environment import (
    APPLE_ENVIRONMENT_PRODUCTION,
    normalize_apple_environment,
)
from services.apple_plans import get_apple_product
from services.apple_verify import (
    AppleVerificationError,
    AppleVerifiedTransaction,
    apple_grant_decision,
    verify_signed_notification,
    verify_signed_renewal_info,
    verify_signed_transaction,
)
from services.apple_writer import (
    apply_apple_status_update,
    find_apple_entitlement,
    mask_apple_id,
    upsert_verified_apple_entitlement,
)
from services.entitlements import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
)

logger = logging.getLogger(__name__)

ASSN_V2_TYPES = frozenset({
    "SUBSCRIBED",
    "DID_RENEW",
    "DID_CHANGE_RENEWAL_STATUS",
    "DID_CHANGE_RENEWAL_PREF",
    "DID_FAIL_TO_RENEW",
    "GRACE_PERIOD_EXPIRED",
    "EXPIRED",
    "REFUND",
    "REVOKE",
})

# Apple Status: 1 active, 2 expired, 3 billing retry, 4 grace, 5 revoked
_STATUS_STILL_HAS_ACCESS = frozenset({1, 3, 4})


@dataclass(frozen=True)
class AppleNotificationResult:
    decision: str
    notification_uuid: Optional[str] = None
    notification_type: Optional[str] = None
    subtype: Optional[str] = None
    environment: Optional[str] = None


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _ms_to_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _environment_from_payloads(*payloads: Any) -> str:
    for payload in payloads:
        if payload is None:
            continue
        raw = getattr(payload, "rawEnvironment", None) or _enum_value(
            getattr(payload, "environment", None)
        )
        normalized = normalize_apple_environment(str(raw or ""))
        if normalized:
            return normalized
    return APPLE_ENVIRONMENT_PRODUCTION


async def _record_notification(
    db: AsyncSession,
    *,
    notification_uuid: str,
    signed_date: Optional[datetime],
    notification_type: Optional[str],
    subtype: Optional[str],
    environment: Optional[str],
    original_transaction_id: Optional[str],
    transaction_id: Optional[str],
    product_id: Optional[str],
    decision: str,
) -> AppleNotificationEvent:
    row = AppleNotificationEvent(
        notification_uuid=notification_uuid,
        signed_date=signed_date,
        notification_type=notification_type,
        subtype=subtype,
        environment=environment,
        original_transaction_id=original_transaction_id,
        transaction_id=transaction_id,
        product_id=product_id,
        decision=decision,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


async def handle_signed_notification(db: AsyncSession, signed_payload: str) -> AppleNotificationResult:
    """Verify and apply one ASSN V2 notification. Never grants from unsigned data."""
    if not signed_payload or not isinstance(signed_payload, str):
        raise AppleVerificationError("missing_signed_payload")
    decoded = verify_signed_notification(signed_payload)
    notification_uuid = getattr(decoded, "notificationUUID", None)
    if not notification_uuid:
        raise AppleVerificationError("missing_notification_uuid")
    existing = (
        await db.execute(
            select(AppleNotificationEvent).where(
                AppleNotificationEvent.notification_uuid == str(notification_uuid)
            )
        )
    ).scalars().first()
    if existing is not None:
        logger.info(
            "apple notification duplicate uuid=%s type=%s",
            notification_uuid,
            existing.notification_type,
        )
        return AppleNotificationResult(
            decision="duplicate",
            notification_uuid=str(notification_uuid),
            notification_type=existing.notification_type,
            subtype=existing.subtype,
            environment=existing.environment,
        )

    notification_type = _enum_value(getattr(decoded, "notificationType", None)) or getattr(
        decoded, "rawNotificationType", None
    )
    subtype = _enum_value(getattr(decoded, "subtype", None)) or getattr(decoded, "rawSubtype", None)
    data = getattr(decoded, "data", None)
    signed_date = _ms_to_dt(getattr(decoded, "signedDate", None))

    transaction: Optional[AppleVerifiedTransaction] = None
    renewal = None
    if data is not None:
        signed_txn = getattr(data, "signedTransactionInfo", None)
        if signed_txn:
            transaction = verify_signed_transaction(signed_txn)
        signed_renewal = getattr(data, "signedRenewalInfo", None)
        if signed_renewal:
            renewal = verify_signed_renewal_info(signed_renewal)

    environment = _environment_from_payloads(data, transaction, renewal)
    original_id = transaction.original_transaction_id if transaction else getattr(
        renewal, "originalTransactionId", None
    )
    product_id = transaction.product_id if transaction else getattr(renewal, "productId", None)
    txn_id = transaction.transaction_id if transaction else None

    logger.info(
        "apple notification uuid=%s type=%s subtype=%s env=%s product=%s original=%s txn=%s",
        notification_uuid,
        notification_type,
        subtype,
        environment,
        product_id,
        mask_apple_id(original_id),
        mask_apple_id(txn_id),
    )

    if notification_type == "TEST":
        await _record_notification(
            db,
            notification_uuid=str(notification_uuid),
            signed_date=signed_date,
            notification_type=notification_type,
            subtype=subtype,
            environment=environment,
            original_transaction_id=original_id,
            transaction_id=txn_id,
            product_id=product_id,
            decision="ignored_test",
        )
        return AppleNotificationResult(
            decision="ignored_test",
            notification_uuid=str(notification_uuid),
            notification_type=notification_type,
            subtype=subtype,
            environment=environment,
        )

    decision = await _apply_lifecycle(
        db,
        notification_type=str(notification_type or ""),
        subtype=str(subtype or "") if subtype else None,
        environment=environment,
        data=data,
        transaction=transaction,
        renewal=renewal,
        signed_date=signed_date,
    )
    await _record_notification(
        db,
        notification_uuid=str(notification_uuid),
        signed_date=signed_date,
        notification_type=notification_type,
        subtype=subtype,
        environment=environment,
        original_transaction_id=original_id,
        transaction_id=txn_id,
        product_id=product_id,
        decision=decision,
    )
    return AppleNotificationResult(
        decision=decision,
        notification_uuid=str(notification_uuid),
        notification_type=notification_type,
        subtype=subtype,
        environment=environment,
    )


async def _resolve_user(
    db: AsyncSession,
    transaction: Optional[AppleVerifiedTransaction],
    renewal: Any,
) -> Optional[User]:
    token = None
    if transaction is not None:
        token = transaction.app_account_token
    if token is None and renewal is not None:
        token = getattr(renewal, "appAccountToken", None)
    user_id = await lookup_user_id_for_apple_account_token(db, token)
    if user_id is None:
        return None
    return (
        await db.execute(select(User).where(User.id == user_id))
    ).scalars().first()


def _apple_data_status(data: Any) -> Optional[int]:
    if data is None:
        return None
    raw = getattr(data, "rawStatus", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    status = getattr(data, "status", None)
    value = getattr(status, "value", status)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _in_retry_or_grace(data: Any, renewal: Any) -> bool:
    apple_status = _apple_data_status(data)
    if apple_status in _STATUS_STILL_HAS_ACCESS:
        return True
    if renewal is not None and getattr(renewal, "isInBillingRetryPeriod", None) is True:
        return True
    if renewal is not None and getattr(renewal, "gracePeriodExpiresDate", None):
        grace = _ms_to_dt(renewal.gracePeriodExpiresDate)
        if grace is not None and grace > datetime.now(timezone.utc):
            return True
    return False


async def _apply_lifecycle(
    db: AsyncSession,
    *,
    notification_type: str,
    subtype: Optional[str],
    environment: str,
    data: Any,
    transaction: Optional[AppleVerifiedTransaction],
    renewal: Any,
    signed_date: Optional[datetime],
) -> str:
    is_sandbox = environment == "Sandbox"
    original_id = (
        transaction.original_transaction_id if transaction
        else getattr(renewal, "originalTransactionId", None)
    )
    if not original_id:
        return "missing_original_transaction_id"

    row = await find_apple_entitlement(
        db, original_transaction_id=str(original_id), is_sandbox=is_sandbox,
    )

    if notification_type in {"REFUND", "REVOKE"}:
        if row is None:
            return "no_matching_entitlement"
        return await apply_apple_status_update(
            db,
            row,
            original_transaction_id=str(original_id),
            environment=environment,
            status=STATUS_REVOKED,
            signed_at=signed_date or (transaction.signed_date if transaction else None),
            product_id=transaction.product_id if transaction else None,
            period_end=transaction.expires_at if transaction else None,
            transaction_id=transaction.transaction_id if transaction else None,
        )

    if notification_type in {"EXPIRED", "GRACE_PERIOD_EXPIRED"}:
        if row is None:
            return "no_matching_entitlement"
        return await apply_apple_status_update(
            db,
            row,
            original_transaction_id=str(original_id),
            environment=environment,
            status=STATUS_EXPIRED,
            signed_at=signed_date or (transaction.signed_date if transaction else None),
            product_id=transaction.product_id if transaction else None,
            period_end=transaction.expires_at if transaction else None,
            transaction_id=transaction.transaction_id if transaction else None,
        )

    if notification_type == "DID_FAIL_TO_RENEW":
        if _in_retry_or_grace(data, renewal):
            if row is None:
                return "billing_retry_no_row"
            return await apply_apple_status_update(
                db,
                row,
                original_transaction_id=str(original_id),
                environment=environment,
                status=STATUS_ACTIVE,
                signed_at=signed_date or (transaction.signed_date if transaction else None),
                product_id=transaction.product_id if transaction else None,
                period_end=transaction.expires_at if transaction else None,
                transaction_id=transaction.transaction_id if transaction else None,
            )
        if row is None:
            return "no_matching_entitlement"
        return await apply_apple_status_update(
            db,
            row,
            original_transaction_id=str(original_id),
            environment=environment,
            status=STATUS_EXPIRED,
            signed_at=signed_date or (transaction.signed_date if transaction else None),
            product_id=transaction.product_id if transaction else None,
            period_end=transaction.expires_at if transaction else None,
            transaction_id=transaction.transaction_id if transaction else None,
        )

    if notification_type == "DID_CHANGE_RENEWAL_STATUS":
        if row is None:
            return "renewal_status_no_row"
        return await apply_apple_status_update(
            db,
            row,
            original_transaction_id=str(original_id),
            environment=environment,
            status=row.status,
            signed_at=signed_date or (transaction.signed_date if transaction else None),
            product_id=transaction.product_id if transaction else None,
            period_end=transaction.expires_at if transaction else None,
            transaction_id=transaction.transaction_id if transaction else None,
        )

    if notification_type == "DID_CHANGE_RENEWAL_PREF":
        if row is None:
            return "renewal_pref_no_row"
        current_product = transaction.product_id if transaction else None
        if current_product and get_apple_product(current_product) is None:
            return "unknown_product"
        return await apply_apple_status_update(
            db,
            row,
            original_transaction_id=str(original_id),
            environment=environment,
            status=row.status,
            signed_at=signed_date or (transaction.signed_date if transaction else None),
            product_id=current_product,
            period_end=transaction.expires_at if transaction else None,
            transaction_id=transaction.transaction_id if transaction else None,
        )

    if notification_type in {"SUBSCRIBED", "DID_RENEW"}:
        if transaction is None:
            return "missing_signed_transaction"
        user = await _resolve_user(db, transaction, renewal)
        if user is None:
            return "unbound_app_account_token"
        bound = (
            await lookup_user_id_for_apple_account_token(db, transaction.app_account_token)
        )
        if bound != user.id:
            return "wrong_app_account_binding"
        decision = apple_grant_decision(transaction, bound_account_token=transaction.app_account_token)
        if not decision.allowed:
            return decision.reason
        _row, result = await upsert_verified_apple_entitlement(
            db, user, transaction, decision, status=STATUS_ACTIVE,
        )
        return result

    return "ignored_unhandled_type"
