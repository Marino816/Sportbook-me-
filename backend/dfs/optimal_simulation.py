"""
SB ME True Optimal-Lineup-Frequency Simulation Engine.

Phase 2A: Genuine Monte Carlo simulation where each simulation run:
1. Generates player outcomes from modeled distributions
2. Solves ONE legal optimal lineup via CP-SAT
3. Records which players appear in that lineup

Optimal% = appearances / completed_simulations × 100

This replaces the legacy per-slot top1_pct in simulate_pool().
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from optimizer.mlb_optimizer import MLBOptimizer, PLATFORM_CONFIG, _normalize_mlb_pos

logger = logging.getLogger(__name__)

SIM_ENGINE_VERSION = "sbme-optimal-sims-v1"

# Sport-appropriate variance (sigma fraction of projection).
VARIANCE = {"MLB": 0.35, "NFL": 0.4, "NBA": 0.3, "NHL": 0.4}
TEAM_CORR = {"MLB": 0.30, "NFL": 0.45, "NBA": 0.25, "NHL": 0.30}

# Performance guardrails
MAX_SIMS = 2000
CP_SAT_TIMEOUT = 10  # seconds per individual solve


@dataclass
class SimPlayerResult:
    """Per-player result from a simulation batch."""
    player_id: str
    name: str
    position: str
    team: str
    salary: int
    projected_fp: float
    appearances: int = 0
    optimal_pct: float = 0.0


@dataclass
class SimBatchResult:
    """Result of a complete simulation batch."""

    sport: str
    platform: str
    slate_id: int
    n_requested: int        # number of sims requested
    n_completed: int        # successfully built a legal lineup
    n_total: int            # total sims attempted (= n_requested)
    runtime_seconds: float
    avg_solve_seconds: float
    p50_solve_seconds: float = 0.0
    p95_solve_seconds: float = 0.0

    # ── Failure categories ──
    failures_infeasible: int = 0        # solver returned INFEASIBLE
    failures_timeout: int = 0           # solver timed out with no solution
    failures_invalid_lineup: int = 0    # solver returned a lineup that failed validation
    failures_unexpected: int = 0        # unexpected exception during this sim
    failure_message: str = ""           # detail for last failure type seen

    # ── Solution-quality categories ──
    completions_optimal: int = 0        # CP-SAT returned OPTIMAL
    completions_feasible: int = 0       # CP-SAT returned FEASIBLE (not proven optimal)

    players: list[SimPlayerResult] = field(default_factory=list)
    model_version: str = SIM_ENGINE_VERSION
    generated_at: str = ""
    inputs_hash: str = ""

    @property
    def completion_rate(self) -> float:
        d = max(self.n_requested, 1)
        return round(self.n_completed / d * 100.0, 1)

    def top_n(self, n: int = 20) -> list[SimPlayerResult]:
        return sorted(self.players, key=lambda p: p.optimal_pct, reverse=True)[:n]


def _rng(seed: Optional[int]) -> np.random.Generator:
    return np.random.default_rng(seed)


def _team_key(p: dict) -> str:
    return p.get("team") or p.get("team_id") or ""


def _is_pitcher(p: dict, sport: str = "MLB") -> bool:
    pos = (p.get("roster_position") or p.get("position") or "").upper()
    return pos == "P" or "SP" in pos or "RP" in pos


def _generate_outcomes(
    pool: list[dict],
    n_sims: int,
    sport: str,
    seed: Optional[int] = 42,
) -> np.ndarray:
    """Generate (n_sims × n_players) outcome matrix.

    Each outcome = mu × (1 + team_corr × team_factor + (1-team_corr) × individual × sigma).

    Returns (n_sims, n_players) float64 array.
    """
    var = VARIANCE.get(sport.upper(), 0.35)
    tcorr = TEAM_CORR.get(sport.upper(), 0.3)
    rng = _rng(seed)

    n_players = len(pool)
    mus = np.array([float(p.get("projected_fp") or 0.0) for p in pool], dtype=float)

    teams = sorted({_team_key(p) for p in pool})
    team_index = {t: i for i, t in enumerate(teams)}
    team_factor = rng.normal(0.0, 1.0, size=(n_sims, len(teams)))
    individual = rng.normal(0.0, 1.0, size=(n_sims, n_players))

    outcome = np.zeros((n_sims, n_players))
    for j, p in enumerate(pool):
        tf = team_factor[:, team_index[_team_key(p)]]
        if _is_pitcher(p, sport) and sport.upper() == "MLB":
            env = -tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
        else:
            env = tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
        outcome[:, j] = mus[j] * (1.0 + env)

    # Hitters: clamp to >= 0 (pitchers and others can go negative)
    for j, p in enumerate(pool):
        if not _is_pitcher(p, sport):
            outcome[:, j] = np.maximum(outcome[:, j], 0.0)

    return outcome


def _pool_slice(pool: list[dict], sim_outcomes: np.ndarray, sim_idx: int) -> list[dict]:
    """Return a copy of the pool with simulated outcome in 'simulated_fp'.

    Keeps original 'projected_fp' intact so CP-SAT's eligibility check
    (_build_maps) still sees the real SB projection and does not drop a
    valid slate player who simulated negative.  The objective function
    uses 'simulated_fp' when present; negative values are legitimate
    (pitchers can have a bad simulated outcome).
    """
    sliced = []
    for j, p in enumerate(pool):
        p_copy = dict(p)
        p_copy["simulated_fp"] = float(sim_outcomes[sim_idx, j])
        sliced.append(p_copy)
    return sliced


def simulate_true_optimal(
    pool: list[dict],
    sport: str = "MLB",
    platform: str = "draftkings",
    n_sims: int = 100,
    seed: Optional[int] = 42,
    strategy: str = "balanced",
    sim_timeout: float = 5.0,  # per-sim solver timeout (shorter than production 15s)
    progress_callback=None,
) -> SimBatchResult:
    """Run true Optimal% simulation: CP-SAT optimal lineup per sim.

    Args:
        pool: canonical player pool (must have projected_fp, salary, position, team)
        sport: MLB/NFL/NBA/NHL
        platform: draftkings or fanduel
        n_sims: number of simulation runs
        seed: RNG seed for reproducibility
        strategy: optimizer strategy (balanced for unbiased baseline)
        progress_callback: optional callable(completed, total) for progress

    Returns SimBatchResult with per-player optimal_pct.
    """
    n_sims = max(1, min(int(n_sims), MAX_SIMS))
    sport_upper = sport.upper()

    t0 = time.time()
    logger.info(
        "Optimal pct sim start: %s/%s slate, %d sims",
        sport_upper, platform, n_sims,
    )

    # ── Generate all outcomes upfront ──
    outcome_matrix = _generate_outcomes(pool, n_sims, sport_upper, seed)

    # ── Build list of eligible players (projected_fp > 0, salary > 0) ──
    eligible_indices = [
        j for j, p in enumerate(pool)
        if (p.get("salary", 0) or 0) > 0 and (p.get("projected_fp", 0) or 0) > 0
    ]

    # ── Per-player appearance tracking (by player ID) ──
    player_ids = []
    for j, p in enumerate(pool):
        pid = str(p.get("id") or p.get("name") or f"player_{j}")
        player_ids.append(pid)

    appearances = {pid: 0 for pid in player_ids}
    completed = 0
    completed_optimal = 0
    completed_feasible = 0
    failures = {"infeasible": 0, "timeout": 0, "invalid_lineup": 0, "unexpected": 0}
    solve_times = []
    failure_msg = ""

    # ── Main simulation loop ──
    # min_salary=0: the $42K floor is a production soft guideline, not a
    # mathematical requirement for Optimal% computation. Cap + roster slots
    # are sufficient constraints. Dropping it reduces CP-SAT complexity.
    # num_workers=4: single-worker caused 17-19% timeout rate on this slate
    # because the search tree is too broad for one thread within 3-5s.
    for sim_idx in range(n_sims):
        sliced = _pool_slice(pool, outcome_matrix, sim_idx)

        opt = MLBOptimizer(
            pool=sliced,
            platform=platform,
            strategy=strategy,
            locks=[],
            excludes=[],
            min_salary=0,
        )

        t_solve = time.time()
        lineup = None
        try:
            lineup = opt.build_lineup(
                forbidden_ids=set(),
                random_seed=None,
                prior_ids=[],
                timeout_seconds=sim_timeout,
                num_workers=4,
            )
        except Exception:
            failures["unexpected"] += 1
            failure_msg = f"sim {sim_idx}: unexpected exception"
            continue

        solve_s = time.time() - t_solve
        solve_times.append(solve_s)

        if lineup is None:
            # Try to distinguish timeout from infeasible.
            # After a timeout CP-SAT sometimes returns FEASIBLE if it found
            # *something* suboptimal; a None here means NO solution at all.
            # If the solve time was close to sim_timeout, classify as timeout.
            if solve_s >= sim_timeout * 0.9:
                failures["timeout"] += 1
                continue
            failures["infeasible"] += 1
            continue

        # Validate the returned lineup
        v = validate_lineup(lineup, platform, sport_upper)
        if v:
            failures["invalid_lineup"] += 1
            failure_msg = f"sim {sim_idx}: " + "; ".join(v[:3])
            continue

        completed += 1

        # Classify solution quality (OPTIMAL vs merely FEASIBLE)
        if lineup.get("solver_status") == "OPTIMAL":
            completed_optimal += 1
        else:
            completed_feasible += 1

        # Record appearances
        seen = set()
        for pl in lineup.get("players", []):
            pid = str(pl.get("id") or "")
            if pid and pid not in seen:
                appearances[pid] = appearances.get(pid, 0) + 1
                seen.add(pid)

        if progress_callback and (sim_idx + 1) % 10 == 0:
            progress_callback(completed, sim_idx + 1)

    elapsed = time.time() - t0

    # ── Build result ──
    denom = max(completed, 1)
    players_out = []
    for j, p in enumerate(pool):
        pid = player_ids[j]
        players_out.append(SimPlayerResult(
            player_id=pid,
            name=p.get("name", ""),
            position=p.get("roster_position") or p.get("position", ""),
            team=p.get("team", ""),
            salary=p.get("salary", 0),
            projected_fp=p.get("projected_fp", 0),
            appearances=appearances.get(pid, 0),
            optimal_pct=round(appearances.get(pid, 0) / denom * 100.0, 2),
        ))

    # Sort solve times for percentiles
    solve_times.sort()
    n_st = len(solve_times)

    result = SimBatchResult(
        sport=sport_upper,
        platform=platform,
        slate_id=int(pool[0].get("slate_id", 0)) if pool else 0,
        n_requested=n_sims,
        n_completed=completed,
        n_total=n_sims,
        runtime_seconds=round(elapsed, 2),
        avg_solve_seconds=round(sum(solve_times) / max(n_st, 1), 3) if n_st else 0.0,
        p50_solve_seconds=round(solve_times[int(n_st * 0.5)], 3) if n_st > 0 else 0.0,
        p95_solve_seconds=round(solve_times[min(int(n_st * 0.95), n_st - 1)], 3) if n_st > 0 else 0.0,
        failures_infeasible=failures["infeasible"],
        failures_timeout=failures["timeout"],
        failures_invalid_lineup=failures["invalid_lineup"],
        failures_unexpected=failures["unexpected"],
        failure_message=failure_msg,
        completions_optimal=completed_optimal,
        completions_feasible=completed_feasible,
        players=players_out,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    # Compute input hash for cache versioning
    result.inputs_hash = _compute_inputs_hash(pool, sport, platform, seed, n_sims, strategy)

    logger.info(
        "Optimal pct sim done: %d/%d solves (%.1f%%), %.1fs total",
        completed, n_sims, result.completion_rate, elapsed,
    )

    return result


def _compute_inputs_hash(
    pool: list[dict],
    sport: str,
    platform: str,
    seed: Optional[int],
    n_sims: int,
    strategy: str,
) -> str:
    """Stable hash of simulation inputs for cache versioning."""
    import hashlib
    import json

    # Use only projection/salary/position/team — not full pool
    fingerprint = {
        "n_players": len(pool),
        "ids": [str(p.get("id", "")) for p in pool],
        "projected_fp": [round(float(p.get("projected_fp", 0)), 1) for p in pool],
        "salaries": [int(p.get("salary", 0)) for p in pool],
        "sport": sport,
        "platform": platform,
        "seed": seed,
        "n_sims": n_sims,
        "strategy": strategy,
        "model_version": SIM_ENGINE_VERSION,
    }
    raw = json.dumps(fingerprint, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def validate_lineup(lineup: dict, platform: str = "draftkings", sport: str = "MLB") -> list[str]:
    """Validate a simulated optimal lineup. Returns list of violation strings (empty = valid)."""
    violations = []
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        return [f"Unknown platform: {platform}"]

    players = lineup.get("players", [])
    cap = cfg["salary_cap"]
    min_count = cfg["player_count"]
    slots = cfg["slots"]

    # Unique count
    if len(players) != min_count:
        violations.append(f"Expected {min_count} players, got {len(players)}")

    # Unique IDs
    ids = [p.get("id") for p in players]
    if len(set(ids)) != len(ids):
        violations.append(f"Duplicate players in lineup")

    # Salary
    total_sal = sum(p.get("salary", 0) for p in players)
    if total_sal > cap:
        violations.append(f"Salary {total_sal} > cap {cap}")

    # Positional slots (approximate — full slot validation requires eligibility)
    pos_counts = {}
    for p in players:
        pos = _normalize_mlb_pos(p.get("roster_position") or p.get("position", ""), platform)
        pos_counts[pos] = pos_counts.get(pos, 0) + 1

    for slot_name, needed in slots.items():
        available = pos_counts.get(slot_name, 0)
        # UTIL can be filled by non-P players
        if slot_name == "UTIL":
            non_p = sum(v for k, v in pos_counts.items() if k != "P")
            if non_p < needed:
                violations.append(f"Not enough non-P for UTIL: {non_p} < {needed}")
        elif available < needed:
            violations.append(f"Slot {slot_name}: {available} < {needed} needed")

    return violations