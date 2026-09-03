"""PayKings webhook HTTP receiver.

Public URL: POST /api/webhooks/paykings

HMAC_SHA256(signing_key, nonce + "." + raw_body) verified on the exact
raw request body before JSON parsing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import PaymentWebhookEvent
from services.paykings_billing import apply_recurring_webhook
from services.paykings_webhooks import (
    PROVIDER,
    dispatch_event,
    extract_confirmed_fields,
    idempotency_for_payload,
    parse_json_body,
    verify_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/paykings")
async def paykings_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    webhook_signature: str | None = Header(None, alias="Webhook-Signature"),
):
    """Accept PayKings HTTPS webhook deliveries.

    Signature header: Webhook-Signature: t=<nonce>,s=<signature>
    """
    raw_body = await request.body()
    ok, reason = verify_request(raw_body, webhook_signature)
    if not ok:
        if reason == "not_configured":
            logger.error("paykings webhook rejected: signing key not configured")
            raise HTTPException(status_code=503, detail="Webhook not configured")
        logger.warning("paykings webhook rejected: %s", reason)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        parsed = parse_json_body(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id, id_source, event_type = idempotency_for_payload(raw_body, parsed)
    # Persist only confirmed PayKings fields (no PAN/CVV, no invented keys).
    sanitized = extract_confirmed_fields(parsed)

    existing = (
        await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == PROVIDER,
                PaymentWebhookEvent.provider_event_id == event_id,
            )
        )
    ).scalars().first()
    if existing:
        logger.info(
            "paykings webhook duplicate type=%s source=%s",
            event_type or "unknown",
            id_source,
        )
        return {"status": "duplicate"}

    row = PaymentWebhookEvent(
        provider=PROVIDER,
        provider_event_id=event_id,
        idempotency_source=id_source,
        event_type=event_type,
        processing_status="received",
        sanitized_payload=sanitized,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"status": "duplicate"}

    dispatch_event(event_type, sanitized)
    bind_status = await apply_recurring_webhook(db, event_type, sanitized)
    row.processing_status = bind_status if bind_status in ("processed", "unresolved", "error") else "processed"
    row.processed_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(
        "paykings webhook processed type=%s source=%s",
        event_type or "unknown",
        id_source,
    )
    return {"status": "success"}
