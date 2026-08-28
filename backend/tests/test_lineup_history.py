"""LineupHistory persistence uses only mapped columns."""

import pytest
from models.domain import LineupHistory


def test_lineup_history_constructs_with_mapped_fields():
    row = LineupHistory(
        user_id=1,
        sport="MLB",
        platform="draftkings",
        slate_id=42,
        strategy="balanced",
        lineup_count=2,
        player_count=10,
        total_salary=49800,
        projected_score=112.4,
        data_mode="native",
        lineups_json=[{"players": []}],
    )
    assert row.user_id == 1
    assert row.slate_id == 42
    assert row.data_mode == "native"


def test_lineup_history_rejects_unmapped_slate_metadata():
    with pytest.raises(TypeError):
        LineupHistory(
            user_id=1,
            slate_name="Main",
            slate_date="2026-08-28",
            game_count=7,
        )
