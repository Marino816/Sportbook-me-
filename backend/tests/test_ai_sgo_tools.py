from unittest.mock import patch

import pytest

from assistant.tools import (
    ALLOWED_TOOLS,
    TOOL_HANDLERS,
    get_sgo_current_events,
    get_sgo_current_odds,
    get_sbme_game_environment,
)


SAMPLE_EVENT = {
    "id": "evt-ai",
    "league": "MLB",
    "status": "SCHEDULED",
    "home_team": {"name": "Cleveland", "abbreviation": "CLE"},
    "away_team": {"name": "Yankees", "abbreviation": "NYY"},
    "home_score": None,
    "away_score": None,
    "markets": [
        {"bet_type": "total", "side": "over", "fair_over_under": 8.0, "books": []},
        {"bet_type": "moneyline", "side": "home", "fair_odds": -130, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "moneyline": -130},
        ]},
        {"bet_type": "moneyline", "side": "away", "fair_odds": 110, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "moneyline": 110},
        ]},
    ],
}


@pytest.mark.asyncio
async def test_sgo_tools_are_cache_only(monkeypatch):
    called = {"fetch": 0}

    async def boom(*_a, **_k):
        called["fetch"] += 1
        raise AssertionError("AI tools must not fetch SportsGameOdds")

    monkeypatch.setattr("providers.nested_events.load_cached_or_fetch_events", boom)
    with patch("providers.nested_events.load_cached_events", return_value=[SAMPLE_EVENT]):
        events = await get_sgo_current_events(None, sport="MLB")
        odds = await get_sgo_current_odds(None, sport="MLB")
        env = await get_sbme_game_environment(None, sport="MLB")
    assert events["available"] is True
    assert odds["available"] is True
    assert env["source"] == "sbme_derived"
    assert called["fetch"] == 0


@pytest.mark.asyncio
async def test_sgo_tools_empty_cache():
    with patch("providers.nested_events.load_cached_events", return_value=[]):
        result = await get_sgo_current_events(None, sport="MLB")
    assert result["available"] is False
    assert result["events"] == []


def test_sgo_tools_registered():
    for name in (
        "get_sgo_current_events",
        "get_sgo_game_status",
        "get_sgo_current_odds",
        "get_sgo_player_props",
        "get_player_last_n",
        "get_sbme_game_environment",
    ):
        assert name in ALLOWED_TOOLS
        assert name in TOOL_HANDLERS
