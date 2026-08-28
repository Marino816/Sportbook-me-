"""
SB ME Top Stacks Engine.

Generates legitimate stack combinations from the canonical pool based on
platform roster rules (MLB first). A stack is a set of same-team hitters
(5-man, 4-man, 3-man, and secondary stacks) plus optional bring-back.

Stack ownership is computed from the SB ME ownership model (sum of member
ownership) — NOT fabricated. Optimal stack appearance is derived from
simulations where available; otherwise N/A.

Implied team total is an SB ME derived field (sbme_implied_team_total) from
nested SGO moneyline/total/spread when present. It is not a provider fact
and is not a stack eligibility requirement.
"""

from __future__ import annotations
import logging
from itertools import combinations
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

STACK_MODEL_VERSION = "sbme-stacks-v1"

# DK MLB roster allows up to 5 hitters from one team.
MAX_HITTERS_PER_TEAM = 5


def _is_pitcher(p: dict) -> bool:
    pos = (p.get("roster_position") or p.get("position") or "").upper()
    return pos == "P" or "SP" in pos or "RP" in pos


def _rating(projection: float, value: float, leverage: float) -> str:
    """Composite rating from stack projection + value + leverage."""
    # Heuristic 0-100 score, then letter grade.
    score = 0.0
    score += max(0.0, projection) * 0.6
    score += max(0.0, value) * 30.0
    score += max(-20.0, min(20.0, leverage)) * 1.0
    if score >= 160:
        return "A+"
    if score >= 140:
        return "A"
    if score >= 120:
        return "B"
    if score >= 100:
        return "C"
    return "D"


def build_top_stacks(
    pool: list[dict],
    sport: str = "MLB",
    platform: str = "draftkings",
    sim_metrics: Optional[dict] = None,
    limit_per_team: int = 4,
) -> dict:
    """
    Build top stacks. Returns {stacks: [...], metadata: {...}}.

    sim_metrics: optional dict from dfs.simulation.simulate_pool, mapping
    player id → optimal_pct, used to compute Optimal Stack %.
    """
    sport = sport.upper()
    # Group hitters by team
    teams: dict[str, list[dict]] = {}
    for p in pool:
        if _is_pitcher(p):
            continue
        team = p.get("team") or p.get("team_id") or ""
        if not team:
            continue
        teams.setdefault(team, []).append(p)

    # Sort each team's hitters by projection desc
    for t in teams:
        teams[t].sort(key=lambda p: float(p.get("projected_fp") or 0), reverse=True)

    # Build sim lookup
    sim_by_id: dict[str, float] = {}
    if sim_metrics:
        for sp in sim_metrics.get("players", []):
            key = str(sp.get("id") or "").lower() or (sp.get("name") or "").lower()
            sim_by_id[key] = float(sp.get("optimal_pct") or 0.0)

    stacks = []
    stack_sizes = [5, 4, 3]

    for team, hitters in teams.items():
        top = hitters[:MAX_HITTERS_PER_TEAM]
        opp = (top[0].get("opponent") or "") if top else ""
        for size in stack_sizes:
            if len(top) < size:
                continue
            # Limit combinations to a manageable, meaningful set
            combos = list(combinations(top, size))
            # Prioritize top-projection combos; keep the first `limit_per_team`
            combos = combos[: min(len(combos), limit_per_team)]
            for combo in combos:
                proj = round(sum(float(p.get("projected_fp") or 0) for p in combo), 1)
                sal = sum(int(p.get("salary") or 0) for p in combo)
                value = round((proj / (sal / 1000.0)), 2) if sal > 0 else 0.0
                ownership = round(sum(float(p.get("sbme_ownership_pct") or 0) for p in combo), 2)
                leverage = round(sum(float(p.get("leverage") or 0) for p in combo), 2)
                optimal = None
                if sim_metrics:
                    opt = sum(
                        sim_by_id.get(str(p.get("id") or "").lower() or (p.get("name") or "").lower(), 0.0)
                        for p in combo
                    )
                    optimal = round(opt, 2)
                stacks.append({
                    "team": team,
                    "opponent": opp,
                    "stack_size": size,
                    "implied_total": (top[0].get("sbme_implied_team_total") if top else None),
                    "sbme_implied_team_total": (top[0].get("sbme_implied_team_total") if top else None),
                    "sbme_game_total": (top[0].get("sbme_game_total") if top else None),
                    "sbme_implied_total_method": (top[0].get("sbme_implied_total_method") if top else None),
                    "sb_projection": proj,
                    "stack_ownership": ownership,
                    "optimal_stack_pct": optimal,
                    "leverage": leverage,
                    "value": value,
                    "rating": _rating(proj, value, leverage),
                    "salary": sal,
                    "players": [
                        {
                            "id": p.get("id"),
                            "name": p.get("name", ""),
                            "position": p.get("roster_position") or p.get("position", ""),
                            "salary": p.get("salary", 0),
                            "projected_fp": p.get("projected_fp", 0),
                            "ownership_pct": p.get("sbme_ownership_pct"),
                            "leverage": p.get("leverage"),
                        }
                        for p in combo
                    ],
                })

    # Sort by rating then projection
    stacks.sort(key=lambda s: (s["sb_projection"]), reverse=True)

    metadata = {
        "model": STACK_MODEL_VERSION,
        "sport": sport,
        "platform": platform,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "team_count": len(teams),
        "stack_count": len(stacks),
        "implied_total": "SB ME derived team implied total from nested SGO markets when available",
        "implied_total_source": "sbme_derived",
    }

    return {"stacks": stacks, "metadata": metadata}
