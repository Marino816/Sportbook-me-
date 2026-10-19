"""PayKings/NMI recurring query and delete_subscription.

Official POST URL:
    https://paykings.transactiongateway.com/api/transact.php
    https://paykings.transactiongateway.com/api/query.php

Delete subscription (NMI Payment API):
    recurring=delete_subscription
    subscription_id=<id>

Never log security_key. Never store or log PAN/CVV.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

TRANSACT_URL = "https://paykings.transactiongateway.com/api/transact.php"
QUERY_URL = "https://paykings.transactiongateway.com/api/query.php"
RECURRING_DELETE_SUBSCRIPTION = "delete_subscription"
DEFAULT_TIMEOUT = 15
REDACTED_FIELDS = frozenset({"security_key", "payment_token", "cc_number", "cc_hash"})


class PayKingsNotConfigured(RuntimeError):
    """PAYKINGS_SECURITY_KEY is missing."""


class PayKingsProviderError(RuntimeError):
    """Gateway returned a declined/error response or HTTP failure."""

    def __init__(self, message: str, parsed: Optional["PayKingsTransactResponse"] = None):
        super().__init__(message)
        self.parsed = parsed


@dataclass(frozen=True)
class PayKingsTransactResponse:
    raw: str
    response: Optional[str] = None
    responsetext: Optional[str] = None
    transactionid: Optional[str] = None
    response_code: Optional[str] = None
    subscription_id: Optional[str] = None

    @property
    def approved(self) -> bool:
        return self.response == "1"


@dataclass(frozen=True)
class PayKingsRecurringSnapshot:
    subscription_id: str
    plan_id: Optional[str] = None
    plan_amount: Optional[str] = None
    next_charge_date: Optional[str] = None
    remaining_payments: Optional[str] = None


def security_key() -> Optional[str]:
    key = os.getenv("PAYKINGS_SECURITY_KEY", "").strip()
    return key or None


def parse_transact_response(body: str) -> PayKingsTransactResponse:
    parsed = parse_qs(body or "", keep_blank_values=True)
    fields = {}
    for key in ("response", "responsetext", "transactionid", "response_code", "subscription_id"):
        values = parsed.get(key)
        if values:
            fields[key] = values[0]
    return PayKingsTransactResponse(raw=body, **fields)


def parse_recurring_snapshots(xml_body: str) -> list[PayKingsRecurringSnapshot]:
    text = (xml_body or "").strip()
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        logger.warning("paykings recurring query xml parse failed")
        return []
    snapshots: list[PayKingsRecurringSnapshot] = []
    for node in root.findall("subscription"):
        sub_id = (node.findtext("subscription_id") or node.get("id") or "").strip()
        if not sub_id:
            continue
        plan = node.find("plan")
        snapshots.append(
            PayKingsRecurringSnapshot(
                subscription_id=sub_id,
                plan_id=(plan.findtext("plan_id") if plan is not None else None) or None,
                plan_amount=(plan.findtext("plan_amount") if plan is not None else None) or None,
                next_charge_date=node.findtext("next_charge_date") or None,
                remaining_payments=node.findtext("remaining_payments") or None,
            )
        )
    return snapshots


def build_delete_subscription_fields(*, subscription_id: str, key: str) -> dict[str, str]:
    return {
        "security_key": key,
        "recurring": RECURRING_DELETE_SUBSCRIPTION,
        "subscription_id": subscription_id,
    }


class PayKingsRecurringClient:
    def __init__(
        self,
        *,
        key: Optional[str] = None,
        transact_url: str = TRANSACT_URL,
        query_url: str = QUERY_URL,
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.key = key if key is not None else security_key()
        self.transact_url = transact_url
        self.query_url = query_url
        self.transport = transport
        self.timeout = timeout

    def _require_key(self) -> str:
        if not self.key:
            raise PayKingsNotConfigured("PAYKINGS_SECURITY_KEY is not configured")
        return self.key

    async def _post(self, url: str, fields: dict[str, str], *, kind: str) -> str:
        self._require_key()
        logger.info(
            "paykings %s kind=%s subscription_id=%s",
            url.split("/")[-1],
            kind,
            fields.get("subscription_id"),
        )
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            res = await client.post(url, data=fields)
        if res.status_code >= 400:
            raise PayKingsProviderError("paykings_http_error")
        return res.text

    async def query_subscription(self, subscription_id: str) -> Optional[PayKingsRecurringSnapshot]:
        sub_id = (subscription_id or "").strip()
        if not sub_id:
            raise ValueError("subscription_id_required")
        body = await self._post(
            self.query_url,
            {
                "security_key": self._require_key(),
                "report_type": "recurring",
                "subscription_id": sub_id,
            },
            kind="query_subscription",
        )
        snapshots = parse_recurring_snapshots(body)
        for row in snapshots:
            if row.subscription_id == sub_id:
                return row
        return snapshots[0] if snapshots else None

    async def delete_subscription(self, subscription_id: str) -> PayKingsTransactResponse:
        sub_id = (subscription_id or "").strip()
        if not sub_id:
            raise ValueError("subscription_id_required")
        existing = await self.query_subscription(sub_id)
        if existing is None:
            logger.info("paykings subscription already absent subscription_id=%s", sub_id)
            return PayKingsTransactResponse(
                raw="response=1&responsetext=Subscription already deleted&response_code=100&subscription_id=" + sub_id,
                response="1",
                responsetext="Subscription already deleted",
                response_code="100",
                subscription_id=sub_id,
            )
        fields = build_delete_subscription_fields(subscription_id=sub_id, key=self._require_key())
        body = await self._post(self.transact_url, fields, kind="delete_subscription")
        parsed = parse_transact_response(body)
        if not parsed.approved:
            logger.info(
                "paykings delete_subscription not approved response=%s response_code=%s",
                parsed.response,
                parsed.response_code,
            )
            raise PayKingsProviderError("paykings_not_approved", parsed)
        remaining = await self.query_subscription(sub_id)
        if remaining is not None:
            logger.warning("paykings delete_subscription approved but subscription still present")
            raise PayKingsProviderError("paykings_still_active", parsed)
        logger.info(
            "paykings delete_subscription approved subscription_id=%s response_code=%s",
            parsed.subscription_id or sub_id,
            parsed.response_code,
        )
        return parsed
