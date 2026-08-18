"""
Canonical DFS slate freshness — single source of truth for date gating.

Uses Eastern time (US) as the DFS contest day boundary.  All date
comparisons are against "now" in America/New_York so that a slate that
starts at 10:10 PM ET on Monday is correctly classified as Monday (not
Tuesday UTC).

CURRENT  — slate date is today (ET)
UPCOMING — slate date is in the future
STALE    — slate date is in the past (or unknown)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional


def _today_et() -> date:
    """Today's calendar date in US Eastern time."""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/New_York")).date()


def slate_date_et(start_time: Optional[datetime]) -> Optional[date]:
    """Calendar date of *start_time* in US Eastern time, or None."""
    if start_time is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        return start_time.astimezone(ZoneInfo("America/New_York")).date()
    except Exception:
        return None


def slate_freshness(start_time: Optional[datetime]) -> str:
    """Return CURRENT / UPCOMING / STALE for a DFS slate.

    A slate whose *start_time* is missing or unparseable is treated as
    STALE (it cannot be proven current).
    """
    sd = slate_date_et(start_time)
    if sd is None:
        return "STALE"
    delta = (sd - _today_et()).days
    if delta == 0:
        return "CURRENT"
    if delta > 0:
        return "UPCOMING"
    return "STALE"


def is_stale_slate(start_time: Optional[datetime]) -> bool:
    """True when a DFS slate date is in the past (or unknown)."""
    return slate_freshness(start_time) == "STALE"


def is_current_slate(start_time: Optional[datetime]) -> bool:
    """True when the slate date equals today (Eastern time)."""
    return slate_freshness(start_time) == "CURRENT"