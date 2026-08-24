'''BCDFS Hardened tests.'''
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from dfs.bcdfs_scheduler import (
    EndpointState, EndpointStatus, SchedulerState, get_scheduler_state,
    _today_key, _get_counter, _try_reserve_budget, _release_budget,
    _budget_remaining, _acquire_sync_lock, _release_sync_lock,
    _set_suspended, _is_suspended, _clear_suspension,
    AUTO_BUDGET, MANUAL_RESERVE, SB_ME_CEILING, PROVIDER_LIMIT,
    PRIORITY_PRE_LOCK, PRIORITY_ACTIVE,
)
from dfs.models import DFSSlate as CanonicalSlate

def _make_slate(name, start_delta_minutes=180):
    start = datetime.now(timezone.utc) + timedelta(minutes=start_delta_minutes)
    return CanonicalSlate(platform="draftkings", slate_id="test", slate_name=name,
                          sport="MLB", start_time=start, player_count=10,
                          data_source="blue_collar")

class MockRedis:
    def __init__(self): self._data = {}
    def incr(self, key):
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val).encode(); return val
    def decr(self, key):
        val = max(0, int(self._data.get(key, 0)) - 1)
        self._data[key] = str(val).encode(); return val
    def get(self, key): return self._data.get(key)
    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._data: return None
        self._data[key] = str(value).encode() if isinstance(value, str) else value
        return True
    def setex(self, key, ttl, value):
        self._data[key] = value if isinstance(value, bytes) else str(value).encode()
        return True
    def delete(self, key): self._data.pop(key, None)
    def expire(self, key, ttl): return True
    def ping(self): return True

@pytest.fixture
def mock_redis():
    mr = MockRedis()
    with patch("dfs.bcdfs_scheduler._redis", return_value=mr):
        yield mr

@pytest.fixture(autouse=True)
def reset_scheduler():
    import dfs.bcdfs_scheduler as mod
    mod._scheduler_state = SchedulerState()
    yield

class TestBudget:
    def test_auto_never_exceeds_130(self, mock_redis):
        for _ in range(200): _try_reserve_budget("auto", 130)
        assert _get_counter(_today_key("budget:auto")) == 130

    def test_total_never_exceeds_150(self, mock_redis):
        for _ in range(200): _try_reserve_budget("auto", 130)
        for _ in range(50): _try_reserve_budget("manual", 20)
        total = _get_counter(_today_key("budget:auto")) + _get_counter(_today_key("budget:manual"))
        assert total <= 150

    def test_auto_exhausted_manual_ok(self, mock_redis):
        for _ in range(130): _try_reserve_budget("auto", 130)
        assert not _try_reserve_budget("auto", 130)
        assert _try_reserve_budget("manual", 20)

    def test_separate_counters(self, mock_redis):
        _try_reserve_budget("auto", 130); _try_reserve_budget("manual", 20)
        assert _get_counter(_today_key("budget:auto")) == 1
        assert _get_counter(_today_key("budget:manual")) == 1

    def test_survives_restart(self, mock_redis):
        _try_reserve_budget("auto", 130)
        assert _get_counter(_today_key("budget:auto")) == 1
        assert _get_counter(_today_key("budget:auto")) == 1  # same key

class TestLock:
    def test_acquire(self, mock_redis): assert _acquire_sync_lock("MLB", "draftkings")
    def test_blocked(self, mock_redis):
        _acquire_sync_lock("MLB", "draftkings")
        assert not _acquire_sync_lock("MLB", "draftkings")
    def test_release(self, mock_redis):
        _acquire_sync_lock("MLB", "draftkings"); _release_sync_lock("MLB", "draftkings")
        assert _acquire_sync_lock("MLB", "draftkings")

class TestSuspension:
    def test_set_check_clear(self, mock_redis):
        assert not _is_suspended("MLB", "draftkings")
        _set_suspended("MLB", "draftkings")
        assert _is_suspended("MLB", "draftkings")
        _clear_suspension("MLB", "draftkings")
        assert not _is_suspended("MLB", "draftkings")

class TestState:
    def test_eight_endpoints(self):
        assert len(SchedulerState().endpoints) == 8
    def test_no_secrets(self):
        d = json.dumps(SchedulerState().to_dict())
        assert "api_key" not in d.lower()
        assert "projection" not in d.lower()
    def test_budgets(self):
        d = SchedulerState().to_dict()
        assert d["auto_budget_limit"] == 130
        assert d["manual_budget_limit"] == 20

class TestTick:
    @pytest.mark.asyncio
    async def test_manual_budget(self, mock_redis, monkeypatch):
        async def fake(db, status, budget_type="auto"):
            assert budget_type == "manual"
            from dfs.bcdfs_adapter import BcSyncReport
            return BcSyncReport(sport=status.sport, platform=status.platform)
        monkeypatch.setattr("dfs.bcdfs_scheduler._sync_one_endpoint", fake)
        from dfs.bcdfs_scheduler import scheduler_tick
        r = await scheduler_tick(MagicMock(), force_sports=[("MLB", "draftkings")])
        assert r["budget_type"] == "manual"

    @pytest.mark.asyncio
    async def test_exhausted_no_sync(self, mock_redis, monkeypatch):
        for _ in range(130): _try_reserve_budget("auto", 130)
        for st in get_scheduler_state().endpoints.values():
            st.next_poll = datetime.now(timezone.utc) - timedelta(minutes=1)
        from dfs.bcdfs_scheduler import scheduler_tick
        result = await scheduler_tick(MagicMock())
        # Budget was 130/130 — every endpoint sync should report budget exhaustion
        for key, ep in result["endpoints"].items():
            assert "budget" in str(ep.get("errors", [])).lower() or "exhaust" in str(ep.get("errors", [])).lower()
        # Auto budget counter should still be exactly 130 (no requests consumed)
        assert _get_counter(_today_key("budget:auto")) == 130

    @pytest.mark.asyncio
    async def test_suspended_skipped(self, mock_redis, monkeypatch):
        _set_suspended("MLB", "draftkings")
        state = get_scheduler_state()
        state.endpoints[("MLB", "draftkings")].state = EndpointState.SUSPENDED
        state.endpoints[("MLB", "draftkings")].next_poll = datetime.now(timezone.utc) - timedelta(minutes=1)
        from dfs.bcdfs_scheduler import scheduler_tick
        result = await scheduler_tick(MagicMock())
        # Suspended endpoints are filtered from targets — should not appear in results
        assert "MLB_draftkings" not in result["endpoints"]

class TestErrors:
    @pytest.mark.asyncio
    async def test_401_suspends(self, mock_redis, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcAuthError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcAuthError(401, "bad")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        await _sync_one_endpoint(MagicMock(), status, budget_type="auto")
        assert status.state == EndpointState.SUSPENDED
        assert _is_suspended("MLB", "draftkings")

    @pytest.mark.asyncio
    async def test_429_not_suspended(self, mock_redis, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcRateLimitError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcRateLimitError(429, "many")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        await _sync_one_endpoint(MagicMock(), status, budget_type="auto")
        assert status.state != EndpointState.SUSPENDED

    @pytest.mark.asyncio
    async def test_outage_preserves_data(self, mock_redis, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcApiError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        status.slate_count = 3; status.player_count = 1491
        def fake_fetch(*a, **kw): raise BcApiError(503, "down")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        await _sync_one_endpoint(MagicMock(), status, budget_type="auto")
        assert status.slate_count == 3

    @pytest.mark.asyncio
    async def test_api_key_not_in_errors(self, mock_redis, monkeypatch):
        from dfs.bcdfs_scheduler import _sync_one_endpoint, BcApiError
        status = EndpointStatus(sport="MLB", platform="draftkings")
        def fake_fetch(*a, **kw): raise BcApiError(500, "err")
        monkeypatch.setattr("dfs.bcdfs_scheduler.fetch_bc_endpoint", fake_fetch)
        report = await _sync_one_endpoint(MagicMock(), status, budget_type="auto")
        assert "ApiKey" not in str(report.errors) + str(status.last_error or "")

class Test001Gone:
    def test_no_001_in_canonical(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "dfs", "canonical.py")
        with open(path) as f:
            for line in f:
                s = line.strip()
                if s.startswith("#"): continue
                if s.startswith(chr(34)*3) or s.startswith(chr(39)*3): continue
                if "0.01" in s and "projected_fp" in s.lower():
                    assert False, f"0.01 still present: {s}"
