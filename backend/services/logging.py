"""
Production structured logging middleware for Sportsbook Me DFS AI.

Provides request IDs, latency tracking, and safe structured logging.
Never logs: passwords, tokens, secrets, Stripe keys, or PII.
"""

import os
import time
import uuid
import logging
import json
from datetime import datetime, timezone
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REDACTED_FIELDS = {
    "password", "hashed_password", "token", "jwt", "secret",
    "api_key", "stripe", "authorization", "cookie", "credit_card",
    "webhook-signature", "paykings", "signing_key", "payment_token", "security_key",
}


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Injects request_id and logs every request with latency and status.

    Redacts sensitive fields from query params and headers before logging.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.time()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            logging.error(
                json.dumps({
                    "event": "unhandled_exception",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "exc": type(exc).__name__,
                    "duration_ms": round(duration_ms, 1),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            )
            raise

        duration_ms = (time.time() - start) * 1000
        logging.info(
            json.dumps({
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        )

        response.headers["X-Request-ID"] = request_id
        return response


def configure_structured_logging():
    """Set up JSON-formatted structured logging for production."""
    level = logging.INFO if os.getenv("NODE_ENV") == "production" else logging.DEBUG
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler], force=True)


def safe_log(msg: str, **kwargs):
    """Log a message with redacted sensitive fields."""
    safe_kwargs = {k: v for k, v in kwargs.items() if k not in REDACTED_FIELDS}
    logging.info(json.dumps({"event": msg, **safe_kwargs}))