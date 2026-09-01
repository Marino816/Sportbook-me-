"""LineupHistory persistence uses only mapped columns."""

import inspect
import pytest
from models.domain import LineupHistory
from models.schemas import LineupHistorySaveRequest, OptimizerSettings
from api.router import lineup_history_from_save, num_lineups_from_settings, run_optimizer, save_lineup_history


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


def test_save_request_binds_lineups_and_current_user():
    body = LineupHistorySaveRequest(
        sport="MLB",
        platform="draftkings",
        slate_id=57,
        strategy="balanced",
        lineups=[{
            "total_salary": 49200,
            "projected_score": 88.1,
            "players": [
                {"id": "GERRIT_COLE_1_MLB", "name": "Gerrit Cole", "salary": 9500, "projected_fp": 18.6},
            ],
        }],
    )
    row = lineup_history_from_save(4, body)
    assert row.user_id == 4
    assert row.sport == "MLB"
    assert row.platform == "draftkings"
    assert row.slate_id == 57
    assert row.strategy == "balanced"
    assert row.lineup_count == 1
    assert row.player_count == 1
    assert row.data_mode == "native"
    assert row.lineups_json[0]["players"][0]["name"] == "Gerrit Cole"
    other = lineup_history_from_save(99, body)
    assert other.user_id == 99
    assert other.user_id != row.user_id


def test_save_endpoint_uses_typed_body_not_bare_dict():
    src = inspect.getsource(save_lineup_history)
    assert "LineupHistorySaveRequest" in src
    assert "lineup_history_from_save(user.id, body)" in src
    assert "wrap_data({\"id\": hist.id, \"saved\": True})" in src or 'saved": True' in src


def test_num_lineups_from_settings_honors_ten():
    assert num_lineups_from_settings({"num_lineups": 10}) == 10
    assert num_lineups_from_settings(OptimizerSettings(num_lineups=10)) == 10
    assert num_lineups_from_settings({"lineup_count": 10}) == 10
    assert num_lineups_from_settings({}) == 1


def test_optimizer_passes_requested_count_to_generator():
    src = inspect.getsource(run_optimizer)
    assert "requested_lineups = num_lineups_from_settings(request.settings)" in src
    assert "opt.generate(count=requested_lineups" in src
