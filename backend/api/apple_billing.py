"""Authenticated Apple IAP billing endpoints.

GET /api/billing/apple/account-token
    Returns the stable StoreKit appAccountToken UUID for the JWT user.
    Creates the binding once. Never returns users.id.

    200 data: { "appAccountToken": "<uuid>" }

POST /api/billing/apple/verify
    Body: { "signedTransaction": "<jws>" }
    or    { "signedTransactions": ["<jws>", ...] }  # restore / multiple
    Extra client fields (environment, is_test_mode, sandbox) are ignored.

    Verifies Apple JWS, binds appAccountToken to the authenticated user,
    upserts a BillingEntitlement only after grant rules pass, then
    reconcile_user_access().

    200 data: { "granted": true, "tier": "pro"|"elite", "status": "active",
                "environment": "Production"|"Sandbox", "provider": "apple" }
    400 detail: missing_signed_transaction | wrong_bundle_id | unknown_product |
                wrong_app_account_binding | expired | revoked | invalid_signature | ...
    401: missing/invalid JWT
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.utils import wrap_data
from models.database import get_db
from models.domain import User
from services.apple_account_token import get_or_create_apple_account_token
from services.apple_environment import apple_environment_from_flag, apple_client_access_override
from services.apple_verify import AppleVerificationError, apple_grant_decision, verify_signed_transaction
from services.apple_writer import upsert_verified_apple_entitlement
from services.entitlements import effective_access_for_user

router = APIRouter()


class AppleVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    signedTransaction: Optional[str] = None
    signedTransactions: Optional[list[str]] = Field(default=None)


def _collect_signed_transactions(body: AppleVerifyRequest) -> list[str]:
    collected: list[str] = []
    if body.signedTransaction and isinstance(body.signedTransaction, str):
        collected.append(body.signedTransaction.strip())
    if body.signedTransactions:
        for item in body.signedTransactions:
            if isinstance(item, str) and item.strip():
                collected.append(item.strip())
    # Restore may repeat the same originalTransactionId; keep order, drop empties.
    return [item for item in collected if item]


@router.get("/apple/account-token")
async def apple_account_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await get_or_create_apple_account_token(db, user)
    await db.commit()
    return wrap_data({"appAccountToken": token})


@router.post("/apple/verify")
async def apple_verify(
    body: AppleVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    apple_client_access_override(
        environment=getattr(body, "environment", None),
        is_test_mode=getattr(body, "is_test_mode", None),
        sandbox=getattr(body, "sandbox", None),
    )
    signed_items = _collect_signed_transactions(body)
    if not signed_items:
        raise HTTPException(status_code=400, detail="missing_signed_transaction")
    bound_token = await get_or_create_apple_account_token(db, user)
    last_reason = "invalid_signature"
    applied = None
    for signed in signed_items:
        try:
            verified = verify_signed_transaction(signed)
        except AppleVerificationError as exc:
            last_reason = exc.reason
            continue
        decision = apple_grant_decision(verified, bound_account_token=bound_token)
        if not decision.allowed:
            last_reason = decision.reason
            continue
        row, result = await upsert_verified_apple_entitlement(
            db, user, verified, decision,
        )
        last_reason = result
        if result == "applied":
            applied = row
    if applied is None:
        raise HTTPException(status_code=400, detail=last_reason)
    await db.commit()
    access = await effective_access_for_user(db, user)
    return wrap_data({
        "granted": True,
        "tier": access.tier,
        "status": access.status,
        "environment": apple_environment_from_flag(bool(applied.is_test_mode)),
        "provider": access.provider,
        "productId": applied.provider_plan_id,
        "originalTransactionId": applied.provider_subscription_id,
    })
