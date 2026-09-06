"""Apple signed-transaction verification via official SignedDataVerifier.

Uses app-store-server-library==3.1.2. Environment comes only from verified
Apple JWS. Client flags and NODE_ENV are not inputs.

Two verifiers:
- Environment.PRODUCTION + appAppleId 6808706342
- Environment.SANDBOX

Online OCSP checks default ON (3.1.2 patched OCSP freshness). If Apple's
OCSP responder is unreachable, verification fails closed. Override only with
APPLE_ENABLE_ONLINE_CHECKS=false for isolated tests — not a production default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
    VerificationException,
    VerificationStatus,
)

from services.apple_account_token import normalize_apple_account_token
from services.apple_certs import load_apple_root_certificates
from services.apple_environment import apple_is_test_mode_from_environment
from services.apple_plans import APPLE_APP_APPLE_ID, APPLE_BUNDLE_ID, get_apple_product


class AppleVerificationError(Exception):
    """Fail-closed verification denial. Never grant on this exception."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class AppleVerifiedTransaction:
    """Only produced after real JWS verification.

    Tests may construct this to exercise grant *decision* rules. Production
    code must obtain it only from ``verify_signed_transaction``.
    """

    original_transaction_id: str
    product_id: str
    bundle_id: str
    app_account_token: Optional[str]
    environment: str
    expires_at: Optional[datetime]
    revocation_date: Optional[datetime]
    revocation_reason: Optional[str] = None
    transaction_id: Optional[str] = None
    signed_date: Optional[datetime] = None
    purchase_date: Optional[datetime] = None
    original_purchase_date: Optional[datetime] = None


@dataclass(frozen=True)
class AppleGrantDecision:
    allowed: bool
    reason: str
    product_id: Optional[str] = None
    tier: Optional[str] = None
    billing_period: Optional[str] = None
    is_sandbox: bool = False


def apple_online_checks_enabled() -> bool:
    raw = os.getenv("APPLE_ENABLE_ONLINE_CHECKS", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def clear_apple_verifier_cache() -> None:
    _signed_data_verifiers.cache_clear()


@lru_cache(maxsize=1)
def _signed_data_verifiers() -> tuple[SignedDataVerifier, SignedDataVerifier]:
    roots = load_apple_root_certificates()
    if not roots:
        raise AppleVerificationError("apple_root_certificates_not_configured")
    online = apple_online_checks_enabled()
    production = SignedDataVerifier(
        roots,
        online,
        Environment.PRODUCTION,
        APPLE_BUNDLE_ID,
        APPLE_APP_APPLE_ID,
    )
    sandbox = SignedDataVerifier(
        roots,
        online,
        Environment.SANDBOX,
        APPLE_BUNDLE_ID,
        APPLE_APP_APPLE_ID,
    )
    return production, sandbox


def _map_verification_status(status: Any) -> str:
    if status == VerificationStatus.INVALID_APP_IDENTIFIER:
        return "wrong_bundle_id"
    if status == VerificationStatus.INVALID_ENVIRONMENT:
        return "invalid_environment"
    if status == VerificationStatus.RETRYABLE_VERIFICATION_FAILURE:
        return "retryable_verification_failure"
    return "invalid_signature"


def _verify_with_both(method_name: str, signed: str) -> Any:
    if not signed or not isinstance(signed, str):
        raise AppleVerificationError("invalid_signature")
    try:
        verifiers = _signed_data_verifiers()
    except AppleVerificationError:
        raise
    last_reason = "invalid_signature"
    for verifier in verifiers:
        try:
            return getattr(verifier, method_name)(signed)
        except VerificationException as exc:
            status = getattr(exc, "status", None)
            last_reason = _map_verification_status(status)
        except Exception:
            last_reason = "invalid_signature"
    raise AppleVerificationError(last_reason)


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


def _environment_name(payload: Any) -> str:
    raw = getattr(payload, "rawEnvironment", None)
    if raw:
        return str(raw)
    env = getattr(payload, "environment", None)
    if env is None:
        return ""
    return getattr(env, "value", str(env))


def _account_token(payload: Any) -> Optional[str]:
    raw = getattr(payload, "appAccountToken", None)
    if raw is None:
        return None
    return str(raw)


def transaction_from_library_payload(payload: Any) -> AppleVerifiedTransaction:
    original = getattr(payload, "originalTransactionId", None) or ""
    env_name = _environment_name(payload)
    revocation_reason = getattr(payload, "revocationReason", None)
    return AppleVerifiedTransaction(
        original_transaction_id=str(original),
        product_id=str(getattr(payload, "productId", None) or ""),
        bundle_id=str(getattr(payload, "bundleId", None) or ""),
        app_account_token=_account_token(payload),
        environment=env_name,
        expires_at=_ms_to_dt(getattr(payload, "expiresDate", None)),
        revocation_date=_ms_to_dt(getattr(payload, "revocationDate", None)),
        revocation_reason=None if revocation_reason is None else str(revocation_reason),
        transaction_id=getattr(payload, "transactionId", None),
        signed_date=_ms_to_dt(getattr(payload, "signedDate", None)),
        purchase_date=_ms_to_dt(getattr(payload, "purchaseDate", None)),
        original_purchase_date=_ms_to_dt(getattr(payload, "originalPurchaseDate", None)),
    )


def verify_signed_transaction(
    signed_transaction: str,
    *,
    expected_bundle_id: str = APPLE_BUNDLE_ID,
    expected_account_token: Optional[str] = None,
) -> AppleVerifiedTransaction:
    """Verify an Apple JWS transaction with SignedDataVerifier."""
    payload = _verify_with_both("verify_and_decode_signed_transaction", signed_transaction)
    verified = transaction_from_library_payload(payload)
    if expected_bundle_id and (verified.bundle_id or "").strip() != expected_bundle_id:
        raise AppleVerificationError("wrong_bundle_id")
    if expected_account_token is not None:
        incoming = normalize_apple_account_token(verified.app_account_token)
        expected = normalize_apple_account_token(expected_account_token)
        if incoming is None or expected is None or incoming != expected:
            raise AppleVerificationError("wrong_app_account_binding")
    return verified


def verify_signed_renewal_info(signed_renewal_info: str) -> Any:
    """Verify Apple signedRenewalInfo JWS. Returns the library payload."""
    return _verify_with_both("verify_and_decode_renewal_info", signed_renewal_info)


def verify_signed_notification(signed_payload: str) -> Any:
    """Verify an ASSN V2 signedPayload. Returns the library payload."""
    return _verify_with_both("verify_and_decode_notification", signed_payload)


def apple_grant_decision(
    verified: AppleVerifiedTransaction,
    *,
    bound_account_token: Optional[str],
    expected_bundle_id: str = APPLE_BUNDLE_ID,
    now: Optional[datetime] = None,
) -> AppleGrantDecision:
    """Apply fail-closed grant rules to an already-verified transaction.

    A writer may set ``paid_verified=True`` only after ``allowed=True``.
    Sandbox decisions set ``is_sandbox=True`` so the writer stores
    ``is_test_mode=True``. Eligibility does not consult NODE_ENV.
    """
    is_sandbox = apple_is_test_mode_from_environment(verified.environment)
    if (verified.bundle_id or "").strip() != expected_bundle_id:
        return AppleGrantDecision(allowed=False, reason="wrong_bundle_id")
    product = get_apple_product(verified.product_id)
    if product is None:
        return AppleGrantDecision(
            allowed=False, reason="unknown_product", product_id=verified.product_id,
        )
    incoming = normalize_apple_account_token(verified.app_account_token)
    expected = normalize_apple_account_token(bound_account_token)
    if incoming is None or expected is None or incoming != expected:
        return AppleGrantDecision(allowed=False, reason="wrong_app_account_binding")
    if verified.revocation_date is not None or verified.revocation_reason:
        return AppleGrantDecision(
            allowed=False, reason="revoked", product_id=product.product_id,
        )
    clock = now or datetime.now(timezone.utc)
    if verified.expires_at is not None:
        expires = verified.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= clock:
            return AppleGrantDecision(
                allowed=False, reason="expired", product_id=product.product_id,
            )
    if not verified.original_transaction_id:
        return AppleGrantDecision(allowed=False, reason="missing_original_transaction_id")
    return AppleGrantDecision(
        allowed=True,
        reason="ok_sandbox" if is_sandbox else "ok",
        product_id=product.product_id,
        tier=product.tier,
        billing_period=product.billing_period,
        is_sandbox=is_sandbox,
    )
