"""App Store Server Notifications V2 receiver.

POST /api/webhooks/apple

Request: { "signedPayload": "<jws>" }
Unsigned JSON, missing signedPayload, and invalid JWS are rejected.
Does not grant from client-supplied environment flags.

200 { "status": "accepted", "decision": "applied"|"duplicate"|... }
400 missing_signed_payload | invalid_json | invalid_signature | ...
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from services.apple_notifications import handle_signed_notification
from services.apple_verify import AppleVerificationError

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/apple")
async def apple_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="missing_signed_payload")
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid_json")
    signed_payload = payload.get("signedPayload") if isinstance(payload, dict) else None
    if not signed_payload or not isinstance(signed_payload, str):
        raise HTTPException(status_code=400, detail="missing_signed_payload")
    try:
        result = await handle_signed_notification(db, signed_payload)
        await db.commit()
    except AppleVerificationError as exc:
        status = 503 if exc.reason in {
            "apple_root_certificates_not_configured",
            "retryable_verification_failure",
        } else 400
        raise HTTPException(status_code=status, detail=exc.reason) from exc
    return {
        "status": "accepted",
        "decision": result.decision,
        "notificationUUID": result.notification_uuid,
        "notificationType": result.notification_type,
    }
