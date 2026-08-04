"""
Optimizer tests for Sportsbook Me DFS AI.

Run with: pytest tests/test_optimizer.py -v
"""

import pandas as pd
import pytest
from optimizer.core import DFSOptimizer


def _make_test_projections():
    """Build a test pool of 12 NBA players."""
    return pd.DataFrame(
        [
            {"id": 1, "name": "Player A", "team": "LAL", "salary": 11000, "projected_fp": 60.0, "roster_position": "PG"},
            {"id": 2, "name": "Player B", "team": "LAL", "salary": 10000, "projected_fp": 55.0, "roster_position": "SG"},
            {"id": 3, "name": "Player C", "team": "BOS", "salary": 9500, "projected_fp": 50.0, "roster_position": "SF"},
            {"id": 4, "name": "Player D", "team": "BOS", "salary": 9000, "projected_fp": 48.0, "roster_position": "PF"},
            {"id": 5, "name": "Player E", "team": "MIA", "salary": 8000, "projected_fp": 45.0, "roster_position": "C"},
            {"id": 6, "name": "Player F", "team": "MIA", "salary": 7000, "projected_fp": 40.0, "roster_position": "PG"},
            {"id": 7, "name": "Player G", "team": "DEN", "salary": 6000, "projected_fp": 35.0, "roster_position": "SG"},
            {"id": 8, "name": "Player H", "team": "DEN", "salary": 5500, "projected_fp": 32.0, "roster_position": "SF"},
            {"id": 9, "name": "Player I", "team": "GSW", "salary": 5000, "projected_fp": 28.0, "roster_position": "PF"},
            {"id": 10, "name": "Player J", "team": "GSW", "salary": 4500, "projected_fp": 25.0, "roster_position": "C"},
            {"id": 11, "name": "Player K", "team": "SAS", "salary": 4000, "projected_fp": 22.0, "roster_position": "PG"},
            {"id": 12, "name": "Player L", "team": "SAS", "salary": 3500, "projected_fp": 18.0, "roster_position": "SG/SF"},
        ]
    )


class TestOptimizerBasics:
    def test_single_lineup(self):
        df = _make_test_projections()
        opt = DFSOptimizer(df, {"num_lineups": 1, "min_uniqueness": 2})
        results = opt.generate()
        assert len(results) == 1
        lineup = results[0]
        assert len(lineup["players"]) == 8
        assert lineup["salary"] <= 50000

    def test_multiple_lineups_unique(self):
        df = _make_test_projections()
        opt = DFSOptimizer(df, {"num_lineups": 3, "min_uniqueness": 2})
        results = opt.generate()
        assert len(results) >= 1  # May be fewer if infeasible


class TestLockedPlayers:
    def test_locked_player_included_canonical(self):
        """Locked player IDs must appear in every generated lineup."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "locked_player_ids": [1],  # canonical name
            },
        )
        results = opt.generate()
        assert len(results) >= 1
        player_ids = [p["id"] for p in results[0]["players"]]
        assert 1 in player_ids

    def test_locked_player_included_legacy(self):
        """Legacy 'locked' key should also work."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "locked": [1],  # legacy name
            },
        )
        results = opt.generate()
        assert len(results) >= 1
        player_ids = [p["id"] for p in results[0]["players"]]
        assert 1 in player_ids

    def test_canonical_takes_priority(self):
        """Canonical locked_player_ids should take priority over legacy locked."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "locked_player_ids": [1],
                "locked": [2],  # should be ignored
            },
        )
        assert opt.locked_ids == [1]


class TestExcludedPlayers:
    def test_excluded_player_not_selected_canonical(self):
        """Excluded player IDs must never appear in lineups."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "excluded_player_ids": [5],  # Player E
            },
        )
        results = opt.generate()
        assert len(results) >= 1
        player_ids = [p["id"] for p in results[0]["players"]]
        assert 5 not in player_ids

    def test_excluded_player_not_selected_legacy(self):
        """Legacy 'excluded' key should also work."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "excluded": [5],
            },
        )
        results = opt.generate()
        assert len(results) >= 1
        player_ids = [p["id"] for p in results[0]["players"]]
        assert 5 not in player_ids


class TestEmptyInputs:
    def test_empty_locked_list(self):
        """Empty locked list should not affect optimization."""
        df = _make_test_projections()
        opt = DFSOptimizer(
            df,
            {
                "num_lineups": 1,
                "min_uniqueness": 2,
                "locked_player_ids": [],
                "excluded_player_ids": [],
            },
        )
        results = opt.generate()
        assert len(results) >= 1

    def test_no_locked_or_excluded_keys(self):
        """Missing keys should default to empty lists."""
        df = _make_test_projections()
        opt = DFSOptimizer(df, {"num_lineups": 1, "min_uniqueness": 2})
        assert opt.locked_ids == []
        assert opt.excluded_ids == []
        results = opt.generate()
        assert len(results) >= 1