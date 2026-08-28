"""Unit tests for native projection BC fallback + coverage counting."""

from projection.native import apply_bc_proj_fallback, count_projected_players


def test_hitter_bc_fallback_applied_when_sgo_unavailable():
    pool = [
        {
            "id": "1",
            "name": "Hitter A",
            "position": "OF",
            "roster_position": "OF",
            "projected_fp": 0.0,
            "projection_source": "UNAVAILABLE",
            "fppg": 8.4,
        }
    ]
    out = apply_bc_proj_fallback(pool)
    assert out[0]["projected_fp"] == 8.4
    assert out[0]["projection_source"] == "BC_PROJ_FALLBACK"
    assert count_projected_players(out) == 1


def test_pitcher_without_bc_fppg_not_counted_when_bc_covers_slate():
    pool = [
        {
            "id": "p_start",
            "name": "Starter",
            "position": "P",
            "roster_position": "P",
            "projected_fp": 18.0,
            "projection_source": "SGO_FANTASY_MARKET",
            "fppg": 17.0,
            "team": "NYY",
            "salary": 9000,
        },
        {
            "id": "p1",
            "name": "Reliever",
            "position": "P",
            "roster_position": "P",
            "projected_fp": 12.0,
            "projection_source": "SGO_FANTASY_MARKET",
            "fppg": None,
            "team": "NYY",
            "salary": 3500,
        },
    ]
    out = apply_bc_proj_fallback(pool)
    assert out[1]["projected_fp"] == 12.0
    assert count_projected_players(out) == 1


def test_pitcher_bc_fallback_when_starter_fppg_present():
    pool = [
        {
            "id": "p2",
            "name": "Starter",
            "position": "SP",
            "roster_position": "SP",
            "projected_fp": 0.0,
            "projection_source": "UNAVAILABLE",
            "fppg": 18.2,
        }
    ]
    out = apply_bc_proj_fallback(pool)
    assert out[0]["projected_fp"] == 18.2
    assert out[0]["projection_source"] == "BC_PROJ_FALLBACK"
    assert count_projected_players(out) == 1


def test_sgo_hitter_not_overwritten_by_fppg():
    pool = [
        {
            "id": "2",
            "name": "Hitter B",
            "position": "SS",
            "projected_fp": 11.1,
            "projection_source": "SGO_FANTASY_MARKET",
            "fppg": 7.0,
        }
    ]
    out = apply_bc_proj_fallback(pool)
    assert out[0]["projected_fp"] == 11.1
    assert out[0]["projection_source"] == "SGO_FANTASY_MARKET"
    assert count_projected_players(out) == 1


def test_min_projected_counts_fallback_hitters():
    pool = [
        {"id": str(i), "name": f"H{i}", "position": "OF", "projected_fp": 0, "fppg": 5.0}
        for i in range(10)
    ]
    out = apply_bc_proj_fallback(pool)
    assert count_projected_players(out) == 10
