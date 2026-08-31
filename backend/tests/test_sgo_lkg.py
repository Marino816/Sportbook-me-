"""Regression: SGO 429 / empty must not wipe last-known-good MLB events."""

from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from api.sgo_data import load_canonical_sb_events
from dfs.freshness import is_current_slate, is_stale_slate, slate_date_et
from projection.sgo_intelligence import _event_date_matches
from providers.sbevent import from_sdk_event


ET = ZoneInfo("America/New_York")

LKG_MLB_AUG31 = [{
    "id": "mlb-aug31-late",
    "sport": "BASEBALL",
    "league": "MLB",
    "start_time": "2026-09-01T02:10:00+00:00",
    "status": "SCHEDULED",
    "home_team": {"name": "Cleveland Guardians", "abbreviation": "CLE", "team_id": "CLE"},
    "away_team": {"name": "New York Yankees", "abbreviation": "NYY", "team_id": "NYY"},
    "players": [{
        "player_id": "JOSE_RAMIREZ_1_MLB",
        "name": "José Ramírez",
        "team_id": "CLE",
        "position": "3B",
    }],
    "markets": [],
    "bookmakers": [],
}]


@pytest.fixture(autouse=True)
def _reset_sgo_fetch_state():
    import api.sgo_data as mod

    mod._fetch_fail_until.clear()
    yield
    mod._fetch_fail_until.clear()


def _sdk_event(starts_at="2026-09-01T02:10:00+00:00"):
    names = lambda long, short: SimpleNamespace(long=long, short=short)
    home = SimpleNamespace(names=names("Cleveland Guardians", "CLE"), team_id="CLE", score=0)
    away = SimpleNamespace(names=names("New York Yankees", "NYY"), team_id="NYY", score=0)
    return SimpleNamespace(
        event_id="mlb-aug31-late",
        sport_id="BASEBALL",
        league_id="MLB",
        teams=SimpleNamespace(home=home, away=away),
        status=SimpleNamespace(
            live=False, completed=False, finalized=False,
            display_long="Scheduled",
            starts_at=starts_at,
            current_period_id="game",
        ),
        players={
            "JOSE_RAMIREZ_1_MLB": SimpleNamespace(
                player_id="JOSE_RAMIREZ_1_MLB",
                name="José Ramírez",
                first_name="José",
                last_name="Ramírez",
                team_id="CLE",
            ),
        },
        odds={},
        results=None,
    )


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


def _customer_games_for_et_date(events: list, et_date: str) -> list:
    return [e for e in events if _event_date_matches(e.get("start_time"), et_date)]


class TestUtcEtBoundaryVisibility:
    def test_same_day_mlb_event_visible_across_utc_date_line(self):
        """Sep 1 02:10 UTC is still Aug 31 ET and remains a same-day game."""
        events = _customer_games_for_et_date(LKG_MLB_AUG31, "2026-08-31")
        assert len(events) == 1
        assert events[0]["id"] == "mlb-aug31-late"
        assert _event_date_matches("2026-09-01T02:10:00+00:00", "2026-09-01") is False

    def test_current_mlb_dfs_slate_not_stale_across_utc_date_line(self, monkeypatch):
        monkeypatch.setattr("dfs.freshness._today_et", lambda: date(2026, 8, 31))
        start = datetime(2026, 9, 1, 2, 10, tzinfo=timezone.utc)
        assert slate_date_et(start) == date(2026, 8, 31)
        assert is_current_slate(start) is True
        assert is_stale_slate(start) is False

    def test_customer_slate_filter_keeps_valid_current_mlb(self, monkeypatch):
        monkeypatch.setattr("dfs.freshness._today_et", lambda: date(2026, 8, 31))
        published = [
            SimpleNamespace(id=53, sport="MLB", start_time=datetime(2026, 9, 1, 2, 10, tzinfo=timezone.utc)),
            SimpleNamespace(id=12, sport="MLB", start_time=datetime(2026, 8, 30, 23, 10, tzinfo=ET)),
        ]
        current = [s for s in published if is_current_slate(s.start_time)]
        assert [s.id for s in current] == [53]


class TestEmptyDoesNotEraseLkg:
    @pytest.mark.asyncio
    async def test_empty_upstream_keeps_lkg(self, monkeypatch):
        store = _install_redis(monkeypatch, {
            "sgo:v2:sbevents:MLB:lkg": list(LKG_MLB_AUG31),
        })
        fetch = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )

        events, source = await load_canonical_sb_events("MLB")
        assert source == "lkg"
        assert len(events) == 1
        assert events[0]["id"] == "mlb-aug31-late"
        assert "sgo:v2:sbevents:MLB" not in store
        assert store["sgo:v2:sbevents:MLB:lkg"][0]["id"] == "mlb-aug31-late"
        fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_429_keeps_lkg_and_does_not_write_empty(self, monkeypatch):
        store = _install_redis(monkeypatch, {
            "sgo:v2:sbevents:MLB:lkg": list(LKG_MLB_AUG31),
        })
        writes = []

        def tracking_rset(key, data, ttl=None):
            writes.append((key, data, ttl))
            store[key] = data

        monkeypatch.setattr("api.sgo_data._rset", tracking_rset)

        async def boom(league):
            raise RuntimeError("Error code: 429 - Rate limit exceeded")

        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=boom),
        )

        events, source = await load_canonical_sb_events("MLB")
        assert source == "lkg"
        assert [e["id"] for e in events] == ["mlb-aug31-late"]
        assert writes == []
        visible = _customer_games_for_et_date(events, "2026-08-31")
        assert len(visible) == 1

    @pytest.mark.asyncio
    async def test_429_without_lkg_returns_empty_not_fabricated(self, monkeypatch):
        _install_redis(monkeypatch, {})

        async def boom(league):
            raise RuntimeError("Error code: 429 - Rate limit exceeded")

        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=boom),
        )
        events, source = await load_canonical_sb_events("MLB")
        assert events == []
        assert source == "sportsgameodds"


class TestCustomerFacingValidData:
    @pytest.mark.asyncio
    async def test_successful_fetch_returns_boundary_game_and_writes_lkg(self, monkeypatch):
        store = _install_redis(monkeypatch, {})
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(
                get_sb_events=AsyncMock(return_value=[from_sdk_event(_sdk_event())]),
            ),
        )
        events, source = await load_canonical_sb_events("MLB")
        assert source == "sportsgameodds"
        assert events
        assert store["sgo:v2:sbevents:MLB:ttl"] == 180
        assert store["sgo:v2:sbevents:MLB:lkg:ttl"] == 6 * 3600
        assert _customer_games_for_et_date(events, "2026-08-31")
        assert events[0]["players"]

    @pytest.mark.asyncio
    async def test_live_cache_hit_does_not_fetch(self, monkeypatch):
        _install_redis(monkeypatch, {"sgo:v2:sbevents:MLB": list(LKG_MLB_AUG31)})
        fetch = AsyncMock(side_effect=AssertionError("must not fetch on live hit"))
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=fetch),
        )
        events, source = await load_canonical_sb_events("MLB")
        assert source == "cached"
        assert events[0]["id"] == "mlb-aug31-late"
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_nested_loader_uses_lkg_on_429(self, monkeypatch):
        _install_redis(monkeypatch, {"sgo:v2:sbevents:MLB:lkg": list(LKG_MLB_AUG31)})

        async def boom(league):
            raise RuntimeError("Error code: 429")

        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(get_sb_events=boom),
        )
        from providers.nested_events import load_cached_or_fetch_events

        events = await load_cached_or_fetch_events("MLB")
        assert len(events) == 1
        assert events[0]["players"]


class TestNoFakeSlatesFromSgo:
    def test_canonical_loader_does_not_create_dfs_slates(self):
        src = inspect.getsource(load_canonical_sb_events)
        assert "DFSSlate" not in src
        assert "bcdfs" not in src.lower()
        assert "slate_name" not in src
        assert "salary" not in src.lower()

    @pytest.mark.asyncio
    async def test_sgo_success_only_writes_sgo_redis_keys(self, monkeypatch):
        store = _install_redis(monkeypatch, {})
        monkeypatch.setattr(
            "api.sgo_data._canonical_event_provider",
            lambda: SimpleNamespace(
                get_sb_events=AsyncMock(return_value=[from_sdk_event(_sdk_event())]),
            ),
        )
        await load_canonical_sb_events("MLB")
        written = [k for k in store if not k.endswith(":ttl")]
        assert set(written) == {"sgo:v2:sbevents:MLB", "sgo:v2:sbevents:MLB:lkg"}
        assert all(k.startswith("sgo:v2:sbevents:") for k in written)
        assert "dfs_slates" not in store
