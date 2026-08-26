"""
Deterministic Optimal% input snapshot.

Captures the canonical player pool exactly once at queue time and stores
it in Redis as an immutable JSON snapshot.  The Celery worker reads the
snapshot rather than re-building from live SGO, guaranteeing that the
simulation's inputs_hash matches what was signed at enqueue time.

Key: opt_sim:snapshot:{platform}:{sport}:{slate_id}:{inputs_hash}
TTL: 6 hours (matches optimal_cache TTL)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SNAPSHOT_KEY = "opt_sim:snapshot:{platform}:{sport}:{slate_id}:{inputs_hash}"
SNAPSHOT_TTL = 6 * 3600  # 6 hours


def _redis():
    from providers.redis_client import get_redis_client
    return get_redis_client()


def _snapshot_key(platform: str, sport: str, slate_id: int, inputs_hash: str) -> str:
    return SNAPSHOT_KEY.format(
        platform=platform, sport=sport, slate_id=slate_id, inputs_hash=inputs_hash
    )


# ── Snapshot format ──────────────────────────────────────────────────

SNAPSHOT_FIELDS = [
    "id",           # canonical player ID (str)
    "name",         # display name
    "position",     # single position string (primary eligibility)
    "positions",    # list of eligible positions (multi-eligibility)
    "team",         # team abbreviation
    "opponent",     # opponent abbreviation (for correlation)
    "salary",       # int — DK salary
    "projected_fp", # float — SB ME projection (0.0 = unprojected)
    "projection_source",  # str — SGO_FANTASY_MARKET / PROP_BASED / UNAVAILABLE
]

# Fields explicitly excluded (cosmetic, non-material, or prohibited):
#   value — derivative of projected_fp/salary, not an input
#   ceiling, floor — model-derived from projected_fp, not independent inputs
#   ownership, leverage — separate metrics, not simulation inputs
#   bc_projection, beta_proj — prohibited Blue Collar data
#   any timestamp that would churn non-materially


def capture_snapshot(pool: list[dict]) -> list[dict]:
    """Extract material simulation inputs from a canonical pool.

    Only includes fields that affect simulation output.  Cosmetic data,
    derived values, and timestamps are excluded so minor non-material
    changes don't invalidate the cache.
    """
    snap = []
    for p in pool:
        entry = {}
        for field in SNAPSHOT_FIELDS:
            entry[field] = p.get(field)
        snap.append(entry)
    return snap


def store_snapshot(
    platform: str,
    sport: str,
    slate_id: int,
    inputs_hash: str,
    pool_snapshot: list[dict],
    metadata: Optional[dict] = None,
) -> bool:
    """Store an immutable input snapshot in Redis.

    Returns True on success, False on Redis failure.
    """
    r = _redis()
    if r is None:
        logger.warning("Snapshot store failed: Redis unavailable")
        return False
    key = _snapshot_key(platform, sport, slate_id, inputs_hash)
    payload = {
        "inputs_hash": inputs_hash,
        "platform": platform,
        "sport": sport,
        "slate_id": slate_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "player_count": len(pool_snapshot),
        "players": pool_snapshot,
        "metadata": metadata or {},
    }
    try:
        r.set(key, json.dumps(payload), ex=SNAPSHOT_TTL)
        logger.info(
            f"Snapshot stored: {sport}/{platform} slate {slate_id} "
            f"hash={inputs_hash} players={len(pool_snapshot)}"
        )
        return True
    except Exception as e:
        logger.warning(f"Snapshot store error: {e}")
        return False


def load_snapshot(
    platform: str, sport: str, slate_id: int, inputs_hash: str
) -> Optional[dict]:
    """Load a previously stored input snapshot.

    Returns the full snapshot payload (including 'players' list) or None.
    """
    r = _redis()
    if r is None:
        return None
    key = _snapshot_key(platform, sport, slate_id, inputs_hash)
    try:
        raw = r.get(key)
        if not raw:
            return None
        return json.loads(raw.decode())
    except Exception as e:
        logger.warning(f"Snapshot load error: {e}")
        return None


def snapshot_exists(
    platform: str, sport: str, slate_id: int, inputs_hash: str
) -> bool:
    """Check whether a snapshot exists for the given hash."""
    r = _redis()
    if r is None:
        return False
    key = _snapshot_key(platform, sport, slate_id, inputs_hash)
    try:
        return bool(r.exists(key))
    except Exception:
        return False