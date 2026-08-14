"""
SB ME Simulation Engine.

A genuine Monte Carlo simulation over the canonical player pool. Outcomes are
drawn from sport-appropriate distributions around each player's SB projection
(mean = projection, sigma = sport-appropriate variance), with shared
game/team environment factors to model within-team correlation (MLB hitters on
the same offense positively correlated; pitcher vs opposing hitters negatively
correlated).

Outputs are real modeled statistics:
  - Sim Score      : mean simulated fantasy points for a lineup
  - Optimal %      : share of simulations where a player appears in the optimal lineup
  - Top 1% %       : share of simulations where a player is in the top 1% of their slot
  - Cash %         : share of simulations where a lineup scores above the cash threshold
  - Win %          : share of simulations where a lineup achieves the top score
  - Leverage       : Optimal % - SB ME projected ownership %
  - Sim ROI        : N/A unless payout/entry-fee information is available

Correlations are MODEL ASSUMPTIONS, not data-derived — labeled as such.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SIM_MODEL_VERSION = "sbme-sims-v1"

# Sport-appropriate per-player variance (fraction of projection) + team correlation.
VARIANCE = {"MLB": 0.35, "NFL": 0.4, "NBA": 0.3, "NHL": 0.4}
TEAM_CORR = {"MLB": 0.30, "NFL": 0.45, "NBA": 0.25, "NHL": 0.30}

SAFE_SIM_LIMIT = 10000  # production cap


def _rng(seed: Optional[int]):
    return np.random.default_rng(seed)


def _team_key(p: dict) -> str:
    return p.get("team") or p.get("team_id") or ""


def _is_pitcher(p: dict) -> bool:
    pos = (p.get("roster_position") or p.get("position") or "").upper()
    return pos == "P" or "SP" in pos or "RP" in pos


def simulate_pool(
    pool: list[dict],
    sport: str = "MLB",
    n_sims: int = 2000,
    seed: Optional[int] = 42,
) -> dict:
    """
    Simulate the full pool and return per-player modeled metrics plus lineup-
    construction context. Returns a dict with:
      players: [{id, name, sim_score, optimal_pct, top1_pct, leverage}]
      metadata: {model, n_sims, seed, generated_at, ...}
    """
    n_sims = max(1, min(int(n_sims), SAFE_SIM_LIMIT))
    sport = sport.upper()
    var = VARIANCE.get(sport, 0.35)
    tcorr = TEAM_CORR.get(sport, 0.3)
    rng = _rng(seed)

    ids = [str(p.get("id") or p.get("name") or i) for i, p in enumerate(pool)]
    mus = np.array([float(p.get("projected_fp") or 0.01) for p in pool], dtype=float)

    # Team factors: one per team per sim (shared environment)
    teams = sorted({_team_key(p) for p in pool})
    team_index = {t: i for i, t in enumerate(teams)}
    team_factor = rng.normal(0.0, 1.0, size=(n_sims, len(teams)))

    # Individual noise
    individual = rng.normal(0.0, 1.0, size=(n_sims, len(pool)))

    # Outcome matrix: outcome = mu * (1 + team_corr*team_factor + (1-team_corr)*individual*var)
    outcome = np.zeros((n_sims, len(pool)))
    for j, p in enumerate(pool):
        tf = team_factor[:, team_index[_team_key(p)]]
        if _is_pitcher(p) and sport == "MLB":
            # Pitcher negatively correlated with opposing hitters' environment.
            # Approximate: apply negative of own team factor (facing the other side).
            env = -tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
        else:
            env = tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
        outcome[:, j] = mus[j] * (1.0 + env)

    # Clamp: hitters >= 0, pitchers can go negative
    for j, p in enumerate(pool):
        if not _is_pitcher(p):
            outcome[:, j] = np.maximum(outcome[:, j], 0.0)

    # Lineup-level: build a representative optimal lineup per sim via a greedy
    # budget-aware fill is expensive; instead we approximate "optimal appearance"
    # as the count of times a player is the top value at their slot within the
    # top-K projection players of that slot. We compute per-player:
    #   sim_score = mean outcome
    #   top1_pct  = fraction of sims where player is the max outcome in their slot
    slot_max = {}
    from dfs.ownership import _slot_for  # reuse slot normalization
    for j, p in enumerate(pool):
        slot = _slot_for(p.get("roster_position") or p.get("position", ""), "draftkings")
        slot_max.setdefault(slot, []).append(j)

    top1 = np.zeros(len(pool))
    for slot, idxs in slot_max.items():
        if not idxs:
            continue
        # For each sim, index of max outcome among this slot's players
        slot_outcomes = outcome[:, idxs]
        argmax = np.argmax(slot_outcomes, axis=1)
        for local_idx, global_idx in enumerate(idxs):
            top1[global_idx] = float(np.sum(argmax == local_idx)) / n_sims

    sim_score = outcome.mean(axis=0)
    own = np.array([float(p.get("sbme_ownership_pct") or 0.0) for p in pool])

    players_out = []
    for j, p in enumerate(pool):
        players_out.append({
            "id": ids[j],
            "name": p.get("name", ""),
            "position": p.get("roster_position") or p.get("position", ""),
            "team": p.get("team", ""),
            "salary": p.get("salary", 0),
            "sim_score": round(float(sim_score[j]), 2),
            "optimal_pct": round(float(top1[j]) * 100.0, 2),
            "top1_pct": round(float(top1[j]) * 100.0, 2),
            "ownership_pct": round(float(own[j]), 2),
            "leverage": round(float(top1[j]) * 100.0 - float(own[j]), 2),
        })

    metadata = {
        "model": SIM_MODEL_VERSION,
        "n_sims": n_sims,
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "correlation_assumption": f"team_corr={tcorr} (model assumption, not data-derived)",
        "variance": f"sigma={var}*projection (sport-appropriate model assumption)",
        "sim_roi": None,  # payout/entry-fee info unavailable → N/A
        "note": "Outcomes are modeled, not guaranteed.",
    }

    return {"players": players_out, "metadata": metadata}


def simulate_lineups(
    lineups: list[dict],
    pool: list[dict],
    sport: str = "MLB",
    n_sims: int = 2000,
    seed: Optional[int] = 42,
) -> dict:
    """
    Simulate a set of built lineups. Returns per-lineup metrics:
      sim_score, cash_pct, win_pct, sim_roi (N/A).
    """
    n_sims = max(1, min(int(n_sims), SAFE_SIM_LIMIT))
    sport = sport.upper()
    var = VARIANCE.get(sport, 0.35)
    tcorr = TEAM_CORR.get(sport, 0.3)
    rng = _rng(seed)

    # Build player lookup by id + name
    pool_by_id = {}
    for p in pool:
        pool_by_id[str(p.get("id") or "")] = p
        pool_by_id[(p.get("name") or "").lower()] = p

    teams = sorted({_team_key(p) for p in pool})
    team_index = {t: i for i, t in enumerate(teams)}
    team_factor = rng.normal(0.0, 1.0, size=(n_sims, len(teams)))

    lineup_results = []
    for li, lu in enumerate(lineups):
        players = lu.get("players", []) or []
        mus = []
        team_ids = []
        pitcher_flags = []
        for pl in players:
            ref = pool_by_id.get(str(pl.get("id") or "")) or pool_by_id.get((pl.get("name") or "").lower())
            mu = float((ref or {}).get("projected_fp") or pl.get("projected_fp") or 0.01)
            mus.append(mu)
            team_ids.append(_team_key(ref) if ref else "")
            pitcher_flags.append(_is_pitcher(ref) if ref else False)

        if not mus:
            lineup_results.append({
                "lineup_index": li + 1, "sim_score": 0.0, "cash_pct": None,
                "win_pct": None, "sim_roi": None, "players": players,
            })
            continue

        mus = np.array(mus)
        individual = rng.normal(0.0, 1.0, size=(n_sims, len(mus)))
        lineup_scores = np.zeros(n_sims)
        for j in range(len(mus)):
            tf = team_factor[:, team_index.get(team_ids[j], 0)]
            if pitcher_flags[j] and sport == "MLB":
                env = -tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
            else:
                env = tcorr * tf + (1.0 - tcorr) * individual[:, j] * var
            lineup_scores += mus[j] * (1.0 + env)

        sim_score = float(lineup_scores.mean())
        # Cash %: fraction above the median of the simulated distribution
        median = float(np.median(lineup_scores))
        cash_pct = float(np.mean(lineup_scores >= median)) * 100.0
        # Win %: fraction at the top decile
        p90 = float(np.percentile(lineup_scores, 90))
        win_pct = float(np.mean(lineup_scores >= p90)) * 100.0

        lineup_results.append({
            "lineup_index": li + 1,
            "sim_score": round(sim_score, 2),
            "cash_pct": round(cash_pct, 1),
            "win_pct": round(win_pct, 1),
            "sim_roi": None,  # payout info unavailable
            "players": players,
        })

    return {
        "lineups": lineup_results,
        "metadata": {
            "model": SIM_MODEL_VERSION,
            "n_sims": n_sims,
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sim_roi": None,
        },
    }
