"""PayKings (NMI gateway) webhook signature verification and event dispatch.

Signature (mandatory):
    HMAC_SHA256(signing_key, nonce + "." + raw_body)

Header:
    Webhook-Signature: t=<nonce>,s=<signature>

Verify against the exact raw request body BEFORE JSON parsing.
Do not log PAYKINGS_WEBHOOK_SIGNING_KEY, PAN, CVV, or the signature header.

This module does not mutate User / Subscription entitlements. Recurring add
binds provider_subscription_id via order_id -> checkout_reference only.

Documented PayKings webhook source IP ranges (NOT enforced until Railway /
proxy forwarding is confirmed):
    104.192.32.81 - 104.192.32.87
    104.192.36.81 - 104.192.36.87
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

from services.paykings_plans import SBME_PLAN_IDS

PROVIDER = "paykings"

# Confirmed PayKings payload fields (do not invent others).
# Envelope: event_id, event_type.
# Transaction: transaction_id, customerid, order_id, requested_amount,
# currency, condition, transaction_type, is_test_mode.
# Nested action: success, response_code, response_text.
# Recurring (same event_body for add / update / delete):
#   subscription_id, subscription_type, next_charge_date,
#   completed_payments, attempted_payments, remaining_payments,
#   plan.{id,name,amount,day_frequency,payments,month_frequency,day_of_month}
#   features.is_test_mode (optional)
# Refund events use the same transaction event_body shape as sales
# (official NMI webhook examples). ACU summaries are a different family:
# official examples include card/PII arrays that are NOT in this allowlist
# and are never persisted. ACU persistence is envelope + already-approved
# operational identifiers only.
# received_at / processed_at / processing_status are OUR ledger columns,
# not PayKings payload fields.
CONFIRMED_SCALAR_FIELDS = (
    "event_id",
    "event_type",
    "transaction_id",
    "customerid",
    "order_id",
    "requested_amount",
    "currency",
    "condition",
    "transaction_type",
    "is_test_mode",
    "subscription_id",
    "subscription_type",
    "next_charge_date",
    "completed_payments",
    "attempted_payments",
    "remaining_payments",
)
CONFIRMED_ACTION_FIELDS = ("success", "response_code", "response_text")
CONFIRMED_PLAN_FIELDS = (
    "id",
    "name",
    "amount",
    "day_frequency",
    "payments",
    "month_frequency",
    "day_of_month",
)
CONFIRMED_FEATURES_FIELDS = ("is_test_mode",)
_ID_SCALAR_FIELDS = (
    "event_id",
    "transaction_id",
    "customerid",
    "order_id",
    "subscription_id",
)

# Official PayKings/NMI webhook event_type values (control-panel subscribed set).
# Chargeback type strings are still unconfirmed in-repo; that handler is not dispatched.
EVENT_TRANSACTION_SUCCESS = "transaction.sale.success"
EVENT_TRANSACTION_FAILURE = "transaction.sale.failure"
EVENT_TRANSACTION_UNKNOWN = "transaction.sale.unknown"
EVENT_TRANSACTION_REFUND_SUCCESS = "transaction.refund.success"
EVENT_TRANSACTION_REFUND_FAILURE = "transaction.refund.failure"
EVENT_RECURRING_CREATED = "recurring.subscription.add"
EVENT_RECURRING_UPDATED = "recurring.subscription.update"
EVENT_RECURRING_CANCELED = "recurring.subscription.delete"
EVENT_ACU_AUTOMATICALLY_UPDATED = "acu.summary.automaticallyupdated"
EVENT_ACU_CONTACT_CUSTOMER = "acu.summary.contactcustomer"
EVENT_ACU_CLOSED_ACCOUNT = "acu.summary.closedaccount"

# Explicit allowlist of the 11 subscribed event types. Unknown types stay unmapped.
SUBSCRIBED_EVENT_TYPES = frozenset({
    EVENT_RECURRING_UPDATED,
    EVENT_RECURRING_CREATED,
    EVENT_RECURRING_CANCELED,
    EVENT_TRANSACTION_FAILURE,
    EVENT_TRANSACTION_SUCCESS,
    EVENT_TRANSACTION_UNKNOWN,
    EVENT_TRANSACTION_REFUND_SUCCESS,
    EVENT_TRANSACTION_REFUND_FAILURE,
    EVENT_ACU_AUTOMATICALLY_UPDATED,
    EVENT_ACU_CONTACT_CUSTOMER,
    EVENT_ACU_CLOSED_ACCOUNT,
})

PAYKINGS_WEBHOOK_SOURCE_IP_RANGES = (
    ("104.192.32.81", "104.192.32.87"),
    ("104.192.36.81", "104.192.36.87"),
)

_SENSITIVE_KEY_RE = re.compile(
    r"(cc_number|cc_exp|card_number|cvv|cvc|csc|cavv|track|magnetic|"
    r"account_number|routing|ssn|social_security|drivers_license|"
    r"password|secret|signing|payment_token|security_key)",
    re.IGNORECASE,
)

_SIG_HEADER_RE = re.compile(r"t=([^,]+),s=(.+)", re.DOTALL)


def signing_key() -> Optional[str]:
    key = os.getenv("PAYKINGS_WEBHOOK_SIGNING_KEY", "").strip()
    return key or None


def parse_signature_header(header: Optional[str]) -> Optional[tuple[str, str]]:
    """Parse Webhook-Signature: t=<nonce>,s=<signature>. None if malformed."""
    if not header or not str(header).strip():
        return None
    raw = str(header).strip()
    match = _SIG_HEADER_RE.fullmatch(raw) or _SIG_HEADER_RE.search(raw)
    if not match:
        return None
    nonce, sig = match.group(1).strip(), match.group(2).strip()
    if not nonce or not sig:
        return None
    return nonce, sig


def compute_signature(key: str, nonce: str, raw_body: bytes) -> str:
    """HMAC-SHA256 hex digest of nonce + '.' + raw_body."""
    message = nonce.encode("utf-8") + b"." + raw_body
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def signatures_match(expected: str, received: str) -> bool:
    try:
        return hmac.compare_digest(expected.lower(), received.lower())
    except (TypeError, ValueError):
        return False


def verify_request(raw_body: bytes, signature_header: Optional[str]) -> tuple[bool, str]:
    """Return (ok, reason_code). Never includes the signing key in reason_code."""
    key = signing_key()
    if not key:
        return False, "not_configured"
    parsed = parse_signature_header(signature_header)
    if parsed is None:
        if not signature_header or not str(signature_header).strip():
            return False, "missing_signature"
        return False, "malformed_signature"
    nonce, received = parsed
    expected = compute_signature(key, nonce, raw_body)
    if not signatures_match(expected, received):
        return False, "invalid_signature"
    return True, "ok"


def parse_json_body(raw_body: bytes) -> Any:
    try:
        text = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_json") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc


def sanitize_payload(value: Any) -> Any:
    """Drop PAN/CVV/secrets. Keep structure for audit without card data."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = str(k)
            if _SENSITIVE_KEY_RE.search(key):
                out[key] = "[redacted]"
            else:
                out[key] = sanitize_payload(v)
        return out
    if isinstance(value, list):
        return [sanitize_payload(v) for v in value]
    return value


def _as_id_str(value: Any) -> Optional[str]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            return str(value)
        return str(int(value) if isinstance(value, float) else value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _field_sources(payload: dict) -> list[dict]:
    """Read confirmed fields from the envelope and, if present, event_body.

    event_body is the documented NMI wrapper around the transaction object.
    We do not store event_body itself — only the confirmed field names.
    """
    sources = [payload]
    body = payload.get("event_body")
    if isinstance(body, dict):
        sources.append(body)
    return sources


def _first_present(sources: list[dict], key: str) -> Any:
    for src in sources:
        if key in src and src[key] is not None:
            return src[key]
    return None


def _nested_object(sources: list[dict], key: str) -> dict:
    for src in sources:
        value = src.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _allowlist_object(obj: dict, keys: tuple[str, ...], id_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        if key not in obj or obj[key] is None:
            continue
        if key in id_keys:
            coerced = _as_id_str(obj[key])
            if coerced is not None:
                out[key] = coerced
            continue
        out[key] = obj[key]
    return out


def recognized_sbme_plan_id(plan_id: Any) -> Optional[str]:
    """Return the Sportbook Me plan id if it matches a known SBME_* constant."""
    coerced = _as_id_str(plan_id)
    if coerced and coerced in SBME_PLAN_IDS:
        return coerced
    return None


def operational_payload(parsed: Any) -> dict[str, Any]:
    """Allowlisted fields plus in-memory plan recognition. Never persisted as-is
    with extra keys — callers persist extract_confirmed_fields() only.
    """
    extracted = extract_confirmed_fields(parsed)
    plan = extracted.get("plan") if isinstance(extracted.get("plan"), dict) else {}
    recognized = recognized_sbme_plan_id(plan.get("id"))
    if recognized:
        extracted["recognized_sbme_plan_id"] = recognized
    return extracted


def extract_confirmed_fields(parsed: Any) -> dict[str, Any]:
    """Allowlist of confirmed PayKings fields only. No PAN/CVV. No invented keys."""
    if not isinstance(parsed, dict):
        return {}
    sources = _field_sources(parsed)
    out: dict[str, Any] = {}
    for key in CONFIRMED_SCALAR_FIELDS:
        value = _first_present(sources, key)
        if value is None:
            continue
        if key in _ID_SCALAR_FIELDS:
            coerced = _as_id_str(value)
            if coerced is not None:
                out[key] = coerced
            continue
        if key == "event_type" and isinstance(value, str) and value.strip():
            out[key] = value.strip()
            continue
        if key == "is_test_mode":
            out[key] = value
            continue
        out[key] = value
    action_out = _allowlist_object(_nested_object(sources, "action"), CONFIRMED_ACTION_FIELDS)
    if action_out:
        out["action"] = action_out
    plan_out = _allowlist_object(
        _nested_object(sources, "plan"),
        CONFIRMED_PLAN_FIELDS,
        id_keys=("id",),
    )
    if plan_out:
        out["plan"] = plan_out
    features_out = _allowlist_object(
        _nested_object(sources, "features"),
        CONFIRMED_FEATURES_FIELDS,
    )
    if features_out:
        out["features"] = features_out
        if "is_test_mode" not in out and "is_test_mode" in features_out:
            out["is_test_mode"] = features_out["is_test_mode"]
    return out


def idempotency_for_payload(raw_body: bytes, parsed: Any) -> tuple[str, str, Optional[str]]:
    """Return (provider_event_id, idempotency_source, event_type).

    event_id is a confirmed PayKings unique event identifier.
    SHA-256 of the raw body is only a fallback if event_id is absent.
    """
    extracted = extract_confirmed_fields(parsed)
    event_type = extracted.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        event_type = None
    event_id = extracted.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id, "event_id", event_type
    digest = hashlib.sha256(raw_body).hexdigest()
    return f"sha256:{digest}", "payload_sha256_fallback", event_type


def _safe_event_log(extracted: dict[str, Any], status: str) -> None:
    action = extracted.get("action") if isinstance(extracted.get("action"), dict) else {}
    plan = extracted.get("plan") if isinstance(extracted.get("plan"), dict) else {}
    logger.info(
        "paykings webhook %s type=%s event_id=%s transaction_id=%s customerid=%s "
        "subscription_id=%s plan.id=%s order_id=%s condition=%s action.success=%s",
        status,
        extracted.get("event_type") or "unknown",
        extracted.get("event_id") or "n/a",
        extracted.get("transaction_id") or "n/a",
        extracted.get("customerid") or "n/a",
        extracted.get("subscription_id") or "n/a",
        plan.get("id") if plan else "n/a",
        extracted.get("order_id") or "n/a",
        extracted.get("condition") or "n/a",
        action.get("success") if action else "n/a",
    )


def handle_transaction_success(payload: dict) -> str:
    """payload is the sanitized operational extract only."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_transaction_failure(payload: dict) -> str:
    """payload is the sanitized operational extract only."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_transaction_unknown(payload: dict) -> str:
    """Record transaction.sale.unknown. Does not change access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_transaction_refund_success(payload: dict) -> str:
    """Record transaction.refund.success. Does not refund, cancel, or revoke access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_transaction_refund_failure(payload: dict) -> str:
    """Record transaction.refund.failure. Does not issue another refund or change access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_recurring_created(payload: dict) -> str:
    """Record recurring.subscription.add. Does not grant access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_recurring_updated(payload: dict) -> str:
    """Record recurring.subscription.update. Does not change access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_recurring_canceled(payload: dict) -> str:
    """Record recurring.subscription.delete. Does not deactivate a user."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_chargeback(payload: dict) -> str:
    """Reserved until PayKings/NMI chargeback event_type strings are confirmed."""
    payload.setdefault("event_type", "chargeback")
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_card_updater(payload: dict) -> str:
    """Legacy alias. Prefer the explicit acu.summary.* handlers."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_acu_automatically_updated(payload: dict) -> str:
    """Record acu.summary.automaticallyupdated. Does not change access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_acu_contact_customer(payload: dict) -> str:
    """Record acu.summary.contactcustomer. Does not change access."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_acu_closed_account(payload: dict) -> str:
    """Record acu.summary.closedaccount. Does not change access or cancel a subscription."""
    _safe_event_log(payload, "recorded")
    return "recorded"


def handle_unmapped(event_type: Optional[str], payload: dict) -> str:
    if event_type:
        payload["event_type"] = event_type
    _safe_event_log(payload, "unmapped")
    return "unmapped"


_RECORD_ONLY_HANDLER_NAMES = {
    EVENT_TRANSACTION_SUCCESS: "handle_transaction_success",
    EVENT_TRANSACTION_FAILURE: "handle_transaction_failure",
    EVENT_TRANSACTION_UNKNOWN: "handle_transaction_unknown",
    EVENT_TRANSACTION_REFUND_SUCCESS: "handle_transaction_refund_success",
    EVENT_TRANSACTION_REFUND_FAILURE: "handle_transaction_refund_failure",
    EVENT_RECURRING_CREATED: "handle_recurring_created",
    EVENT_RECURRING_UPDATED: "handle_recurring_updated",
    EVENT_RECURRING_CANCELED: "handle_recurring_canceled",
    EVENT_ACU_AUTOMATICALLY_UPDATED: "handle_acu_automatically_updated",
    EVENT_ACU_CONTACT_CUSTOMER: "handle_acu_contact_customer",
    EVENT_ACU_CLOSED_ACCOUNT: "handle_acu_closed_account",
}


def dispatch_event(event_type: Optional[str], payload: dict) -> str:
    """Route subscribed event types with a sanitized operational payload.

    Does not change User.is_pro, Subscription rows, or active_subscription_id.
    Refund and ACU events are record-only and never bind a user.
    """
    operational = operational_payload(payload)
    name = _RECORD_ONLY_HANDLER_NAMES.get(event_type)
    if name:
        return globals()[name](operational)
    return handle_unmapped(event_type, operational)
