"""
Blue Collar DFS Automated Slate Scheduler — Phase 2.

Sport-aware, rate-budgeted polling that keeps current DFS slates available
without admin intervention.  Built on top of the existing bcdfs_adapter.

DOES NOT:
  - Copy BC projections into projected_fp
  - Replace the manual CSV importer
  - Expose BCDFS_API_KEY or raw BC JSON
  - Activate itself — the caller decides when to run ticks
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from dfs.bcdfs_adapter import (
    ENDPOINTS,
    BcRateLimiter,
    fetch_bc_endpoint,
    parse_bc_response,
    sync_bc_to_db,
    BcSyncReport,
    BcApiError,
    BcRateLimitError,
    BcAuthError,
)

logger = logging.getLogger(__name__)

# =====================================================================
# Scheduler configuration
# =====================================================================

ACTIVE_INTERVAL     = 45 * 60       # 45 min — in-season sport
PRE_LOCK_INTERVAL   = 20 * 60       # 20 min — approaching first lock
OFFSEASON_INTERVAL  = 24 * 3600     # 24 hours — empty endpoints
POST_LOCK_INTERVAL  = 6 * 3600      # 6 hours — after all slates locked
LOCK_WINDOW_SECONDS = 2 * 3600      # 2 hours — pre-lock window
BACKOFF_BASE        = 60            # 1 minute
BACKOFF_MAX         = 3600          # 1 hour
SAFE_DAILY_LIMIT    = 150           # soft cap
HARD_DAILY_LIMIT    = 200           # documented cap


class EndpointState(Enum):
    ACTIVE   = "active"
    OFFSZN   = "offseason"
    PRE_LOCK = "pre_lock"
    POST_LOCK = "post_lock"
    ERROR    = "error"
    UNKNOWN  = "unknown"


@dataclass
class EndpointStatus:
    sport: str
    platform: str
    state: EndpointState = EndpointState.UNKNOWN
    last_sync: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    slate_count: int = 0
    player_count: int = 0
    backoff_until: Optional[datetime] = None
    consecutive_errors: int = 0
    next_poll: Optional[datetime] = None

    def interval_seconds(self) -> int:
        if self.backoff_until and datetime.now(timezone.utc) < self.backoff_until:
            return BACKOFF_BASE * (2 ** min(self.consecutive_errors, 5))
        if self.state == EndpointState.PRE_LOCK:
            return PRE_LOCK_INTERVAL
        if self.state == EndpointState.ACTIVE:
            return ACTIVE_INTERVAL
        if self.state == EndpointState.POST_LOCK:
            return POST_LOCK_INTERVAL
        if self.state == EndpointState.ERROR:
            return BACKOFF_BASE * (2 ** min(self.consecutive_errors, 5))
        return OFFSEASON_INTERVAL


@dataclass
class SchedulerState:
    rate_limiter: BcRateLimiter = field(default_factory=BcRateLimiter)
    endpoints: dict = field(default_factory=dict)
    last_tick: Optional[datetime] = None
    tick_count: int = 0
    active_sync_lock: bool = False

    def __post_init__(self):
        for (sport, platform) in ENDPOINTS:
            self.endpoints[(sport, platform)] = EndpointStatus(
                sport=sport, platform=platform,
            )

    def daily_requests_used(self) -> int:
        return sum(self.rate_limiter._counts.values()) if self.rate_limiter._counts else 0

    def daily_requests_remaining(self) -> int:
        return self.rate_limiter.remaining()

    def to_dict(self) -> dict:
        now = datetime.now(timezone.utc)
        eps = {}
        for key, status in self.endpoints.items():
            eps[f"{key[0]}_{key[1]}"] = {
                "state": status.state.value,
                "last_sync": status.last_sync.isoformat() if status.last_sync else None,
                "last_success": status.last_success.isoformat() if status.last_success else None,
                "last_error": status.last_error,
                "last_error_time": status.last_error_time.isoformat() if status.last_error_time else None,
                "slate_count": status.slate_count,
                "player_count": status.player_count,
                "backoff_until": status.backoff_until.isoformat() if status.backoff_until else None,
                "consecutive_errors": status.consecutive_errors,
                "next_poll": status.next_poll.isoformat() if status.next_poll else None,
            }
        return {
            "daily_requests_used": self.daily_requests_used(),
            "daily_requests_remaining": self.daily_requests_remaining(),
            "safe_daily_limit": SAFE_DAILY_LIMIT,
            "hard_daily_limit": HARD_DAILY_LIMIT,
            "last_tick": self.last_tick.isoformat() if self.last_tick else None,
            "tick_count": self.tick_count,
            "endpoints": eps,
        }


# Global singleton
_scheduler_state: Optional[SchedulerState] = None


def get_scheduler_state() -> SchedulerState:
    global _scheduler_state
    if _scheduler_state is None:
        _scheduler_state = SchedulerState()
    return _scheduler_state


# =====================================================================
# Slate activity detection
# =====================================================================

def _determine_state(parse_result, prev_state: EndpointState) -> EndpointState:
    if not parse_result.slates:
        return EndpointState.OFFSZN

    now = datetime.now(timezone.utc)
    earliest = None
    all_past = True

    for cs in parse_result.slates:
        if cs.start_time:
            if earliest is None or cs.start_time < earliest:
                earliest = cs.start_time
            if cs.start_time > now:
                all_past = False

    if earliest is None:
        return EndpointState.ACTIVE

    seconds_to_first = (earliest - now).total_seconds()
    if 0 < seconds_to_first < LOCK_WINDOW_SECONDS:
        return EndpointState.PRE_LOCK
    if all_past:
        return EndpointState.POST_LOCK
    return EndpointState.ACTIVE


# =====================================================================
# Per-endpoint sync
# =====================================================================

async def _sync_one_endpoint(
    db: AsyncSession,
    status: EndpointStatus,
) -> BcSyncReport:
    state = get_scheduler_state()
    now = datetime.now(timezone.utc)
    report = BcSyncReport(sport=status.sport, platform=status.platform)

    if status.backoff_until and now < status.backoff_until:
        report.warnings.append(f"Backoff until {status.backoff_until.isoformat()}")
        return report

    if not state.rate_limiter.can_request():
        report.errors.append("Daily budget exhausted")
        status.state = EndpointState.ERROR
        status.last_error = "Daily budget exhausted"
        status.last_error_time = now
        return report

    try:
        data = fetch_bc_endpoint(
            status.sport, status.platform, rate_limiter=state.rate_limiter,
        )
        parse_result = parse_bc_response(data, status.sport, status.platform)
        report = await sync_bc_to_db(db, parse_result, auto_publish=True)

        status.state = _determine_state(parse_result, status.state)
        status.last_sync = now
        status.last_success = now
        status.consecutive_errors = 0
        status.backoff_until = None
        status.slate_count = report.total_slates
        status.player_count = report.total_players
        status.last_error = None
        status.last_error_time = None

    except BcRateLimitError as e:
        status.state = EndpointState.ERROR
        status.last_error = f"429: {e.body[:120] if hasattr(e,'body') else str(e)}"
        status.last_error_time = now
        status.consecutive_errors += 1
        status.backoff_until = now + timedelta(seconds=BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)))
        report.errors.append(f"Rate limited: {e}")

    except BcAuthError as e:
        status.state = EndpointState.ERROR
        status.last_error = f"Auth error ({e.status})"
        status.last_error_time = now
        status.consecutive_errors += 1
        status.backoff_until = now + timedelta(hours=6)
        report.errors.append(f"Auth: {e}")

    except BcApiError as e:
        if status.state != EndpointState.OFFSZN:
            status.state = EndpointState.ERROR
        status.last_error = f"{e.status}: {e.body[:120] if hasattr(e,'body') else str(e)}"
        status.last_error_time = now
        status.consecutive_errors += 1
        status.backoff_until = now + timedelta(seconds=BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)))
        report.errors.append(str(e))

    except Exception as e:
        if status.state != EndpointState.OFFSZN:
            status.state = EndpointState.ERROR
        status.last_error = str(e)[:200]
        status.last_error_time = now
        status.consecutive_errors += 1
        status.backoff_until = now + timedelta(seconds=BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)))
        report.errors.append(str(e))

    status.next_poll = now + timedelta(seconds=status.interval_seconds())
    return report


# =====================================================================
# Scheduler tick
# =====================================================================

async def scheduler_tick(
    db: AsyncSession,
    force_sports: Optional[list] = None,
) -> dict:
    state = get_scheduler_state()
    now = datetime.now(timezone.utc)

    if state.active_sync_lock and force_sports is None:
        return {"status": "skipped", "reason": "sync already in progress"}

    state.active_sync_lock = True
    state.last_tick = now
    state.tick_count += 1

    try:
        if force_sports is not None:
            targets = [(s.upper(), p.lower()) for s, p in force_sports]
        else:
            targets = [
                (sport, platform)
                for (sport, platform), status in state.endpoints.items()
                if status.next_poll is None or now >= status.next_poll
            ]

        reports: dict = {}
        for sport, platform in targets:
            key = f"{sport}_{platform}"
            status = state.endpoints.get((sport, platform))
            if status is None:
                reports[key] = {"error": "Unknown endpoint"}
                continue
            report = await _sync_one_endpoint(db, status)
            reports[key] = {
                "slates_created": report.slates_created,
                "slates_updated": report.slates_updated,
                "players_added": report.players_added,
                "players_updated": report.players_updated,
                "players_removed": report.players_removed,
                "state": status.state.value,
                "next_poll": status.next_poll.isoformat() if status.next_poll else None,
                "errors": report.errors,
                "warnings": report.warnings,
            }
            if len(targets) > 1:
                await asyncio.sleep(1)

        return {
            "status": "ok",
            "tick": state.tick_count,
            "synced": len(reports),
            "daily_requests_used": state.daily_requests_used(),
            "daily_requests_remaining": state.daily_requests_remaining(),
            "endpoints": reports,
        }
    finally:
        state.active_sync_lock = False


async def admin_refresh(db: AsyncSession, sport: str, platform: str) -> dict:
    return await scheduler_tick(db, force_sports=[(sport, platform)])


def get_operational_status() -> dict:
    return get_scheduler_state().to_dict()
