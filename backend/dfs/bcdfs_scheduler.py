"""
Blue Collar DFS Automated Slate Scheduler — Phase 2B hardened.

Redis-backed persistent rate accounting with separate automated (130/day)
and manual (20/day) budgets against the 150/day SB ME ceiling.  Atomic
INCR reservation prevents over-spend across concurrent workers.
Per-endpoint SETNX locks prevent duplicate concurrent syncs.

Scheduler host: in-process FastAPI lifespan loop when BCDFS_SCHEDULER_ENABLED
is true (tick interval BCDFS_TICK_INTERVAL, default 600s). Railway Cron is
an optional alternative. Tick frequency ≠ provider frequency: scheduler_tick()
checks each endpoint's due time; a wake-up may result in 0–8 provider calls.

DOES NOT:
  - Copy BC projections into projected_fp (fppg + bc_player_meta only)
  - Replace the manual CSV importer
  - Expose BCDFS_API_KEY or raw BC JSON
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from dfs.bcdfs_adapter import (
    ENDPOINTS,
    fetch_bc_endpoint,
    parse_bc_response,
    sync_bc_to_db,
    BcSyncReport,
    BcApiError,
    BcRateLimitError,
    BcAuthError,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# Configuration — hard budget guarantees
# ══════════════════════════════════════════════════════════════════════

PROVIDER_LIMIT      = 200   # Blue Collar documented limit
SB_ME_CEILING       = 150   # SB ME internal ceiling
MANUAL_RESERVE      = 20    # admin emergency reserve
AUTO_BUDGET         = 130   # maximum automated requests/day

# Polling intervals (seconds)
ACTIVE_INTERVAL     = 45 * 60       # 45 min — in-season
PRE_LOCK_INTERVAL   = 20 * 60       # 20 min — approaching lock
OFFSEASON_INTERVAL  = 24 * 3600     # 24 hours — empty endpoints
POST_LOCK_INTERVAL  = 6 * 3600      # 6 hours — all locked
LOCK_WINDOW_SECONDS = 2 * 3600      # 2 hours

# Backoff (seconds)
BACKOFF_BASE        = 60
BACKOFF_MAX_SEC     = 3600
AUTH_BACKOFF_SEC    = 6 * 3600      # 401/403 — 6 hours

# Distributed lock TTL
LOCK_TTL            = 120            # 2 min — max duration of one sync

# Priority values for endpoint ordering
PRIORITY_PRE_LOCK   = 0
PRIORITY_ACTIVE     = 1
PRIORITY_POST_LOCK  = 2
PRIORITY_OFFSZN     = 3
PRIORITY_ERROR      = 4
PRIORITY_UNKNOWN    = 5


class EndpointState(Enum):
    ACTIVE   = "active"
    OFFSZN   = "offseason"
    PRE_LOCK = "pre_lock"
    POST_LOCK = "post_lock"
    ERROR    = "error"
    SUSPENDED = "suspended"   # 401/403 — requires admin intervention
    UNKNOWN  = "unknown"


PRIORITY_MAP = {
    EndpointState.PRE_LOCK:  PRIORITY_PRE_LOCK,
    EndpointState.ACTIVE:    PRIORITY_ACTIVE,
    EndpointState.POST_LOCK: PRIORITY_POST_LOCK,
    EndpointState.OFFSZN:    PRIORITY_OFFSZN,
    EndpointState.ERROR:     PRIORITY_ERROR,
    EndpointState.UNKNOWN:   PRIORITY_UNKNOWN,
    EndpointState.SUSPENDED: PRIORITY_ERROR,  # below everything except unknown
}


# ══════════════════════════════════════════════════════════════════════
# Redis helpers — persistence, atomic ops, distributed locks
# ══════════════════════════════════════════════════════════════════════

def _redis():
    """Lazy Redis client — never fails (returns None if unavailable)."""
    from providers.redis_client import get_redis_client
    return get_redis_client()


def _today_key(suffix: str) -> str:
    """Key with today's UTC date: bcdfs:{suffix}:2026-08-24"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"bcdfs:{suffix}:{today}"


def _get_counter(key: str) -> int:
    """Read a Redis counter, returning 0 if missing."""
    r = _redis()
    if r is None:
        return 0
    try:
        val = r.get(key)
        return int(val) if val else 0
    except Exception:
        return 0


def _try_reserve_budget(budget_type: str, limit: int) -> bool:
    """Atomically reserve one request from a budget bucket.

    Uses Redis INCR + check pattern.  If the incremented count
    exceeds *limit*, DECR to roll back and return False.
    Otherwise return True — the request is reserved.

    budget_type: 'auto' or 'manual'
    """
    r = _redis()
    if r is None:
        return False  # no Redis = no reservation = no request
    key = _today_key(f"budget:{budget_type}")
    try:
        count = r.incr(key)
        if count > limit:
            r.decr(key)
            return False
        # Set TTL so keys auto-expire after 48h (cleanup)
        r.expire(key, 172800)
        return True
    except Exception:
        return False


def _release_budget(budget_type: str) -> None:
    """Release a reserved request on error (best-effort rollback)."""
    r = _redis()
    if r is None:
        return
    key = _today_key(f"budget:{budget_type}")
    try:
        r.decr(key)
    except Exception:
        pass


def _budget_remaining(budget_type: str, limit: int) -> int:
    """How many requests remain in a budget bucket."""
    return max(0, limit - _get_counter(_today_key(f"budget:{budget_type}")))


def _acquire_sync_lock(sport: str, platform: str) -> bool:
    """Try to acquire a per-endpoint distributed lock via SETNX.

    Returns True if the lock was acquired, False if another worker
    is already syncing this endpoint.
    """
    r = _redis()
    if r is None:
        return True  # no Redis = no concurrency control (single-worker safe)
    key = f"bcdfs:lock:{sport.lower()}_{platform.lower()}"
    try:
        acquired = r.set(key, "1", nx=True, ex=LOCK_TTL)
        return bool(acquired)
    except Exception:
        return True   # err on the side of allowing the sync


def _release_sync_lock(sport: str, platform: str) -> None:
    """Release a per-endpoint distributed lock."""
    r = _redis()
    if r is None:
        return
    key = f"bcdfs:lock:{sport.lower()}_{platform.lower()}"
    try:
        r.delete(key)
    except Exception:
        pass


def _set_suspended(sport: str, platform: str) -> None:
    """Flag an endpoint as suspended (401/403 — needs admin attention)."""
    r = _redis()
    if r is None:
        return
    key = f"bcdfs:suspend:{sport.lower()}_{platform.lower()}"
    try:
        r.setex(key, 86400, "1")  # 24h TTL
    except Exception:
        pass


def _is_suspended(sport: str, platform: str) -> bool:
    """Check if endpoint is flagged as suspended."""
    r = _redis()
    if r is None:
        return False
    key = f"bcdfs:suspend:{sport.lower()}_{platform.lower()}"
    try:
        return bool(r.get(key))
    except Exception:
        return False


def _clear_suspension(sport: str, platform: str) -> None:
    """Clear a suspension flag on successful auth."""
    r = _redis()
    if r is None:
        return
    key = f"bcdfs:suspend:{sport.lower()}_{platform.lower()}"
    try:
        r.delete(key)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# EndpointStatus
# ══════════════════════════════════════════════════════════════════════

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
            backoff = BACKOFF_BASE * (2 ** min(self.consecutive_errors, 5))
            return min(backoff, BACKOFF_MAX_SEC)
        if self.state == EndpointState.PRE_LOCK:
            return PRE_LOCK_INTERVAL
        if self.state == EndpointState.ACTIVE:
            return ACTIVE_INTERVAL
        if self.state == EndpointState.POST_LOCK:
            return POST_LOCK_INTERVAL
        if self.state in (EndpointState.ERROR, EndpointState.SUSPENDED):
            backoff = BACKOFF_BASE * (2 ** min(self.consecutive_errors, 5))
            return min(backoff, BACKOFF_MAX_SEC)
        return OFFSEASON_INTERVAL

    def priority(self) -> int:
        return PRIORITY_MAP.get(self.state, PRIORITY_UNKNOWN)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "slate_count": self.slate_count,
            "player_count": self.player_count,
            "backoff_until": self.backoff_until.isoformat() if self.backoff_until else None,
            "consecutive_errors": self.consecutive_errors,
            "next_poll": self.next_poll.isoformat() if self.next_poll else None,
        }


# ══════════════════════════════════════════════════════════════════════
# Global state (per-process only — counters live in Redis)
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SchedulerState:
    endpoints: dict = field(default_factory=dict)
    last_tick: Optional[datetime] = None
    tick_count: int = 0

    def __post_init__(self):
        for (sport, platform) in ENDPOINTS:
            status = EndpointStatus(sport=sport, platform=platform)
            if _is_suspended(sport, platform):
                status.state = EndpointState.SUSPENDED
            self.endpoints[(sport, platform)] = status

    def to_dict(self) -> dict:
        eps = {}
        for key, status in self.endpoints.items():
            eps[f"{key[0]}_{key[1]}"] = status.to_dict()
        return {
            "daily_requests_used": _get_counter(_today_key("budget:auto")) + _get_counter(_today_key("budget:manual")),
            "daily_requests_remaining": SB_ME_CEILING - (
                _get_counter(_today_key("budget:auto")) + _get_counter(_today_key("budget:manual"))
            ),
            "auto_budget_remaining": _budget_remaining("auto", AUTO_BUDGET),
            "manual_budget_remaining": _budget_remaining("manual", MANUAL_RESERVE),
            "auto_budget_limit": AUTO_BUDGET,
            "manual_budget_limit": MANUAL_RESERVE,
            "sb_me_ceiling": SB_ME_CEILING,
            "provider_limit": PROVIDER_LIMIT,
            "last_tick": self.last_tick.isoformat() if self.last_tick else None,
            "tick_count": self.tick_count,
            "endpoints": eps,
        }


_scheduler_state: Optional[SchedulerState] = None


def get_scheduler_state() -> SchedulerState:
    global _scheduler_state
    if _scheduler_state is None:
        _scheduler_state = SchedulerState()
    return _scheduler_state


# ══════════════════════════════════════════════════════════════════════
# Slate activity detection
# ══════════════════════════════════════════════════════════════════════

def _determine_state(parse_result, prev_state: EndpointState) -> EndpointState:
    if not parse_result.slates:
        return EndpointState.OFFSZN

    now_utc = datetime.now(timezone.utc)
    earliest = None
    all_past = True

    for cs in parse_result.slates:
        st = cs.start_time
        if st is None:
            continue
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        if earliest is None or st < earliest:
            earliest = st
        if st > now_utc:
            all_past = False

    if earliest is None:
        return EndpointState.ACTIVE

    seconds_to_first = (earliest - now_utc).total_seconds()
    if 0 < seconds_to_first < LOCK_WINDOW_SECONDS:
        return EndpointState.PRE_LOCK
    if all_past:
        return EndpointState.POST_LOCK
    return EndpointState.ACTIVE


# ══════════════════════════════════════════════════════════════════════
# Per-endpoint sync — with atomic budget reservation + distributed lock
# ══════════════════════════════════════════════════════════════════════

async def _sync_one_endpoint(
    db: AsyncSession,
    status: EndpointStatus,
    budget_type: str = "auto",
) -> BcSyncReport:
    """Sync one endpoint.  Atomic budget reservation guards spending.

    budget_type: 'auto' (scheduler) or 'manual' (admin refresh).
    Each has its own Redis counter and limit.

    On 401/403: sets persistent suspension flag, stops automated retries.
    On 429: respects provider backoff, does NOT re-fetch.
    On 5xx/network: exponential backoff, preserves last-good data.
    """
    now = datetime.now(timezone.utc)
    report = BcSyncReport(sport=status.sport, platform=status.platform)
    budget_limit = AUTO_BUDGET if budget_type == "auto" else MANUAL_RESERVE

    # ── Check suspension ──
    if budget_type == "auto" and _is_suspended(status.sport, status.platform):
        report.warnings.append("Endpoint suspended (auth failure) — requires admin")
        return report
    if status.state == EndpointState.SUSPENDED:
        report.warnings.append("Endpoint suspended")
        return report

    # ── Backoff check ──
    if status.backoff_until and now < status.backoff_until:
        remaining = (status.backoff_until - now).total_seconds()
        report.warnings.append(f"Backoff for {int(remaining)}s")
        return report

    # ── Distributed lock (prevent concurrent sync of same endpoint) ──
    if not _acquire_sync_lock(status.sport, status.platform):
        report.warnings.append("Sync already in progress for this endpoint")
        return report

    try:
        # ── Atomic budget reservation ──
        reserved = False
        consumed_provider_request = False
        if not _try_reserve_budget(budget_type, budget_limit):
            status.last_error = f"DAILY_BUDGET_EXHAUSTED ({budget_type})"
            status.last_error_time = now
            report.errors.append(f"Daily {budget_type} budget exhausted ({budget_limit}/day)")
            if budget_type == "auto":
                pass  # don't flip to ERROR on budget exhaustion — retry tomorrow
            return report
        reserved = True

        # ── Fetch + parse + sync ──
        try:
            data = fetch_bc_endpoint(status.sport, status.platform)
            consumed_provider_request = True
            parse_result = parse_bc_response(data, status.sport, status.platform)
            report = await sync_bc_to_db(db, parse_result, auto_publish=True)

            # Success — reset everything
            status.state = _determine_state(parse_result, status.state)
            status.last_sync = now
            status.last_success = now
            status.consecutive_errors = 0
            status.backoff_until = None
            status.slate_count = report.total_slates
            status.player_count = report.total_players
            status.last_error = None
            status.last_error_time = None

            # Clear any prior suspension
            _clear_suspension(status.sport, status.platform)

        except BcAuthError as e:
            consumed_provider_request = True
            # 401/403 — suspend automated syncs permanently
            status.state = EndpointState.SUSPENDED
            status.last_error = f"Auth ({e.status})"
            status.last_error_time = now
            status.consecutive_errors += 1
            status.backoff_until = now + timedelta(seconds=AUTH_BACKOFF_SEC)
            report.errors.append(f"Auth failure: endpoint suspended")
            if budget_type == "auto":
                _set_suspended(status.sport, status.platform)  # persistent across restarts

        except BcRateLimitError as e:
            consumed_provider_request = True
            status.state = EndpointState.ERROR
            status.last_error = "429 provider rate limit"
            status.last_error_time = now
            status.consecutive_errors += 1
            status.backoff_until = now + timedelta(seconds=BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)))
            report.errors.append("Provider 429")

        except BcApiError as e:
            # HTTP responses reached Blue Collar (count against budget).
            # status 0 = local/network failure before a countable HTTP response.
            consumed_provider_request = bool(getattr(e, "status", 0))
            if status.state not in (EndpointState.OFFSZN, EndpointState.SUSPENDED, EndpointState.POST_LOCK):
                status.state = EndpointState.ERROR
            status.last_error = str(e)[:200]
            status.last_error_time = now
            status.consecutive_errors += 1
            backoff = min(BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)), BACKOFF_MAX_SEC)
            status.backoff_until = now + timedelta(seconds=backoff)
            report.errors.append(str(e))

        except Exception as e:
            # Unknown failure after reservation: keep the budget slot so retries
            # cannot exceed Blue Collar's actual daily cap.
            consumed_provider_request = True
            if status.state not in (EndpointState.OFFSZN, EndpointState.SUSPENDED, EndpointState.POST_LOCK):
                status.state = EndpointState.ERROR
            status.last_error = str(e)[:200]
            status.last_error_time = now
            status.consecutive_errors += 1
            backoff = min(BACKOFF_BASE * (2 ** min(status.consecutive_errors, 5)), BACKOFF_MAX_SEC)
            status.backoff_until = now + timedelta(seconds=backoff)
            report.errors.append(str(e))

    finally:
        if reserved and not consumed_provider_request:
            _release_budget(budget_type)
        _release_sync_lock(status.sport, status.platform)

    status.next_poll = now + timedelta(seconds=status.interval_seconds())
    return report


# ══════════════════════════════════════════════════════════════════════
# Scheduler tick — prioritised, budget-aware
# ══════════════════════════════════════════════════════════════════════

async def scheduler_tick(
    db: AsyncSession,
    force_sports: Optional[list] = None,
) -> dict:
    """Run one scheduler cycle.

    Automated tick (force_sports=None):
      - Collects endpoints whose next_poll is due
      - Sorts by priority (PRE_LOCK > ACTIVE > POST_LOCK > OFFSZN)
      - Syncs each in order, stopping when auto budget is exhausted
      - A tick wake-up may sync 0 endpoints (none due)

    Manual refresh (force_sports provided):
      - Uses manual budget (MANUAL_RESERVE = 20/day)
      - Bypasses priority/due-time checks
    """
    state = get_scheduler_state()
    now = datetime.now(timezone.utc)
    state.last_tick = now
    state.tick_count += 1

    budget_type = "auto" if force_sports is None else "manual"

    if force_sports is not None:
        targets = [(s.upper(), p.lower()) for s, p in force_sports]
    else:
        # Collect due endpoints, sorted by priority (lowest = most urgent)
        due = [
            (status.priority(), sport, platform)
            for (sport, platform), status in state.endpoints.items()
            if (status.next_poll is None or now >= status.next_poll)
            and not _is_suspended(sport, platform)
        ]
        due.sort(key=lambda x: x[0])  # sort by priority
        targets = [(s, p) for _, s, p in due]

    reports: dict = {}
    for sport, platform in targets:
        key = f"{sport}_{platform}"
        status = state.endpoints.get((sport, platform))
        if status is None:
            reports[key] = {"error": "Unknown endpoint"}
            continue

        report = await _sync_one_endpoint(db, status, budget_type=budget_type)
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

        # Budget check after each sync — stop if automated budget exhausted
        if budget_type == "auto" and _budget_remaining("auto", AUTO_BUDGET) <= 0:
            logger.warning("BCDFS auto budget exhausted — stopping tick after %d syncs", len(reports))
            break

        # Stagger writes
        if len(targets) > 1:
            await asyncio.sleep(1)

    # ── Optimal% auto-generation trigger (Phase 2E) ──
    # After each BCDFS tick, check if any unlocked slates need fresh
    # Optimal% computation. This is a lightweight eligibility check;
    # the actual 500-sim workload runs asynchronously in the Celery worker.
    if budget_type == "auto":
        try:
            from worker.tasks import auto_generate_optimal_pct
            auto_generate_optimal_pct.delay()
        except Exception:
            pass  # non-blocking; try again next tick

    return {
        "status": "ok",
        "budget_type": budget_type,
        "tick": state.tick_count,
        "synced": len(reports),
        "auto_budget_remaining": _budget_remaining("auto", AUTO_BUDGET),
        "manual_budget_remaining": _budget_remaining("manual", MANUAL_RESERVE),
        "daily_requests_used": _get_counter(_today_key("budget:auto")) + _get_counter(_today_key("budget:manual")),
        "endpoints": reports,
    }


# ══════════════════════════════════════════════════════════════════════
# Admin + observability
# ══════════════════════════════════════════════════════════════════════

async def admin_refresh(db: AsyncSession, sport: str, platform: str) -> dict:
    """Admin-only manual refresh — uses manual budget (20/day)."""
    return await scheduler_tick(db, force_sports=[(sport, platform)])


def get_operational_status() -> dict:
    """Full operational status — no secrets, no raw BC data."""
    state = get_scheduler_state()
    result = state.to_dict()
    # Add per-endpoint suspension status
    for key, ep in result.get("endpoints", {}).items():
        sport, platform = key.split("_", 1)
        ep["suspended"] = _is_suspended(sport, platform)
    return result