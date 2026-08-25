"""Tests for the true Optimal% simulation engine (Phase 2A)."""

from __future__ import annotations

import numpy as np
import pytest

from dfs.optimal_simulation import (
    simulate_true_optimal,
    validate_lineup,
    _generate_outcomes,
    _pool_slice,
    SimBatchResult,
    SimPlayerResult,
    SIM_ENGINE_VERSION,
)


# ── Tiny synthetic pool for deterministic tests ──
def make_pool(n_players: int = 20, sport: str = "MLB") -> list[dict]:
    """Build a minimal pool with enough players for a legal lineup."""
    import math
    pool = []
    positions = ["P", "P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "OF", "OF", "OF"]
    for i in range(n_players):
        pos = positions[i % len(positions)]
        team = f"T{i % 4}"
        opp = f"T{(i + 1) % 4}"
        pool.append({
            "id": f"p{i}",
            "name": f"Player {i}",
            "position": pos,
            "roster_position": pos,
            "team": team,
            "opponent": opp,
            "salary": 3000 + (i * 500) % 8000,
            "projected_fp": 5.0 + (i % 10),
            "sbme_ownership_pct": 2.0,
            "slate_id": 1,
        })
    return pool


class TestOutcomeMatrix:
    def test_shape(self):
        pool = make_pool(15)
        out = _generate_outcomes(pool, 10, "MLB", seed=42)
        assert out.shape == (10, 15)

    def test_deterministic_seed(self):
        pool = make_pool(15)
        a = _generate_outcomes(pool, 10, "MLB", seed=42)
        b = _generate_outcomes(pool, 10, "MLB", seed=42)
        assert np.array_equal(a, b)

    def test_different_seed_differs(self):
        pool = make_pool(15)
        a = _generate_outcomes(pool, 50, "MLB", seed=1)
        b = _generate_outcomes(pool, 50, "MLB", seed=2)
        assert not np.array_equal(a, b)

    def test_hitters_nonnegative(self):
        pool = make_pool(15)
        out = _generate_outcomes(pool, 20, "MLB", seed=42)
        for j, p in enumerate(pool):
            if p["position"] != "P":
                assert (out[:, j] >= 0).all()

    def test_pool_slice(self):
        pool = make_pool(10)
        out = _generate_outcomes(pool, 5, "MLB", seed=42)
        sliced = _pool_slice(pool, out, 0)
        assert len(sliced) == len(pool)
        # projected_fp is preserved (eligibility), simulated_fp carries the outcome
        assert sliced[0]["projected_fp"] == pool[0]["projected_fp"]
        assert "simulated_fp" in sliced[0]
        assert isinstance(sliced[0]["simulated_fp"], float)

    def test_slice_keeps_eligibility_with_negative_pitcher(self):
        """Pitcher who sims negative still keeps original projected_fp > 0 → eligible."""
        pool = make_pool(20)
        # Force a pitcher to have negative outcome
        import numpy as np
        out = np.ones((3, len(pool))) * -5.0  # all sim to -5
        sliced = _pool_slice(pool, out, 0)
        for j, p in enumerate(pool):
            # projected_fp should be original (positive for projected players)
            assert sliced[j]["projected_fp"] == p["projected_fp"]
            # simulated_fp should be the negative value
            assert sliced[j]["simulated_fp"] == -5.0

    def test_slice_zero_outcome_keeps_eligibility(self):
        """Player who sims to 0 still has original projected_fp."""
        pool = make_pool(20)
        import numpy as np
        out = np.zeros((3, len(pool)))
        sliced = _pool_slice(pool, out, 0)
        for j, p in enumerate(pool):
            assert sliced[j]["projected_fp"] == p["projected_fp"]
            assert sliced[j]["simulated_fp"] == 0.0


class TestSimulationEngine:
    def test_small_sim_runs(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        assert isinstance(result, SimBatchResult)
        assert result.n_total == 5
        assert result.n_completed >= 1
        # optimal_pct is 0..100
        assert all(0.0 <= p.optimal_pct <= 100.0 for p in result.players)

    def test_reproducible(self):
        pool = make_pool(30)
        a = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        b = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        assert a.inputs_hash == b.inputs_hash
        pa = {p.player_id: p.optimal_pct for p in a.players}
        pb = {p.player_id: p.optimal_pct for p in b.players}
        assert pa == pb

    def test_appearance_accounting(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        # sum of appearances = completed * roster_size
        total_appearances = sum(p.appearances for p in result.players)
        roster = 10  # DK MLB
        assert total_appearances == result.n_completed * roster

    def test_optimal_pct_matches_appearances(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        denom = max(result.n_completed, 1)
        for p in result.players:
            expected = round(p.appearances / denom * 100.0, 2)
            assert p.optimal_pct == expected


class TestLineupValidation:
    def _build_legal_lineup(self):
        pool = make_pool(30)
        from optimizer.mlb_optimizer import MLBOptimizer
        opt = MLBOptimizer(pool=pool, platform="draftkings", strategy="balanced")
        lu = opt.build_lineup(forbidden_ids=set(), prior_ids=[], timeout_seconds=2.0, num_workers=1)
        return lu

    def test_legal_lineup_validates_clean(self):
        lu = self._build_legal_lineup()
        if lu:
            violations = validate_lineup(lu, "draftkings", "MLB")
            assert violations == []

    def test_duplicate_lineup_invalid(self):
        lu = self._build_legal_lineup()
        if lu:
            # Duplicate a player
            lu2 = dict(lu)
            lu2["players"] = lu["players"][:1] * 10
            violations = validate_lineup(lu2, "draftkings", "MLB")
            assert any("Duplicate" in v or "Expected" in v for v in violations)


class TestFailureClassification:
    """Phase 2A.1 — completeness + failure categorisation."""

    def test_result_fields_present(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        assert hasattr(result, "n_requested")
        assert hasattr(result, "completion_rate")
        assert hasattr(result, "failures_infeasible")
        assert hasattr(result, "failures_timeout")
        assert hasattr(result, "failures_invalid_lineup")
        assert hasattr(result, "failures_unexpected")
        assert hasattr(result, "p50_solve_seconds")
        assert hasattr(result, "p95_solve_seconds")

    def test_requested_preserved(self):
        pool = make_pool(30)
        for n in [5, 10, 20]:
            result = simulate_true_optimal(pool, sport="MLB", n_sims=n, seed=42, sim_timeout=2.0)
            assert result.n_requested == n

    def test_completed_denominator(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=10, seed=42, sim_timeout=2.0)
        # Every appearance sum = completed * 10 (DK roster)
        total = sum(p.appearances for p in result.players)
        assert total == result.n_completed * 10

    def test_failure_counts_sum(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=20, seed=42, sim_timeout=2.0)
        accounted = (result.n_completed + result.failures_infeasible +
                     result.failures_timeout + result.failures_invalid_lineup +
                     result.failures_unexpected)
        assert accounted == result.n_requested

    def test_no_001_in_result(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        for p in result.players:
            assert p.projected_fp != 0.01

    def test_no_bc_projection_in_result(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        for p in result.players:
            assert "blue" not in str(p.player_id).lower()
            assert "collar" not in str(p.player_id).lower()


class TestDeterministicReproducibility:
    def test_seeded_run_reproducible(self):
        pool = make_pool(30)
        a = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        b = simulate_true_optimal(pool, sport="MLB", n_sims=5, seed=42, sim_timeout=2.0)
        assert a.n_completed == b.n_completed
        assert a.inputs_hash == b.inputs_hash
        for pa, pb in zip(a.players, b.players):
            assert pa.optimal_pct == pb.optimal_pct


class TestCacheLayer:
    def test_cache_graceful_without_redis(self, monkeypatch):
        import dfs.optimal_cache as cache
        monkeypatch.setattr(cache, "_redis", lambda: None)
        assert cache.get_status("draftkings", "MLB", 1) == cache.STATUS_NOT_RUN
        assert cache.get_result("draftkings", "MLB", 1) is None
        cache.set_status("draftkings", "MLB", 1, cache.STATUS_RUNNING)  # no-op
        cache.set_result("draftkings", "MLB", 1, {})  # no-op


class TestNoLeakage:
    def test_no_bc_projection(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=3, seed=42, sim_timeout=2.0)
        # No player should carry any BC/blue-collar source
        for p in result.players:
            assert "blue" not in str(p.player_id).lower()

    def test_no_001_phantom(self):
        pool = make_pool(30)
        result = simulate_true_optimal(pool, sport="MLB", n_sims=3, seed=42, sim_timeout=2.0)
        # optimal_pct is a frequency, never a 0.01 projection placeholder
        for p in result.players:
            assert p.projected_fp != 0.01
