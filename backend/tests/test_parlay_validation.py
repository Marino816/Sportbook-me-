"""Parlay duplicate and opposing-outcome validation."""

from market_engine.parlay import build_parlay_dict, unique_valid_leg_dicts, validate_parlay_legs


def test_duplicate_moneyline_is_invalid():
    legs = [
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 103},
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 103},
    ]
    result = validate_parlay_legs(legs)
    assert result["valid"] is False
    assert any("duplicate" in e.lower() for e in result["errors"])


def test_opposing_moneylines_are_invalid():
    legs = [
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 103},
        {"event_id": "cle-det", "market": "moneyline", "selection": "Detroit Tigers", "odds": -118},
    ]
    result = validate_parlay_legs(legs)
    assert result["valid"] is False
    assert any("conflict" in e.lower() for e in result["errors"])


def test_unique_cross_game_moneylines_are_valid():
    legs = [
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 103},
        {"event_id": "nyy-bos", "market": "moneyline", "selection": "New York Yankees", "odds": -130},
    ]
    result = validate_parlay_legs(legs)
    assert result["valid"] is True


def test_payout_uses_unique_legs_only():
    dupes = [
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 100},
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 100},
        {"event_id": "nyy-bos", "market": "moneyline", "selection": "New York Yankees", "odds": 100},
    ]
    unique = unique_valid_leg_dicts(dupes)
    assert len(unique) == 2
    doubled = build_parlay_dict(dupes, stake=10)
    honest = build_parlay_dict(unique, stake=10)
    assert doubled["leg_count"] == honest["leg_count"] == 2
    assert doubled["potential_payout"] == honest["potential_payout"]


def test_conflicting_moneylines_are_dropped_from_payout():
    legs = [
        {"event_id": "cle-det", "market": "moneyline", "selection": "Cleveland Guardians", "odds": 100},
        {"event_id": "cle-det", "market": "moneyline", "selection": "Detroit Tigers", "odds": -120},
    ]
    assert len(unique_valid_leg_dicts(legs)) == 1
