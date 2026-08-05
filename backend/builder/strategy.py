"""
SB-Me Builder strategy profiles and objective function.

12 deterministic strategy profiles with documented weights.
Objective function is testable and reproducible.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class StrategyProfile:
    name: str
    description: str
    projection_weight: float = 1.0
    ceiling_weight: float = 0.0
    edge_weight: float = 0.5
    ownership_weight: float = 0.0
    leverage_weight: float = 0.0
    risk_penalty: float = 0.1
    salary_usage_target: float = 0.95
    correlation_bonus: float = 0.0
    uniqueness_target: int = 2
    max_exposure_default: float = 1.0
    random_noise: float = 0.0
    prefer_contrarian: bool = False
    prefer_stars: bool = False


# ── Strategy Profiles ────────────────────────────────────────

STRATEGY_PROFILES: Dict[str, StrategyProfile] = {
    "cash": StrategyProfile(
        name="Cash",
        description="High-floor, low-risk. Maximizes median projection with salary efficiency.",
        projection_weight=1.0, ceiling_weight=0.0, edge_weight=0.3,
        ownership_weight=0.1, leverage_weight=0.0, risk_penalty=0.15,
        salary_usage_target=0.98, uniqueness_target=1,
    ),
    "single_entry": StrategyProfile(
        name="Single Entry",
        description="Balanced approach for single-entry contests.",
        projection_weight=0.8, ceiling_weight=0.2, edge_weight=0.5,
        ownership_weight=0.1, leverage_weight=0.1, risk_penalty=0.1,
        salary_usage_target=0.95, uniqueness_target=2,
    ),
    "small_gpp": StrategyProfile(
        name="Small-Field GPP",
        description="Balanced ceiling with moderate leverage for small tournaments.",
        projection_weight=0.6, ceiling_weight=0.4, edge_weight=0.5,
        ownership_weight=0.2, leverage_weight=0.2, risk_penalty=0.05,
        salary_usage_target=0.92, uniqueness_target=3,
    ),
    "large_gpp": StrategyProfile(
        name="Large-Field GPP",
        description="High ceiling, high leverage, contrarian for large tournaments.",
        projection_weight=0.4, ceiling_weight=0.6, edge_weight=0.6,
        ownership_weight=0.3, leverage_weight=0.4, risk_penalty=0.0,
        salary_usage_target=0.90, uniqueness_target=4, prefer_contrarian=True,
    ),
    "max20": StrategyProfile(
        name="20-Max",
        description="Moderate diversification for 20-entry contests.",
        projection_weight=0.7, ceiling_weight=0.3, edge_weight=0.5,
        ownership_weight=0.15, leverage_weight=0.15, risk_penalty=0.08,
        salary_usage_target=0.93, uniqueness_target=2, max_exposure_default=0.40,
    ),
    "max150": StrategyProfile(
        name="150-Max",
        description="Full portfolio diversification for 150-entry contests.",
        projection_weight=0.6, ceiling_weight=0.4, edge_weight=0.5,
        ownership_weight=0.25, leverage_weight=0.25, risk_penalty=0.03,
        salary_usage_target=0.90, uniqueness_target=3, max_exposure_default=0.25,
        prefer_contrarian=True,
    ),
    "conservative": StrategyProfile(
        name="Conservative",
        description="Safety-first with high risk penalty and strict constraints.",
        projection_weight=1.0, ceiling_weight=0.0, edge_weight=0.3,
        ownership_weight=0.0, leverage_weight=0.0, risk_penalty=0.25,
        salary_usage_target=0.97, uniqueness_target=1, max_exposure_default=0.50,
    ),
    "balanced": StrategyProfile(
        name="Balanced",
        description="Evenly weighted medium-risk profile.",
        projection_weight=0.7, ceiling_weight=0.3, edge_weight=0.5,
        ownership_weight=0.1, leverage_weight=0.1, risk_penalty=0.1,
        salary_usage_target=0.95, uniqueness_target=2,
    ),
    "aggressive": StrategyProfile(
        name="Aggressive",
        description="High ceiling chasing with low risk penalty.",
        projection_weight=0.3, ceiling_weight=0.7, edge_weight=0.6,
        ownership_weight=0.2, leverage_weight=0.3, risk_penalty=0.0,
        salary_usage_target=0.90, uniqueness_target=4, prefer_contrarian=True,
    ),
    "stars_and_scrubs": StrategyProfile(
        name="Stars and Scrubs",
        description="High-salary stars paired with minimum-salary scrubs.",
        projection_weight=0.5, ceiling_weight=0.5, edge_weight=0.5,
        ownership_weight=0.15, leverage_weight=0.2, risk_penalty=0.05,
        salary_usage_target=0.95, uniqueness_target=2, prefer_stars=True,
    ),
    "contrarian": StrategyProfile(
        name="Contrarian",
        description="Fades chalk. Maximizes leverage over ownership.",
        projection_weight=0.4, ceiling_weight=0.6, edge_weight=0.6,
        ownership_weight=0.4, leverage_weight=0.5, risk_penalty=0.0,
        salary_usage_target=0.90, uniqueness_target=4, prefer_contrarian=True,
    ),
    "high_correlation": StrategyProfile(
        name="High-Correlation",
        description="Stacks teammates for correlation upside.",
        projection_weight=0.5, ceiling_weight=0.5, edge_weight=0.5,
        ownership_weight=0.1, leverage_weight=0.2, risk_penalty=0.05,
        salary_usage_target=0.93, uniqueness_target=2, correlation_bonus=0.15,
    ),
}


def get_strategy(name: str) -> StrategyProfile:
    """Look up a strategy by name (case-insensitive)."""
    key = name.lower().replace(" ", "_").replace("-", "_")
    profile = STRATEGY_PROFILES.get(key)
    if profile is None:
        raise ValueError(f"Unknown strategy: '{name}'. Available: {sorted(STRATEGY_PROFILES.keys())}")
    return profile


def list_strategies() -> List[str]:
    return sorted(STRATEGY_PROFILES.keys())


# ── Objective Function ───────────────────────────────────────

def builder_objective(
    player: dict,
    strategy: StrategyProfile,
    randomness: float = 0.0,
) -> float:
    """
    SB-Me Builder objective score for a single player.

    Components (weighted by strategy profile):
      - median_projection (projection_weight)
      - ceiling_projection (ceiling_weight)
      - edge_score         (edge_weight)
      - ownership_leverage (leverage_weight)
      - risk_penalty       (risk_penalty, subtracted)
      - correlation_bonus  (correlation_bonus, added if stacked)
      - random_noise       (randomness * rand())

    Returns a float score used by the optimizer as the objective coefficient.
    """
    import random

    med = player.get("projected_fp", player.get("median_projection", 0)) or 0
    ceil = player.get("ceiling", player.get("ceiling_projection", 0)) or 0
    edge = player.get("edge_score", 50) or 50
    leverage = player.get("leverage", player.get("leverage_score", 0)) or 0
    risk = player.get("risk_score", 0) or 0
    corr = player.get("correlation_bonus", 0) or 0
    own = player.get("ownership", player.get("ownership_projection", 0)) or 0

    if strategy.prefer_contrarian and own > 0:
        leverage = max(leverage, (1.0 - own / 100.0) * 0.5)

    if strategy.prefer_stars and player.get("salary", 0) > 9000:
        med *= 1.1
        ceil *= 1.1

    score = (
        strategy.projection_weight * med / 60.0
        + strategy.ceiling_weight * ceil / 70.0
        + strategy.edge_weight * edge / 100.0
        + strategy.ownership_weight * (1.0 - min(own, 100) / 100.0)
        + strategy.leverage_weight * leverage
        - strategy.risk_penalty * risk
        + strategy.correlation_bonus * corr
    )

    if randomness > 0:
        score += random.uniform(-randomness, randomness) * 0.1

    return max(0.0, round(score, 4))