from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.player_stats import resolve_sgo_player_id, compute_last_n
from scoring import ScoringPlatform


class _Row:
    def __init__(self, *, provider_player_id="", sbme_player_id=None, player_name="", team=""):
        self.provider_player_id = provider_player_id
        self.sbme_player_id = sbme_player_id
        self.player_name = player_name
        self.team = team


class _Result:
    def __init__(self, row=None):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _DB:
    def __init__(self, row=None):
        self._row = row
        self.executed = 0

    async def execute(self, _q):
        self.executed += 1
        return _Result(self._row)


@pytest.mark.asyncio
async def test_resolve_passes_through_sgo_shaped_id():
    with patch("providers.nested_events.load_cached_events", return_value=[]):
        sgo_id, reason = await resolve_sgo_player_id(_DB(), "JOSE_RAMIREZ_1_MLB")
    assert sgo_id == "JOSE_RAMIREZ_1_MLB"
    assert reason == ""


@pytest.mark.asyncio
async def test_resolve_unmatched_returns_reason():
    with patch("providers.nested_events.load_cached_events", return_value=[]):
        sgo_id, reason = await resolve_sgo_player_id(_DB(), "401234", name="Nobody", team="XYZ")
    assert sgo_id is None
    assert "reconciled" in reason.lower() or "matched" in reason.lower() or "unavailable" in reason.lower()


@pytest.mark.asyncio
async def test_resolve_from_cached_event_name():
    events = [{
        "id": "e1",
        "home_team": {"abbreviation": "CLE", "team_id": "CLE"},
        "away_team": {"abbreviation": "NYY", "team_id": "NYY"},
        "players": [{"player_id": "JOSE_RAMIREZ_1_MLB", "name": "José Ramírez", "team_id": "CLE"}],
    }]
    with patch("providers.nested_events.load_cached_events", return_value=events):
        sgo_id, reason = await resolve_sgo_player_id(_DB(), "dk-99", name="Jose Ramirez", team="CLE")
    assert sgo_id == "JOSE_RAMIREZ_1_MLB"
    assert reason == ""


class _FakeProvider:
    def __init__(self, events):
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get_events(self, league_id="MLB", extra_params=None):
        return self._events


@pytest.mark.asyncio
async def test_last_n_filters_non_finalized_and_missing_results():
    events = [
        {"status": {"finalized": False}, "results": {"game": {"hits": 1}}},
        {"status": {"finalized": True}, "results": {}},
        {"status": {"finalized": True}, "results": {"game": {"hits": 2}}},
    ]
    fake_log = MagicMock()
    fake_log.player_id = "JOSE_RAMIREZ_1_MLB"
    fake_log.player_name = "José Ramírez"
    fake_log.platform = "draftkings"
    fake_log.sport = "MLB"
    fake_log.player_role = "hitter"
    fake_log.scoring_mode = MagicMock(value="exact")
    fake_log.n = 1
    fake_log.average_fp = 8.0
    fake_log.min_fp = 8.0
    fake_log.max_fp = 8.0
    fake_log.average_is_exact = True
    fake_log.global_missing_fields = []
    game = MagicMock()
    game.date = "2026-08-01"
    game.event_id = "e3"
    game.opponent = "NYY"
    game.home_away = "home"
    game.result.fantasy_points = 8.0
    game.result.scoring_mode = MagicMock(value="exact")
    game.result.is_exact = True
    game.result.missing_fields = []
    game.result.calculated_from = "results"
    game.result.raw_stats = {"hits": 2}
    fake_log.games = [game]

    with patch("providers.nested_events.load_cached_events", return_value=[]), \
         patch("providers.sportsgameodds.SportsGameOddsProvider", return_value=_FakeProvider(events)), \
         patch("api.player_stats.build_game_log", new=AsyncMock(return_value=fake_log)) as mock_log:
        payload = await compute_last_n(
            _DB(), "JOSE_RAMIREZ_1_MLB", scoring_platform=ScoringPlatform.DRAFTKINGS,
        )
        passed = mock_log.await_args.args[0]
        assert len(passed) == 1
        assert passed[0]["results"]["game"]["hits"] == 2
    assert payload["available"] is True
    assert payload["games"][0]["fantasy_points"] == 8.0


@pytest.mark.asyncio
async def test_provider_player_id_is_never_treated_as_sgo_id():
    """DK/FD/Blue Collar site IDs must not be forwarded to SGO historical."""
    for site_id in ("401234", "bc_player_99", "dk_16001342", "fd-888777"):
        row = _Row(provider_player_id=site_id, sbme_player_id=site_id, player_name="Nobody", team="XYZ")
        with patch("providers.nested_events.load_cached_events", return_value=[]):
            sgo_id, reason = await resolve_sgo_player_id(_DB(row), site_id)
        assert sgo_id is None, site_id
        assert reason


@pytest.mark.asyncio
async def test_provider_id_does_not_trigger_sgo_historical_fetch():
    row = _Row(provider_player_id="401234", sbme_player_id="401234")
    fetch = AsyncMock(side_effect=AssertionError("must not call SGO with a DFS site id"))

    class _Boom(_FakeProvider):
        async def get_events(self, league_id="MLB", extra_params=None):
            await fetch()
            return []

    with patch("providers.nested_events.load_cached_events", return_value=[]), \
         patch("providers.sportsgameodds.SportsGameOddsProvider", return_value=_Boom([])):
        payload = await compute_last_n(_DB(row), "401234")
    assert payload["available"] is False
    assert payload["games"] == []
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_reconciled_sbme_player_id_used_when_sgo_shaped():
    row = _Row(
        provider_player_id="401234",
        sbme_player_id="JOSE_RAMIREZ_1_MLB",
        player_name="Jose Ramirez",
        team="CLE",
    )
    with patch("providers.nested_events.load_cached_events", return_value=[]):
        sgo_id, reason = await resolve_sgo_player_id(_DB(row), "401234")
    assert sgo_id == "JOSE_RAMIREZ_1_MLB"
    assert reason == ""


@pytest.mark.asyncio
async def test_last_n_unavailable_history():
    with patch("providers.nested_events.load_cached_events", return_value=[]), \
         patch("providers.sportsgameodds.SportsGameOddsProvider", return_value=_FakeProvider([])), \
         patch("api.player_stats.build_game_log", new=AsyncMock(return_value=None)):
        payload = await compute_last_n(_DB(), "JOSE_RAMIREZ_1_MLB")
    assert payload["available"] is False
    assert payload["games"] == []
