"""PayKings Payment API client (transact.php).

Official POST URL (PayKings Integration Portal):
    https://paykings.transactiongateway.com/api/transact.php

Authentication (documented Transaction Variables):
    security_key = API Security Key (Settings > Security Keys)

Add subscription to an existing plan (documented):
    recurring=add_subscription
    plan_id=<existing plan>
    payment_token=<Collect.js single-use token>
    orderid=<merchant order id>

Response (documented): HTTP body is query-string name/value pairs, e.g.
    response=1&responsetext=Approved&transactionid=...&orderid=...
Standard fields: response, responsetext, authcode, transactionid,
avsresponse, cvvresponse, orderid, response_code.
Conditional: customer_vault_id.
subscription_id is NOT in the documented standard response; if PayKings
includes it we store it, otherwise the webhook is authoritative.

Never log security_key or payment_token.
Never send ccnumber, ccexp, CVV, checkaccount, or checkaba.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs

import httpx

logger = logging.getLogger(__name__)

TRANSACT_URL = "https://paykings.transactiongateway.com/api/transact.php"
RECURRING_ADD_SUBSCRIPTION = "add_subscription"
DEFAULT_TIMEOUT = 15

# Documented Payment API standard + conditional response fields only.
DOCUMENTED_RESPONSE_FIELDS = (
    "response",
    "responsetext",
    "authcode",
    "transactionid",
    "avsresponse",
    "cvvresponse",
    "orderid",
    "response_code",
    "customer_vault_id",
)


class PayKingsNotConfigured(RuntimeError):
    """PAYKINGS_SECURITY_KEY is missing; do not call transact.php."""


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
    authcode: Optional[str] = None
    transactionid: Optional[str] = None
    avsresponse: Optional[str] = None
    cvvresponse: Optional[str] = None
    orderid: Optional[str] = None
    response_code: Optional[str] = None
    customer_vault_id: Optional[str] = None
    subscription_id: Optional[str] = None  # only if gateway included it

    @property
    def approved(self) -> bool:
        return self.response == "1"


def security_key() -> Optional[str]:
    key = os.getenv("PAYKINGS_SECURITY_KEY", "").strip()
    return key or None


def parse_transact_response(body: str) -> PayKingsTransactResponse:
    """Parse documented query-string Payment API response."""
    parsed = parse_qs(body or "", keep_blank_values=True)
    fields = {}
    for key in DOCUMENTED_RESPONSE_FIELDS:
        values = parsed.get(key)
        if values:
            fields[key] = values[0]
    extra_sub = parsed.get("subscription_id")
    if extra_sub and extra_sub[0]:
        fields["subscription_id"] = extra_sub[0]
    return PayKingsTransactResponse(raw=body, **fields)


def build_add_subscription_fields(
    *,
    plan_id: str,
    payment_token: str,
    order_id: str,
    key: str,
) -> dict[str, str]:
    """Documented add_subscription fields. orderid is server-owned."""
    return {
        "security_key": key,
        "recurring": RECURRING_ADD_SUBSCRIPTION,
        "plan_id": plan_id,
        "payment_token": payment_token,
        "orderid": order_id,
    }


class PayKingsClient:
    """httpx client for PayKings transact.php. Credentials stay server-side."""

    def __init__(
        self,
        *,
        key: Optional[str] = None,
        transact_url: str = TRANSACT_URL,
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.key = key if key is not None else security_key()
        self.transact_url = transact_url
        self.transport = transport
        self.timeout = timeout

    async def create_subscription(
        self,
        *,
        plan_id: str,
        payment_token: str,
        order_id: str,
    ) -> PayKingsTransactResponse:
        if not self.key:
            raise PayKingsNotConfigured("PAYKINGS_SECURITY_KEY is not configured")
        token = (payment_token or "").strip()
        if not token:
            raise ValueError("payment_token_required")
        fields = build_add_subscription_fields(
            plan_id=plan_id,
            payment_token=token,
            order_id=order_id,
            key=self.key,
        )
        logger.info(
            "paykings transact.php add_subscription plan_id=%s orderid=%s",
            plan_id,
            order_id,
        )
        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            res = await client.post(self.transact_url, data=fields)
        parsed = parse_transact_response(res.text)
        if res.status_code >= 400:
            logger.warning(
                "paykings transact.php http_status=%s response=%s",
                res.status_code,
                parsed.response,
            )
            raise PayKingsProviderError("paykings_http_error", parsed)
        if not parsed.approved:
            logger.info(
                "paykings transact.php not approved response=%s response_code=%s",
                parsed.response,
                parsed.response_code,
            )
            raise PayKingsProviderError("paykings_not_approved", parsed)
        return parsed
