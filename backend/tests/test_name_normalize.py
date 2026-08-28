from unittest.mock import AsyncMock, patch

import pytest
from dfs.name_normalize import fold_player_name, names_equal
from projection.sgo_intelligence import _norm_name, build_sgo_intelligence


def test_fold_accented_mlb_name():
    assert fold_player_name("José Ramírez") == fold_player_name("Jose Ramirez")
    assert names_equal("José Ramírez", "Jose Ramirez")


def test_fold_does_not_fuzzy_match_distinct_players():
    assert not names_equal("Jose Ramirez", "Jose Altuve")
    assert fold_player_name("Juan Soto") != fold_player_name("Juan Uribe")


def test_intelligence_norm_uses_fold():
    assert _norm_name("José Ramírez") == fold_player_name("Jose Ramirez")


@pytest.mark.asyncio
async def test_accented_name_preserves_fantasy_market():
    events = [{
        "id": "e1",
        "markets": [{
            "player_name": "José Ramírez",
            "market_name": "Player Fantasy Score",
            "stat_id": "fantasyScore",
            "fair_over_under": 11.5,
            "books": [],
        }],
    }]
    dfs = [{"id": "dk-1", "name": "Jose Ramirez"}]
    with patch("providers.nested_events.load_cached_or_fetch_events", new=AsyncMock(return_value=events)):
        intel = await build_sgo_intelligence("MLB", dfs)
    assert intel["dk-1"]["fantasyScore"] == 11.5
    assert intel["dk-1"]["fantasyMarketLine"] == 11.5
