from providers.nested_events import (
    american_implied_prob,
    attach_environment_to_pool,
    derive_game_environment,
    environments_by_team,
    extract_research_props,
    looks_like_sgo_player_id,
    resolve_sgo_id_from_events,
)


def _evt(**kwargs):
    base = {
        "id": "evt1",
        "status": "SCHEDULED",
        "home_team": {"name": "Cleveland Guardians", "abbreviation": "CLE", "team_id": "CLE"},
        "away_team": {"name": "New York Yankees", "abbreviation": "NYY", "team_id": "NYY"},
        "players": [
            {"player_id": "JOSE_RAMIREZ_1_MLB", "name": "José Ramírez", "team_id": "CLE"},
            {"player_id": "JUAN_SOTO_6_MLB", "name": "Juan Soto", "team_id": "NYY"},
        ],
        "markets": [],
        "bookmakers": ["draftkings", "fanduel"],
    }
    base.update(kwargs)
    return base


def test_american_implied_prob():
    assert round(american_implied_prob(150), 4) == 0.4
    assert round(american_implied_prob(-200), 4) == round(200 / 300, 4)


def test_implied_team_total_spread_and_total():
    evt = _evt(markets=[
        {"bet_type": "total", "side": "over", "fair_over_under": 8.5, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "over_under": 8.5},
        ]},
        {"bet_type": "spread", "side": "home", "fair_spread": -1.5, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "spread": -1.5},
        ]},
        {"bet_type": "moneyline", "side": "home", "fair_odds": -150, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "moneyline": -150},
        ]},
        {"bet_type": "moneyline", "side": "away", "fair_odds": 130, "books": [
            {"bookmaker": "dk", "available": True, "is_main_line": True, "moneyline": 130},
        ]},
    ])
    env = derive_game_environment(evt)
    assert env["source"] == "sbme_derived"
    assert env["sbme_game_total"] == 8.5
    assert env["sbme_implied_total_method"] == "spread_and_total"
    # total/2 - spread/2 = 4.25 - (-1.5)/2 = 4.25 + 0.75 = 5.0
    assert env["sbme_implied_team_total_home"] == 5.0
    assert env["sbme_implied_team_total_away"] == 3.5
    assert env["sbme_home_win_prob_raw"] is not None
    assert env["sbme_home_win_prob_devig"] is not None


def test_implied_team_total_requires_spread():
    """Moneyline win probability is not a scoring share — totals stay unavailable."""
    evt = _evt(markets=[
        {"bet_type": "total", "side": "over", "fair_over_under": 10.0, "books": []},
        {"bet_type": "moneyline", "side": "home", "fair_odds": -200, "books": []},
        {"bet_type": "moneyline", "side": "away", "fair_odds": 150, "books": []},
    ])
    env = derive_game_environment(evt)
    assert env["sbme_game_total"] == 10.0
    assert env["sbme_home_win_prob_devig"] is not None
    assert env["sbme_away_win_prob_devig"] is not None
    assert env["sbme_implied_team_total_home"] is None
    assert env["sbme_implied_team_total_away"] is None
    assert env["sbme_implied_total_method"] is None
    by_team = environments_by_team([evt])
    assert by_team["CLE"]["sbme_team_win_prob_devig"] is not None
    assert by_team["CLE"]["sbme_implied_team_total"] is None


def test_research_props_not_converted_to_fp():
    evt = _evt(markets=[
        {"bet_type": "player_prop", "player_id": "JOSE_RAMIREZ_1_MLB", "player_name": "José Ramírez",
         "market_name": "Hits", "stat_id": "hits", "fair_over_under": 1.5, "books": []},
        {"bet_type": "player_prop", "player_id": "JOSE_RAMIREZ_1_MLB", "player_name": "José Ramírez",
         "market_name": "Home Runs", "stat_id": "home_runs", "fair_over_under": 0.5, "books": []},
    ])
    props = extract_research_props(evt)
    folded = next(iter(props.values()))
    assert folded["hits_line"] == 1.5
    assert folded["hr_line"] == 0.5
    assert "fantasy" not in folded["note"].lower() or "not" in folded["note"].lower()


def test_resolve_sgo_id_exact_folded_name():
    events = [_evt()]
    assert resolve_sgo_id_from_events(events, name="Jose Ramirez", team="CLE") == "JOSE_RAMIREZ_1_MLB"


def test_resolve_sgo_id_ambiguous_without_team():
    events = [_evt(players=[
        {"player_id": "A_MLB", "name": "John Smith", "team_id": "CLE"},
        {"player_id": "B_MLB", "name": "John Smith", "team_id": "NYY"},
    ])]
    assert resolve_sgo_id_from_events(events, name="John Smith") is None
    assert resolve_sgo_id_from_events(events, name="John Smith", team="NYY") == "B_MLB"


def test_looks_like_sgo_player_id():
    assert looks_like_sgo_player_id("JOSE_RAMIREZ_1_MLB")
    assert not looks_like_sgo_player_id("401234")
    assert not looks_like_sgo_player_id("Jose Ramirez")
    assert not looks_like_sgo_player_id("bc_player_99")
    assert not looks_like_sgo_player_id("dk_16001342")
    assert not looks_like_sgo_player_id("fd-12345678")


def test_attach_environment_does_not_gate_eligibility():
    pool = [{"id": "dk-1", "name": "José Ramírez", "team": "CLE", "projected_fp": 0.0}]
    attach_environment_to_pool(pool, [_evt(markets=[
        {"bet_type": "total", "side": "over", "fair_over_under": 8.5, "books": []},
        {"bet_type": "spread", "side": "home", "fair_spread": -1.0, "books": []},
        {"bet_type": "moneyline", "side": "home", "fair_odds": -120, "books": []},
        {"bet_type": "moneyline", "side": "away", "fair_odds": 100, "books": []},
    ])])
    assert pool[0]["sgo_player_id"] == "JOSE_RAMIREZ_1_MLB"
    assert pool[0]["sbme_environment_source"] == "sbme_derived"
    assert pool[0]["projected_fp"] == 0.0
