"""Regression: customer GET /api/optimal-pct must read real DFS slates + cached Optimal%."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import models.domain as domain_models
from api import data_hub
from api.data_hub import optimal_pct


def test_optimal_pct_imports_dfs_slate_not_domain():
    """The customer endpoint used to `from models.domain import DFSSlate`, which
    does not exist — every request 500'd and the Optimizer showed OPT% as —."""
    src = inspect.getsource(data_hub.optimal_pct)
    assert "from dfs.db import DFSSlate" in src
    assert "from models.domain import DFSSlate" not in src
    assert not hasattr(domain_models, "DFSSlate")


class _FakeResult:
    def __init__(self, slate):
        self._slate = slate

    def scalar_one_or_none(self):
        return self._slate


class _FakeDB:
    def __init__(self, slate):
        self._slate = slate

    async def execute(self, _stmt):
        return _FakeResult(self._slate)


@pytest.mark.asyncio
async def test_optimal_pct_returns_cached_players(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(hours=8)
    slate = SimpleNamespace(
        id=57, start_time=future, platform="draftkings", sport="MLB", status="PUBLISHED",
    )
    fake_result = {
        "n_requested": 500,
        "n_completed": 500,
        "inputs_hash": "abc123",
        "generated_at": future.isoformat(),
        "players": [
            {"player_id": "12345", "name": "Aaron Judge", "optimal_pct": 42.5, "appearances": 212},
        ],
    }

    import dfs.optimal_cache as ocache
    monkeypatch.setattr(ocache, "get_status", lambda plat, sport, sid: ocache.STATUS_COMPLETE)
    monkeypatch.setattr(ocache, "get_result", lambda plat, sport, sid: fake_result)

    out = await optimal_pct(
        slate_id=57,
        platform="draftkings",
        sport="MLB",
        user=SimpleNamespace(id=1),
        db=_FakeDB(slate),
    )
    assert out["data"]["status"] == "COMPLETE"
    players = out["data"]["result"]["players"]
    assert players[0]["name"] == "Aaron Judge"
    assert players[0]["optimal_pct"] == 42.5


@pytest.mark.asyncio
async def test_optimal_pct_does_not_substitute_other_metrics(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(hours=8)
    slate = SimpleNamespace(
        id=57, start_time=future, platform="draftkings", sport="MLB", status="PUBLISHED",
    )
    fake_result = {
        "players": [
            {
                "player_id": "1",
                "name": "Judge",
                "optimal_pct": 11.0,
                "appearances": 55,
                "sbme_ownership_pct": 40.0,
                "leverage": 2.1,
                "projected_fp": 12.5,
            },
        ],
    }
    import dfs.optimal_cache as ocache
    monkeypatch.setattr(ocache, "get_status", lambda *a, **k: ocache.STATUS_COMPLETE)
    monkeypatch.setattr(ocache, "get_result", lambda *a, **k: fake_result)

    out = await optimal_pct(
        slate_id=57, platform="draftkings", sport="MLB",
        user=SimpleNamespace(id=1), db=_FakeDB(slate),
    )
    pct = out["data"]["result"]["players"][0]["optimal_pct"]
    assert pct == 11.0
    assert pct != 40.0
    assert pct != 2.1
    assert pct != 12.5


@pytest.mark.asyncio
async def test_optimal_pct_normalizes_cache_key_case(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(hours=8)
    slate = SimpleNamespace(
        id=9, start_time=future, platform="draftkings", sport="MLB", status="PUBLISHED",
    )
    seen = {}

    def _status(plat, sport, sid):
        seen["key"] = (plat, sport, sid)
        return "NOT_RUN"

    import dfs.optimal_cache as ocache
    monkeypatch.setattr(ocache, "get_status", _status)
    monkeypatch.setattr(ocache, "get_result", lambda *a, **k: None)

    await optimal_pct(
        slate_id=9, platform="DraftKings", sport="mlb",
        user=SimpleNamespace(id=1), db=_FakeDB(slate),
    )
    assert seen["key"] == ("draftkings", "MLB", 9)
