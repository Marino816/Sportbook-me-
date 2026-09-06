"""Apple IAP environment trust model.

Authoritative environment comes from Apple's VERIFIED signed transaction
or ASSN V2 notification — never NODE_ENV, never the client.

Apple Environment values (from verified JWS, Phase 2):
- Production
- Sandbox

Persistence (no new column):
- BillingEntitlement.is_test_mode = True  → Apple Environment.SANDBOX
- BillingEntitlement.is_test_mode = False → Apple Environment.PRODUCTION

Eligibility (after Phase 2 verification has set paid_verified):
- A verified Sandbox row may grant its bound account on ANY backend
  runtime, including NODE_ENV=production (TestFlight / App Review).
- A verified Production row may grant its bound account.
- NODE_ENV is not an Apple eligibility input.

Isolation:
- Sandbox and Production rows are distinct lifecycles.
- A Sandbox notification must never mutate a Production row.
- A Production notification must never mutate a Sandbox row.
- is_test_mode is never flipped after persist.

Identity for Phase 2 writers:
  (provider='apple', originalTransactionId, environment)
The DB unique constraint (provider, provider_subscription_id) does NOT
include environment. Apple does not document that originalTransactionId
is unique across Sandbox and Production. Phase 2 must look up by
identity-including-environment and must not upsert across environments.
See apple_subscription_identity().

Client query params, headers, or body flags (environment, is_test_mode,
allow_sandbox, sandbox) are ignored and never grant access.
"""

from __future__ import annotations

from typing import Any, Optional

APPLE_ENVIRONMENT_PRODUCTION = "Production"
APPLE_ENVIRONMENT_SANDBOX = "Sandbox"


def apple_environment_from_flag(is_test_mode: bool) -> str:
    return APPLE_ENVIRONMENT_SANDBOX if is_test_mode else APPLE_ENVIRONMENT_PRODUCTION


def apple_is_test_mode_from_environment(environment: str) -> bool:
    return (environment or "").strip().lower() == "sandbox"


def normalize_apple_environment(environment: str) -> Optional[str]:
    """Return Production/Sandbox from verified Apple data, or None if unknown."""
    value = (environment or "").strip().lower()
    if value == "sandbox":
        return APPLE_ENVIRONMENT_SANDBOX
    if value == "production":
        return APPLE_ENVIRONMENT_PRODUCTION
    return None


def apple_row_environment(row: Any) -> str:
    return apple_environment_from_flag(bool(getattr(row, "is_test_mode", False)))


def apple_subscription_identity(
    original_transaction_id: str,
    environment: str,
) -> tuple[str, str, str]:
    """Stable Apple subscription identity including environment.

    Phase 2 writers must use this, not (provider, originalTransactionId) alone.
    """
    env = normalize_apple_environment(environment) or ""
    return ("apple", original_transaction_id or "", env)


def apple_client_access_override(**claims: Any) -> bool:
    """Client cannot enable, disable, or choose Apple environment.

    Any combination of environment / is_test_mode / allow_sandbox / sandbox
    claims is discarded. Always returns False (does not grant).
    """
    _ = claims
    return False


def apple_sandbox_entitlements_allowed(*, client_requested: Any = None) -> bool:
    """Not an eligibility gate. Client flags never enable a special mode."""
    return apple_client_access_override(
        client_requested=client_requested,
        allow_sandbox=client_requested,
    )


def apple_lifecycle_may_mutate(
    row: Any,
    *,
    original_transaction_id: str,
    environment: str,
) -> str:
    """Whether a verified Apple lifecycle event may touch this row.

    Returns ``ok`` or a deny reason. Never treats NODE_ENV as input.
    """
    if getattr(row, "provider", None) != "apple":
        return "wrong_provider"
    stored_id = getattr(row, "provider_subscription_id", None) or ""
    if stored_id != (original_transaction_id or ""):
        return "identity_mismatch"
    incoming = normalize_apple_environment(environment)
    if incoming is None:
        return "unknown_environment"
    if apple_row_environment(row) != incoming:
        return "environment_mismatch"
    return "ok"


def apply_verified_apple_lifecycle(
    row: Any,
    *,
    original_transaction_id: str,
    environment: str,
    status: str,
) -> str:
    """Apply a verified lifecycle status only to the matching environment row.

    Never flips ``is_test_mode``. Never writes when environments differ.
    """
    reason = apple_lifecycle_may_mutate(
        row,
        original_transaction_id=original_transaction_id,
        environment=environment,
    )
    if reason != "ok":
        return reason
    row.status = status
    return "applied"


def select_apple_entitlement_for_lifecycle(
    rows: list[Any],
    *,
    original_transaction_id: str,
    environment: str,
) -> Any:
    """Return the same-environment Apple row, or None.

    Opposite-environment rows with the same originalTransactionId are ignored.
    """
    for row in rows:
        if apple_lifecycle_may_mutate(
            row,
            original_transaction_id=original_transaction_id,
            environment=environment,
        ) == "ok":
            return row
    return None
