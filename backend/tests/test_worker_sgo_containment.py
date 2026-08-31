"""Celery Optimal% must not issue duplicate current-event SGO HTTP."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.sgo_data import load_canonical_sb_events
from dfs.optimal_cache import STATUS_FAILED
from projection.sgo_intelligence import build_sgo_intelligence
from worker.optimal_sim_tasks import (
    _build_pool_live,
    _run_sim_async,
    run_optimal_sim,
)
from worker.tasks import _auto_generate_sync, auto_generate_optimal_pct


LKG = [{
    "id": "mlb-1",
    "start_time": "2026-08-31T23:10:00+00:00",
    "home_team": {"abbreviation": "CLE", "team_id": "CLE"},
    "away_team": {"abbreviation": "NYY", "team_id": "NYY"},
    "players": [{"player_id": "p1", "name": "José Ramírez", "team_id": "CLE", "position": "3B"}],
    "markets": [{
        "player_name": "José Ramírez",
        "market_name": "Player Fantasy Score",
        "fair_over_under": 11.5,
        "books": [],
    }],
}]


@pytest.fixture(autouse=True)
def _reset_sgo_fetch_state():
    import api.sgo_data as mod
    mod._fetch_fail_until.clear()
    yield
    mod._fetch_fail_until.clear()


def _install_redis(monkeypatch, store: dict):
    def fake_rget(key):
        return store.get(key)

    def fake_rset(key, data, ttl=None):
        store[key] = data
        store[f"{key}:ttl"] = ttl

    monkeypatch.setattr("api.sgo_data._rget", fake_rget)
    monkeypatch.setattr("api.sgo_data._rset", fake_rset)
    monkeypatch.setattr("api.sgo_data._clear_obsolete_event_model_keys", lambda league: None)
    return store


class TestWorkerDoesNotDirectFetch:
    def test_live_pool_builder_disables_sgo_fetch(self):
        src = inspect.getsource(_build_pool_live)
        assert "sgo_allow_fetch=False" in src
        assert "SdkSgoProvider" not in src

    def test_run_optimal_sim_task_still_registered(self):
        assert run_optimal_sim.name.endswith("run_optimal_sim")
        assert getattr(run_optimal_sim, "max_retries", None) == 0

    def test_auto_generate_still_enqueues_without_sgo(self):
        src = inspect.getsource(_auto_generate_sync)
        assert "run_optimal_sim.delay" in src
        assert "SdkSgoProvider" not in src
        assert "get_sb_events" not in src
        assert "SdkSgoProvider" not in inspect.getsource(auto_generate_optimal_pct)

    def test_canonical_sdk_provider_disables_retries(self):
        from providers.sdk_provider import SdkSgoProvider
        src = inspect.getsource(SdkSgoProvider.__init__)
        assert "max_retries=0" in src

    @pytest.mark.asyncio
    async def test_allow_fetch_false_does_not_call_upstream(self, monkeypatch):
        _install_redis(monkeypatch, {})
        fetch = AsyncMock(side_effect=AssertionError("worker must not hit SGO"))
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )
        intel = await build_sgo_intelligence(
            "MLB", [{"id": "dk-1", "name": "Jose Ramirez"}], allow_fetch=False,
        )
        assert intel == {}
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_lkg_satisfies_worker_without_upstream(self, monkeypatch):
        _install_redis(monkeypatch, {"sgo:v2:sbevents:MLB:lkg": list(LKG)})
        fetch = AsyncMock(side_effect=AssertionError("must not fetch"))
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )
        intel = await build_sgo_intelligence(
            "MLB", [{"id": "dk-1", "name": "Jose Ramirez"}], allow_fetch=False,
        )
        assert intel["dk-1"]["fantasyScore"] == 11.5
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_cache_satisfies_worker(self, monkeypatch):
        _install_redis(monkeypatch, {"sgo:v2:sbevents:MLB": list(LKG)})
        fetch = AsyncMock(side_effect=AssertionError("must not fetch"))
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )
        events, source = await load_canonical_sb_events("MLB", allow_fetch=False)
        assert source == "cached"
        assert events[0]["id"] == "mlb-1"
        intel = await build_sgo_intelligence(
            "MLB", [{"id": "dk-1", "name": "Jose Ramirez"}], allow_fetch=False,
        )
        assert intel["dk-1"]["fantasyScore"] == 11.5
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_lkg_stays_honest_empty(self, monkeypatch):
        _install_redis(monkeypatch, {})
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=AsyncMock(side_effect=RuntimeError("429"))),
        )
        intel = await build_sgo_intelligence("MLB", [{"id": "x", "name": "Nobody"}], allow_fetch=False)
        assert intel == {}

    @pytest.mark.asyncio
    async def test_api_default_allow_fetch_still_reaches_canonical_upstream(self, monkeypatch):
        """Sportbook-me- /optimize keeps allow_fetch=True (default)."""
        _install_redis(monkeypatch, {})
        fetch = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )
        intel = await build_sgo_intelligence("MLB", [{"id": "dk-1", "name": "Jose Ramirez"}])
        assert intel == {}
        fetch.assert_awaited_once_with("MLB")

    @pytest.mark.asyncio
    async def test_snapshot_mode_does_not_build_live_pool(self):
        with patch("worker.optimal_sim_tasks._build_pool_live", new=AsyncMock(
            side_effect=AssertionError("snapshot must not live-build"),
        )), patch("worker.optimal_sim_tasks._load_pool_from_snapshot", new=AsyncMock(
            return_value=None,
        )), patch("worker.optimal_sim_tasks.cache.set_status"):
            result = await _run_sim_async(
                "draftkings", "MLB", 1, 10, 42, 1.0, inputs_hash="abc",
            )
        assert result == {"error": "snapshot not found", "inputs_hash": "abc"}

    @pytest.mark.asyncio
    async def test_live_mode_empty_pool_is_honest_error(self):
        with patch("worker.optimal_sim_tasks._build_pool_live", new=AsyncMock(return_value=[])), \
             patch("worker.optimal_sim_tasks.cache.set_status") as set_status:
            result = await _run_sim_async("draftkings", "MLB", 1, 10, 42, 1.0)
        assert result == {"error": "empty pool"}
        failed = [c for c in set_status.call_args_list if STATUS_FAILED in c.args]
        assert failed
