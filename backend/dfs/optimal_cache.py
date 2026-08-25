"""
Optimal% simulation result storage + cache (Redis-backed).

Keys are versioned by platform + sport + slate_id + inputs_hash so:
  - cached results are reused while inputs are unchanged
  - different slates/platforms never share results
  - material input changes (salary/position/projection) invalidate

Status lifecycle: NOT_RUN → QUEUED → RUNNING → COMPLETE / FAILED.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Redis key namespaces
OPT_STATUS_KEY = "opt_sim:status:{platform}:{sport}:{slate_id}"
OPT_RESULT_KEY = "opt_sim:result:{platform}:{sport}:{slate_id}"
OPT_CACHE_TTL = 6 * 3600  # 6 hours

STATUS_NOT_RUN = "NOT_RUN"
STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETE = "COMPLETE"
STATUS_FAILED = "FAILED"


def _redis():
    from providers.redis_client import get_redis_client
    return get_redis_client()


def _status_key(platform: str, sport: str, slate_id: int) -> str:
    return OPT_STATUS_KEY.format(platform=platform, sport=sport, slate_id=slate_id)


def _result_key(platform: str, sport: str, slate_id: int) -> str:
    return OPT_RESULT_KEY.format(platform=platform, sport=sport, slate_id=slate_id)


def get_status(platform: str, sport: str, slate_id: int) -> str:
    """Return current simulation status (NOT_RUN if never started)."""
    r = _redis()
    if r is None:
        return STATUS_NOT_RUN
    try:
        raw = r.get(_status_key(platform, sport, slate_id))
        return raw.decode() if raw else STATUS_NOT_RUN
    except Exception as e:
        logger.warning(f"opt_sim get_status error: {e}")
        return STATUS_NOT_RUN


def set_status(platform: str, sport: str, slate_id: int, status: str) -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.set(_status_key(platform, sport, slate_id), status, ex=OPT_CACHE_TTL)
    except Exception as e:
        logger.warning(f"opt_sim set_status error: {e}")


def get_result(platform: str, sport: str, slate_id: int, expected_hash: Optional[str] = None) -> Optional[dict]:
    """Return cached result if it matches expected_hash (or any hash if None)."""
    r = _redis()
    if r is None:
        return None
    try:
        raw = r.get(_result_key(platform, sport, slate_id))
        if not raw:
            return None
        data = json.loads(raw.decode())
        if expected_hash and data.get("inputs_hash") != expected_hash:
            # Stale — inputs changed since this was cached
            return None
        return data
    except Exception as e:
        logger.warning(f"opt_sim get_result error: {e}")
        return None


def set_result(platform: str, sport: str, slate_id: int, data: dict) -> None:
    """Store a completed simulation result."""
    r = _redis()
    if r is None:
        return
    try:
        r.set(_result_key(platform, sport, slate_id), json.dumps(data), ex=OPT_CACHE_TTL)
    except Exception as e:
        logger.warning(f"opt_sim set_result error: {e}")


def clear(platform: str, sport: str, slate_id: int) -> None:
    """Clear both status and result for a slate."""
    r = _redis()
    if r is None:
        return
    try:
        r.delete(_status_key(platform, sport, slate_id), _result_key(platform, sport, slate_id))
    except Exception as e:
        logger.warning(f"opt_sim clear error: {e}")
