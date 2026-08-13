"""Shared Redis client for backend services."""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client: Optional["Redis"] = None  # type: ignore[name-defined]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_client():
    """Lazy-init a shared Redis connection pool, usable sync and async."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        import redis
        _redis_client = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=3,
            socket_timeout=5,
            decode_responses=False,
        )
        _redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis unavailable, falling back to in-memory cache: {e}")
        _redis_client = None

    return _redis_client


def redis_available() -> bool:
    """Check if Redis is reachable."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False