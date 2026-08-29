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


WEEKLY_SPORTS = frozenset({"NFL", "NCAAF"})


def is_weekly_sport(sport: Optional[str]) -> bool:
    return (sport or "").strip().upper() in WEEKLY_SPORTS


def is_customer_visible_slate(start_time: Optional[datetime], sport: Optional[str] = None) -> bool:
    """Whether a stored slate should appear in the customer optimizer.

    CURRENT slates are always visible (existing MLB/NBA daily behavior).
    UPCOMING slates are visible only for weekly sports (NFL / NCAAF) so
    weekend contests can be selected before game day.
    STALE slates are never visible.
    """
    freshness = slate_freshness(start_time)
    if freshness == "CURRENT":
        return True
    if freshness == "UPCOMING" and is_weekly_sport(sport):
        return True
    return False


def is_auto_publishable(start_time: Optional[datetime], sport: Optional[str] = None) -> bool:
    """Ingest may auto-publish CURRENT slates, plus UPCOMING weekly slates."""
    return is_customer_visible_slate(start_time, sport)


def is_runnable_slate(status: Optional[str], start_time: Optional[datetime], sport: Optional[str] = None) -> bool:
    """Whether a stored slate row may be loaded by optimizer or AI tools.

    PUBLISHED + not STALE: yes (including upcoming MLB that an admin published).
    DRAFT + weekly + UPCOMING: yes. Those rows exist because ingest previously
    refused to publish weekend NFL/NCAAF before game day.
    ARCHIVED / STALE: never.
    """
    st = (status or "").upper()
    if st == "ARCHIVED":
        return False
    if is_stale_slate(start_time):
        return False
    if st == "PUBLISHED":
        return True
    if st == "DRAFT" and is_weekly_sport(sport) and slate_freshness(start_time) == "UPCOMING":
        return True
    return False


# Back-compat alias used by older call sites.
def is_optimizer_eligible_status(status: Optional[str], start_time: Optional[datetime], sport: Optional[str] = None) -> bool:
    return is_runnable_slate(status, start_time, sport)


def is_ai_matchable_slate(status: Optional[str], start_time: Optional[datetime], sport: Optional[str] = None) -> bool:
    """Slates the assistant may bind in conversation.

    PUBLISHED slates match even if they already locked or the date is past so
    the assistant can report LOCKED/STALE honestly. DRAFT weekly upcoming
    slates match because ingest used to leave weekend NFL/NCAAF unpublished.
    """
    st = (status or "").upper()
    if st == "ARCHIVED":
        return False
    if st == "PUBLISHED":
        return True
    if st == "DRAFT" and is_weekly_sport(sport) and not is_stale_slate(start_time):
        return True
    return False