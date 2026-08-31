"""Repair Batch 4 — SportsGameOdds Rookie utilization."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.sgo_data import _sb_event_to_dict
from providers.nested_events import (
    derive_game_environment,
    extract_nested_consensus,
    extract_nested_fair_odds,
    sbevent_player_props,
    sbevent_team_props,
)
from providers.sbevent import from_sdk_event
from providers.sgo_rookie import (
    LKG_EVENT_TTL_SECONDS,
    NESTED_EVENT_TTL_SECONDS,
    ROOKIE_LEAGUE_IDS,
    SOCCER_LEAGUE_IDS,
    classify_sgo_market,
    is_full_game_period,
    is_soccer_league,
    normalize_league_id,
    parse_account_usage,
)


def test_cache_ttl_is_three_minutes():
    assert NESTED_EVENT_TTL_SECONDS == 180
    assert LKG_EVENT_TTL_SECONDS == 6 * 3600


def test_all_seventeen_rookie_league_ids():
    assert len(ROOKIE_LEAGUE_IDS) == 17
    assert set(ROOKIE_LEAGUE_IDS) == {
        "MLB", "NBA", "NCAAB", "WNBA", "NCAAF", "NFL", "EHF_EURO", "NHL", "UFC",
        "BUNDESLIGA", "EPL", "FR_LIGUE_1", "INTERNATIONAL_SOCCER", "IT_SERIE_A",
        "LA_LIGA", "MLS", "UEFA_CHAMPIONS_LEAGUE",
    }


def test_soccer_league_routing():
    assert len(SOCCER_LEAGUE_IDS) == 8
    assert set(SOCCER_LEAGUE_IDS) == {
        "BUNDESLIGA", "EPL", "FR_LIGUE_1", "INTERNATIONAL_SOCCER",
        "IT_SERIE_A", "LA_LIGA", "MLS", "UEFA_CHAMPIONS_LEAGUE",
    }
    assert normalize_league_id("UCL") == "UEFA_CHAMPIONS_LEAGUE"
    assert normalize_league_id("ligue-1") == "FR_LIGUE_1"
    assert normalize_league_id("Serie A") == "IT_SERIE_A"
    assert normalize_league_id("LaLiga") == "LA_LIGA"
    assert normalize_league_id("premier") == "EPL"
    assert is_soccer_league("EPL")
    assert is_soccer_league("ucl")
    assert not is_soccer_league("MLB")


def test_classify_team_props_vs_game_totals():
    assert classify_sgo_market(odd_id="points-home-game-ou-over", stat_entity_id="home", bet_type_id="ou") == "team_prop"
    assert classify_sgo_market(odd_id="points-away-game-ou-under", stat_entity_id="away", bet_type_id="ou") == "team_prop"
    assert classify_sgo_market(odd_id="points-all-game-ou-over", stat_entity_id="all", bet_type_id="ou") == "total"
    assert classify_sgo_market(odd_id="points-JOSE_RAMIREZ_1_MLB-game-ou-over", player_id="JOSE_RAMIREZ_1_MLB") == "player_prop"
    assert classify_sgo_market(odd_id="points-home-1h-ml-home", stat_entity_id="home", bet_type_id="ml") == "moneyline"
    assert classify_sgo_market(odd_id="points-home-game-sp-home", stat_entity_id="home", bet_type_id="sp") == "spread"


def test_period_filtering_full_game_vs_first_half():
    assert is_full_game_period("game")
    assert is_full_game_period("")
    assert is_full_game_period("ft")
    assert is_full_game_period("reg")
    assert not is_full_game_period("1h")
    assert not is_full_game_period("1q")

    evt = {
        "id": "e1",
        "home_team": {"abbreviation": "CLE"},
        "away_team": {"abbreviation": "NYY"},
        "markets": [
            {"bet_type": "total", "side": "over", "period_id": "1h", "fair_over_under": 4.5, "books": []},
            {"bet_type": "total", "side": "over", "period_id": "game", "fair_over_under": 8.5, "books": []},
            {"bet_type": "spread", "side": "home", "period_id": "game", "fair_spread": -1.5, "books": []},
        ],
    }
    env = derive_game_environment(evt)
    assert env["sbme_game_total"] == 8.5


def test_account_usage_parsing_strips_secrets():
    raw = {
        "success": True,
        "data": {
            "tier": "rookie",
            "isActive": True,
            "email": "secret@example.com",
            "keyID": "should-not-leak",
            "customerID": "cust-hidden",
            "rateLimits": {"requests-per-minute": 50, "objects-per-month": 100000, "current-entities": 37394},
        },
    }
    parsed = parse_account_usage(raw)
    assert parsed["available"] is True
    assert parsed["tier"] == "rookie"
    assert parsed["is_active"] is True
    assert parsed["rate_limits"]["requests-per-minute"] == 50
    blob = str(parsed)
    assert "secret@example.com" not in blob
    assert "should-not-leak" not in blob
    assert "cust-hidden" not in blob
    assert "email" not in parsed
    assert "keyID" not in parsed
    assert "customerID" not in parsed


def _sdk_event(*, live=False, finalized=False, odds=None, results=None):
    names = lambda long, short: SimpleNamespace(long=long, short=short)
    home = SimpleNamespace(names=names("Cleveland Guardians", "CLE"), team_id="CLE", score=3)
    away = SimpleNamespace(names=names("New York Yankees", "NYY"), team_id="NYY", score=1)
    return SimpleNamespace(
        event_id="evt-rookie",
        sport_id="BASEBALL",
        league_id="MLB",
        teams=SimpleNamespace(home=home, away=away),
        status=SimpleNamespace(
            live=live, completed=finalized, finalized=finalized,
            display_long="Final" if finalized else ("Live" if live else "Scheduled"),
            starts_at="2026-08-28T23:00:00Z",
            current_period_id="game",
        ),
        players={
            "JOSE_RAMIREZ_1_MLB": SimpleNamespace(
                player_id="JOSE_RAMIREZ_1_MLB", name="José Ramírez", first_name="José", last_name="Ramírez", team_id="CLE",
            ),
        },
        odds=odds or {},
        results=results,
    )


def test_from_sdk_maps_alt_lines_book_odds_fair_odds_open_close():
    odds = {
        "points-all-game-ou-over": SimpleNamespace(
            stat_entity_id="all",
            player_id="",
            period_id="game",
            stat_id="points",
            bet_type_id="ou",
            market_name="Total",
            fair_odds="-110",
            fair_over_under="8.5",
            book_odds="-108",
            book_over_under="8.5",
            by_bookmaker={
                "draftkings": SimpleNamespace(
                    bookmaker_id="draftkings",
                    available=True,
                    odds="-110",
                    over_under="8.5",
                    is_main_line=True,
                    opening_odds="-105",
                    opening_over_under="8.0",
                    close_odds="-110",
                    close_over_under="8.5",
                    last_updated_at="2026-08-28T20:00:00Z",
                ),
                "fanduel": SimpleNamespace(
                    bookmaker_id="fanduel",
                    available=True,
                    odds="-115",
                    over_under="9.0",
                    is_main_line=False,
                    opening_odds="-110",
                    opening_over_under="8.5",
                    close_odds=None,
                    close_over_under=None,
                    last_updated_at=None,
                ),
            },
        ),
        "points-home-game-ou-over": SimpleNamespace(
            stat_entity_id="home",
            player_id="",
            period_id="game",
            stat_id="points",
            bet_type_id="ou",
            market_name="Home Total",
            fair_odds="-105",
            fair_over_under="4.5",
            book_odds="-102",
            book_over_under="4.5",
            by_bookmaker={},
        ),
        "points-JOSE_RAMIREZ_1_MLB-game-ou-over": SimpleNamespace(
            stat_entity_id="JOSE_RAMIREZ_1_MLB",
            player_id="JOSE_RAMIREZ_1_MLB",
            period_id="game",
            stat_id="batting_hits",
            bet_type_id="ou",
            market_name="Hits",
            fair_odds="-120",
            fair_over_under="1.5",
            book_odds="-118",
            book_over_under="1.5",
            by_bookmaker={},
        ),
    }
    evt = from_sdk_event(_sdk_event(odds=odds))
    payload = _sb_event_to_dict(evt)

    total = next(m for m in payload["markets"] if m["odd_id"] == "points-all-game-ou-over")
    assert total["bet_type"] == "total"
    assert total["period_id"] == "game"
    assert total["fair_odds"] == -110
    assert total["fair_over_under"] == 8.5
    assert total["book_odds"] == -108
    books = {b["bookmaker"]: b for b in total["books"]}
    assert books["draftkings"]["is_main_line"] is True
    assert books["fanduel"]["is_main_line"] is False
    assert books["fanduel"]["over_under"] == 9.0
    assert books["draftkings"]["opening_over_under"] == 8.0
    assert books["draftkings"]["close_over_under"] == 8.5

    team = next(m for m in payload["markets"] if m["odd_id"] == "points-home-game-ou-over")
    assert team["bet_type"] == "team_prop"
    player = next(m for m in payload["markets"] if m["odd_id"].startswith("points-JOSE"))
    assert player["bet_type"] == "player_prop"
    assert player["player_name"]

    nested_team = sbevent_team_props(payload)
    assert nested_team and nested_team[0]["fair_over_under"] == 4.5
    nested_player = sbevent_player_props(payload)
    assert nested_player and nested_player[0]["fair_odds"] == -120
    fair = extract_nested_fair_odds(payload)
    assert any(row["fair_odds"] == -110 for row in fair)
    consensus = extract_nested_consensus(payload)
    assert consensus["source"] == "nested_v2_events"
    assert payload["results"] is None


def test_odd_level_is_main_line_inherited_when_books_omit_flag():
    odds = {
        "points-home-game-ml-home": SimpleNamespace(
            stat_entity_id="home",
            player_id="",
            period_id="game",
            stat_id="points",
            bet_type_id="ml",
            market_name="Home ML",
            is_main_line=True,
            fair_odds="-120",
            book_odds="-118",
            by_bookmaker={
                "draftkings": SimpleNamespace(
                    bookmaker_id="draftkings",
                    available=True,
                    odds="-120",
                    is_main_line=None,
                ),
            },
        ),
    }
    payload = _sb_event_to_dict(from_sdk_event(_sdk_event(odds=odds)))
    ml = payload["markets"][0]
    assert ml["is_main_line"] is True
    assert ml["books"][0]["is_main_line"] is True


def test_current_vs_finalized_status_and_results():
    live = from_sdk_event(_sdk_event(live=True))
    assert live.status == "LIVE"
    final = from_sdk_event(_sdk_event(
        finalized=True,
        results={"game": {"home": {"points": 7}, "away": {"points": 2}}},
    ))
    assert final.status == "FINAL"
    assert final.home_score == 7.0
    assert final.away_score == 2.0
    payload = _sb_event_to_dict(final)
    assert payload["results"]["game"]["home"]["points"] == 7
    scheduled = from_sdk_event(_sdk_event())
    assert scheduled.status == "SCHEDULED"


@pytest.mark.asyncio
async def test_nested_fetch_writes_180s_ttl(monkeypatch):
    captured = {}

    def fake_rset(key, data, ttl=None):
        captured.setdefault("calls", []).append((key, ttl, len(data) if isinstance(data, list) else 0))

    class Provider:
        async def get_sb_events(self, league):
            return [from_sdk_event(_sdk_event())]

    monkeypatch.setattr("api.sgo_data._rget", lambda key: None)
    monkeypatch.setattr("api.sgo_data._rset", fake_rset)
    monkeypatch.setattr("api.sgo_data._clear_obsolete_event_model_keys", lambda league: None)
    monkeypatch.setattr("api.sgo_data._canonical_event_provider", lambda: Provider())

    from providers.nested_events import load_cached_or_fetch_events
    events = await load_cached_or_fetch_events("MLB")
    assert events
    assert captured["calls"][0] == ("sgo:v2:sbevents:MLB", 180, 1)
    assert captured["calls"][1] == ("sgo:v2:sbevents:MLB:lkg", 6 * 3600, 1)


@pytest.mark.asyncio
async def test_sdk_current_events_pass_rookie_flags():
    captured = {}

    class FakeEvents:
        async def get(self, **kwargs):
            captured.update(kwargs)

            async def _gen():
                if False:
                    yield None
            return _gen()

    class FakeClient:
        events = FakeEvents()

    from providers.sdk_provider import SdkSgoProvider
    provider = object.__new__(SdkSgoProvider)
    provider._client = FakeClient()
    await provider._get_events("ucl", finalized=False, odds_available=True)
    assert captured["league_id"] == "UEFA_CHAMPIONS_LEAGUE"
    assert captured["include_alt_lines"] is True
    assert captured["include_open_close_odds"] is True
    assert captured["finalized"] is False
    assert captured["odds_available"] is True


@pytest.mark.asyncio
async def test_sdk_finalized_events_expand_results():
    captured = {}

    class FakeEvents:
        async def get(self, **kwargs):
            captured.update(kwargs)

            async def _gen():
                if False:
                    yield None
            return _gen()

    class FakeClient:
        events = FakeEvents()

    from providers.sdk_provider import SdkSgoProvider
    provider = object.__new__(SdkSgoProvider)
    provider._client = FakeClient()
    await provider.get_finalized_events("MLB")
    assert captured["finalized"] is True
    assert captured["odds_available"] is False
    assert captured["expand_results"] is True
    assert captured["include_alt_lines"] is True


@pytest.mark.asyncio
async def test_dedicated_urls_are_not_callable():
    from providers.sportsgameodds import SportsGameOddsProvider
    provider = SportsGameOddsProvider(api_key="x")
    for method in ("get_odds", "get_player_props", "get_fair_odds", "get_consensus", "get_scores"):
        with pytest.raises(RuntimeError, match="not used"):
            await getattr(provider, method)("evt")
