"""
Optimal% slate lock-time eligibility — single canonical gate.

DFSSlate.start_time is authoritative.  It is stored as a timezone-aware
UTC DateTime (bcdfs_adapter computes it from the slate name's Eastern time
hint and stores it as UTC).  This module treats that field as the
canonical lock time — no separate lock_time or first_game column exists.

Rules:
  UNLOCKED  — now < start_time (generation + serving ALLOWED)
  PRE_LOCK  — now within 30 min of start_time (generation prioritised)
  LOCKED    — now >= start_time (generation BLOCKED, serving BLOCKED)
  EXPIRED   — start_time is more than 24h in the past

At exactly now == start_time → LOCKED (tie goes to locked).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


PRE_LOCK_WINDOW = timedelta(minutes=30)
EXPIRED_WINDOW = timedelta(hours=24)


class LockStatus(str, Enum):
    UNLOCKED = "UNLOCKED"
    PRE_LOCK = "PRE_LOCK"
    LOCKED = "LOCKED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"  # missing start_time


def is_slate_locked(start_time: Optional[datetime]) -> bool:
    """True if the slate has locked (now >= start_time). Missing start_time = locked."""
    if start_time is None:
        return True  # can't prove it's unlocked → treat as locked
    now = datetime.now(timezone.utc)
    st = _ensure_utc(start_time)
    return now >= st


def slate_lock_status(start_time: Optional[datetime]) -> LockStatus:
    """Return the lock status of a slate given its start_time."""
    if start_time is None:
        return LockStatus.UNKNOWN
    now = datetime.now(timezone.utc)
    st = _ensure_utc(start_time)
    if now < st:
        if (st - now) <= PRE_LOCK_WINDOW:
            return LockStatus.PRE_LOCK
        return LockStatus.UNLOCKED
    # now >= st → locked
    if (now - st) > EXPIRED_WINDOW:
        return LockStatus.EXPIRED
    return LockStatus.LOCKED


def _ensure_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC, assuming Eastern if naive."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    # Naive datetime — assume US Eastern (BC's convention in parse_slate_time)
    from zoneinfo import ZoneInfo
    eastern = dt.replace(tzinfo=ZoneInfo("America/New_York"))
    return eastern.astimezone(timezone.utc)