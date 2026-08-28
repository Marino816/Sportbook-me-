from unittest.mock import AsyncMock, patch

import pytest
from inspect import signature

from api.market_tools import get_live_odds
from market_engine.cache import MarketCache


def test_live_odds_accepts_league_and_optional_event_id():
    params = signature(get_live_odds).parameters
    assert "event_id" in params
    assert "league" in params
    assert params["event_id"].default != ...
    # Query default for event_id is empty string, not required
    event_q = params["event_id"].default
    assert getattr(event_q, "default", "") == "" or event_q == ""


@pytest.mark.asyncio
async def test_live_odds_lists_games_from_nested_cache():
    events = [{
        "id": "e1",
        "home_team": {"name": "Cleveland", "abbreviation": "CLE"},
        "away_team": {"name": "Yankees", "abbreviation": "NYY"},
        "markets": [
            {"bet_type": "total", "side": "over", "fair_over_under": 8.5, "books": []},
            {"bet_type": "moneyline", "side": "home", "fair_odds": -120, "books": []},
            {"bet_type": "moneyline", "side": "away", "fair_odds": 100, "books": []},
        ],
        "bookmakers": ["dk"],
    }]
    user = type("U", (), {"id": 1})()
    with patch("providers.nested_events.load_cached_or_fetch_events", new=AsyncMock(return_value=events)):
        resp = await get_live_odds(event_id="", league="MLB", slate_id=None, user=user)
    data = resp["data"]
    assert data["count"] == 1
    assert data["games"][0]["id"] == "e1"
    assert data["league"] == "MLB"


@pytest.mark.asyncio
async def test_market_cache_does_not_call_dedicated_urls():
    cache = MarketCache()
    cache._provider = type("P", (), {
        "get_odds": AsyncMock(side_effect=AssertionError("dedicated odds")),
        "get_player_props": AsyncMock(side_effect=AssertionError("dedicated props")),
        "get_fair_odds": AsyncMock(side_effect=AssertionError("fair-odds")),
        "get_consensus": AsyncMock(side_effect=AssertionError("consensus")),
    })()
    evt = {"id": "e9", "markets": [], "home_team": {}, "away_team": {}}
    with patch("providers.nested_events.find_cached_event", return_value=evt):
        data = await cache.get_event_data("e9")
    assert data["nested"]["id"] == "e9"
    assert data["odds"] is None
    cache._provider.get_odds.assert_not_called()
