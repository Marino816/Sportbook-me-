"""BCDFS Scheduler tests — comprehensive coverage."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from dfs.bcdfs_scheduler import (
    EndpointState, EndpointStatus, SchedulerState, _determine_state,
    get_scheduler_state, SAFE_DAILY_LIMIT, ACTIVE_INTERVAL,
    PRE_LOCK_INTERVAL, OFFSEASON_INTERVAL, POST_LOCK_INTERVAL,
)
from dfs.bcdfs_adapter import BcRateLimiter, BcParseResult
from dfs.models import DFSSlate as CanonicalSlate


def _make_slate(name, start_delta_minutes=180):
    start = datetime.now(timezone.utc) + timedelta(minutes=start_delta_minutes)
    return CanonicalSlate(
        platform="draftkings", slate_id="test", slate_name=name,
        sport="MLB", start_time=start, player_count=10,
        data_source="blue_collar",
    )


class TestEndpointInterval:
    def test_active(self):
        s = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.ACTIVE)
        assert s.interval_seconds() == ACTIVE_INTERVAL

    def test_pre_lock(self):
        s = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.PRE_LOCK)
        assert s.interval_seconds() == PRE_LOCK_INTERVAL

    def test_offseason(self):
        s = EndpointStatus(sport="NFL", platform="draftkings", state=EndpointState.OFFSZN)
        assert s.interval_seconds() == OFFSEASON_INTERVAL

    def test_post_lock(self):
        s = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.POST_LOCK)
        assert s.interval_seconds() == POST_LOCK_INTERVAL

    def test_backoff_overrides(self):
        s = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.ACTIVE)
        s.backoff_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        s.consecutive_errors = 2
        assert s.interval_seconds() == 240

    def test_error_state(self):
        s = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.ERROR)
        s.consecutive_errors = 1
        assert s.interval_seconds() == 120


class TestDetermineState:
    def test_no_slates_offseason(self):
        r = BcParseResult(sport="NFL", platform="draftkings")
        assert _determine_state(r, EndpointState.ACTIVE) == EndpointState.OFFSZN

    def test_active(self):
        r = BcParseResult(sport="MLB", platform="draftkings")
        r.slates = [_make_slate("Main", 180)]
        assert _determine_state(r, EndpointState.UNKNOWN) == EndpointState.ACTIVE

    def test_pre_lock(self):
        r = BcParseResult(sport="MLB", platform="draftkings")
        r.slates = [_make_slate("Main", 90)]
        assert _determine_state(r, EndpointState.UNKNOWN) == EndpointState.PRE_LOCK

    def test_no_start_time(self):
        r = BcParseResult(sport="MLB", platform="draftkings")
        cs = _make_slate("Main", 180)
        cs.start_time = None
        r.slates = [cs]
        assert _determine_state(r, EndpointState.UNKNOWN) == EndpointState.ACTIVE

    def test_post_lock(self):
        r = BcParseResult(sport="MLB", platform="draftkings")
        r.slates = [_make_slate("Main", -120)]
        assert _determine_state(r, EndpointState.UNKNOWN) == EndpointState.POST_LOCK


class TestSchedulerState:
    def test_initial_endpoints(self):
        s = SchedulerState()
        assert len(s.endpoints) == 8
        assert ("MLB", "draftkings") in s.endpoints
        assert ("GOLF", "fanduel") in s.endpoints

    def test_endpoints_unknown(self):
        s = SchedulerState()
        for st in s.endpoints.values():
            assert st.state == EndpointState.UNKNOWN

    def test_budget_tracks(self):
        s = SchedulerState()
        s.rate_limiter.record("test")
        assert s.daily_requests_used() == 1

    def test_to_dict_serializable(self):
        s = SchedulerState()
        d = s.to_dict()
        assert d["safe_daily_limit"] == SAFE_DAILY_LIMIT
        assert "MLB_draftkings" in d["endpoints"]

    def test_singleton(self):
        s1 = get_scheduler_state()
        s2 = get_scheduler_state()
        assert s1 is s2

    def test_concurrent_lock(self):
        s = SchedulerState()
        s.active_sync_lock = True
        assert s.active_sync_lock


class TestSchedulerTick:
    @pytest.mark.asyncio
    async def test_skips_when_locked(self):
        state = get_scheduler_state()
        state.active_sync_lock = True
        from dfs.bcdfs_scheduler import scheduler_tick
        result = await scheduler_tick(MagicMock())
        assert result["status"] == "skipped"
        state.active_sync_lock = False

    @pytest.mark.asyncio
    async def test_force_sports_works(self, monkeypatch):
        from dfs.bcdfs_scheduler import scheduler_tick, get_scheduler_state
        state = get_scheduler_state()
        state.active_sync_lock = False
        state.rate_limiter._counts.clear()

        async def fake_sync(db, status):
            from dfs.bcdfs_scheduler import BcSyncReport
            r = BcSyncReport(sport=status.sport, platform=status.platform)
            r.slates_created = 1; r.players_added = 100; return r
        monkeypatch.setattr("dfs.bcdfs_scheduler._sync_one_endpoint", fake_sync)

        result = await scheduler_tick(MagicMock(), force_sports=[("MLB", "draftkings")])
        assert result["status"] == "ok"
        assert result["synced"] == 1
        assert result["endpoints"]["MLB_draftkings"]["slates_created"] == 1

    @pytest.mark.asyncio
    async def test_unknown_endpoint(self, monkeypatch):
        from dfs.bcdfs_scheduler import scheduler_tick, get_scheduler_state
        state = get_scheduler_state()
        state.active_sync_lock = False
        state.endpoints.pop(("MLB", "draftkings"), None)
        result = await scheduler_tick(MagicMock(), force_sports=[("MLB", "draftkings")])
        assert "error" in result["endpoints"]["MLB_draftkings"]


class TestSyncOneEndpointErrors:
    @pytest.mark.asyncio
    async def test_rate_limit(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, get_scheduler_state, BcRateLimitError
        state = get_scheduler_state()
        state.active_sync_lock = False
        state.rate_limiter._counts.clear()
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcRateLimitError(429, "Too many")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        report = await _sync_one_endpoint(MagicMock(), status)
        assert len(report.errors) > 0
        assert status.state == EndpointState.ERROR

    @pytest.mark.asyncio
    async def test_auth_long_backoff(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcAuthError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcAuthError(401, "bad")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        await _sync_one_endpoint(MagicMock(), status)
        assert status.backoff_until is not None
        backoff_s = (status.backoff_until - datetime.now(timezone.utc)).total_seconds()
        assert backoff_s > 21000

    @pytest.mark.asyncio
    async def test_5xx_backoff_grows(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcApiError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcApiError(500, "err")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        
        await _sync_one_endpoint(MagicMock(), status)
        assert status.consecutive_errors == 1
        b1 = status.backoff_until
        
        # Advance past backoff for second error
        status.backoff_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await _sync_one_endpoint(MagicMock(), status)
        assert status.consecutive_errors == 2
        assert status.backoff_until > b1

    @pytest.mark.asyncio
    async def test_offseason_stays_offseason_on_error(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcApiError
        status = EndpointStatus(sport="NFL", platform="draftkings", state=EndpointState.OFFSZN)
        def fake_fetch(*a, **kw): raise BcApiError(500, "err")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        await _sync_one_endpoint(MagicMock(), status)
        assert status.state == EndpointState.OFFSZN

    @pytest.mark.asyncio
    async def test_budget_exhausted(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, get_scheduler_state
        state = get_scheduler_state()
        state.active_sync_lock = False
        for _ in range(state.rate_limiter.remaining()):
            state.rate_limiter.record()
        status = EndpointStatus(sport="MLB", platform="draftkings")
        report = await _sync_one_endpoint(MagicMock(), status)
        assert "budget" in str(report.errors).lower() or "Budget" in str(report.errors)
        assert status.state == EndpointState.ERROR

    @pytest.mark.asyncio
    async def test_backoff_skips(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint
        status = EndpointStatus(sport="MLB", platform="draftkings")
        status.backoff_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        report = await _sync_one_endpoint(MagicMock(), status)
        assert "Backoff" in str(report.warnings)

    @pytest.mark.asyncio
    async def test_success_resets_errors(self, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, get_scheduler_state
        state = get_scheduler_state()
        state.active_sync_lock = False
        state.rate_limiter._counts.clear()
        status = EndpointStatus(sport="MLB", platform="draftkings", state=EndpointState.ERROR)
        status.consecutive_errors = 5
        status.backoff_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        # Mock success
        def fake_fetch(*a, **kw): return {}
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        def fake_parse(*a, **kw):
            r = BcParseResult(sport="MLB", platform="draftkings")
            r.slates = [_make_slate("M", 180)]
            r.players_by_slate = {r.slates[0].slate_id: []}
            return r
        monkeypatch.setattr("dfs.bcdfs_scheduler.parse_bc_response", fake_parse)
        async def fake_sync(*a, **kw):
            from dfs.bcdfs_scheduler import BcSyncReport
            return BcSyncReport(sport="MLB", platform="draftkings")
        monkeypatch.setattr("dfs.bcdfs_scheduler.sync_bc_to_db", fake_sync)
        await _sync_one_endpoint(MagicMock(), status)
        assert status.consecutive_errors == 0
        assert status.state == EndpointState.ACTIVE


# Verify no BC projection leakage
class TestNoBcProjectionLeakage:
    def test_scheduler_state_no_api_key(self):
        """SchedulerState.to_dict must not contain BC_API_KEY or raw data."""
        s = SchedulerState()
        d = s.to_dict()
        assert "api_key" not in str(d).lower()
        assert "bc_api" not in str(d).lower()

    def test_endpoint_status_no_secret(self):
        s = EndpointStatus(sport="MLB", platform="draftkings")
        d = {
            "state": s.state.value,
            "last_error": s.last_error,
            "slate_count": s.slate_count,
        }
        assert "api_key" not in str(d).lower()
        assert "projection" not in str(d).lower()  # no BC projection


# Verify 0.01 fallback remains removed
class TestNo001Fallback:
    def test_canonical_no_001_loop(self):
        """Verify the 0.01 fallback loop is NOT present in canonical.py."""
        import ast, os
        path = os.path.join(
            os.path.dirname(__file__), "..", "dfs", "canonical.py"
        )
        with open(path) as f:
            lines = f.readlines()
        # Check each line: if it contains 0.01 AND is actual code (not a comment)
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "0.01" in stripped:
                # If the line is a triple-quoted string (docstring/comment), skip
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                # If the line is inside a string literal
                assert False, f"0.01 fallback must be removed from canonical.py — found: {stripped}"
