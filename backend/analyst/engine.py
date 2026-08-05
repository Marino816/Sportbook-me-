"""
SB-Me Analyst — Core analysis engines.

Matchup analysis, risk assessment, edge scoring, projection-change analysis.
All formulas are deterministic and testable.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


# ── Matchup Engine ───────────────────────────────────────────

MATCHUP_FACTORS_NBA = [
    "pace", "offensive_efficiency", "defensive_efficiency", "position_defense",
    "rebounding", "turnover_rate", "usage", "minutes", "recent_form",
    "home_away_split", "rest_days", "injury_status", "vegas_total",
    "spread", "line_movement", "starting_confirmed",
]


class MatchupEngine:
    """Analyze game matchups for structured factors."""

    @staticmethod
    def analyze(player_data: dict, game_data: Optional[dict] = None) -> dict:
        factors = []
        pace = player_data.get("pace", None)
        if pace is not None:
            factors.append({"factor": "pace", "value": pace, "label": f"Team pace: {pace:.1f}"})
        off_eff = player_data.get("offensive_efficiency", None)
        if off_eff is not None:
            factors.append({"factor": "offensive_efficiency", "value": off_eff, "label": f"OffEff: {off_eff:.1f}"})
        def_eff = player_data.get("defensive_efficiency", None)
        if def_eff is not None:
            factors.append({"factor": "defensive_efficiency", "value": def_eff, "label": f"DefEff: {def_eff:.1f}"})
        usage = player_data.get("usage", None)
        if usage is not None:
            factors.append({"factor": "usage", "value": usage, "label": f"Usage: {usage:.1%}"})
        rest = player_data.get("rest_days", None)
        if rest is not None:
            factors.append({"factor": "rest", "value": rest, "label": f"Rest: {rest} days"})
        home = player_data.get("is_home", None)
        if home is not None:
            factors.append({"factor": "home_away", "value": 1 if home else 0, "label": "Home" if home else "Away"})
        injury = player_data.get("injury_status", "unknown")
        if injury != "unknown":
            factors.append({"factor": "injury", "value": None, "label": f"Injury: {injury}"})
        return {"available_factors": len(factors), "factors": factors, "missing_factors": [f for f in MATCHUP_FACTORS_NBA if f not in [x["factor"] for x in factors]]}


# ── Risk Engine ──────────────────────────────────────────────

RISK_WEIGHTS = {
    "blowout_risk": 0.10,
    "minutes_uncertainty": 0.12,
    "injury_uncertainty": 0.15,
    "starting_uncertainty": 0.10,
    "ownership_risk": 0.08,
    "small_sample": 0.10,
    "stale_data": 0.10,
    "missing_market_data": 0.08,
    "high_volatility": 0.12,
    "role_instability": 0.05,
}


class RiskEngine:
    """Deterministic risk assessment for players and matchups."""

    @staticmethod
    def assess(player_data: dict, is_stale: bool = False, missing_fields: List[str] = None) -> List[dict]:
        risks = []
        missing_fields = missing_fields or []
        injury = player_data.get("injury_status", "unknown")
        starter = player_data.get("starting_status", "unknown")
        sample_size = player_data.get("games_played", 0)
        avg_fp = player_data.get("avg_fp_last_5")

        if injury in ("Out", "Doubtful"):
            risks.append({"risk_type": "injury_uncertainty", "label": f"Player {injury}", "severity": 0.9})
        elif injury not in ("Healthy", "Probable"):
            risks.append({"risk_type": "injury_uncertainty", "label": f"Status: {injury}", "severity": 0.5})

        if starter not in ("Confirmed", "Probable"):
            risks.append({"risk_type": "starting_uncertainty", "label": f"Starting: {starter}", "severity": 0.5})

        if is_stale:
            risks.append({"risk_type": "stale_data", "label": "Data is stale", "severity": 0.7})

        if "salary" in missing_fields or "odds" in missing_fields:
            risks.append({"risk_type": "missing_market_data", "label": "Missing market data", "severity": 0.6})

        if sample_size > 0 and sample_size < 5:
            risks.append({"risk_type": "small_sample", "label": f"Small sample: {sample_size} games", "severity": 0.5 - (sample_size * 0.1)})
        elif sample_size == 0:
            risks.append({"risk_type": "small_sample", "label": "No game data available", "severity": 0.8})

        if avg_fp is not None and sample_size > 0:
            recent = player_data.get("recent_form", 0)
            if recent is not None and abs(recent - avg_fp) / max(avg_fp, 1) > 0.3:
                risks.append({"risk_type": "high_volatility", "label": "High recent volatility", "severity": 0.4})

        minutes_avg = player_data.get("minutes", None)
        if minutes_avg is not None and minutes_avg < 20:
            risks.append({"risk_type": "minutes_uncertainty", "label": f"Low minutes: {minutes_avg:.0f}/gm", "severity": 0.5})

        return risks

    @staticmethod
    def aggregate_risk_score(risks: List[dict]) -> float:
        if not risks:
            return 0.0
        total = 0.0
        for r in risks:
            weight = RISK_WEIGHTS.get(r["risk_type"], 0.05)
            total += r["severity"] * weight
        return round(min(1.0, total), 3)


# ── SB-Me Edge Engine ────────────────────────────────────────

EDGE_WEIGHTS = {
    "projection_strength": 0.30,
    "matchup_quality": 0.20,
    "market_alignment": 0.15,
    "ownership_leverage": 0.10,
    "data_quality": 0.15,
    "confidence": 0.05,
    "risk_penalty": -0.05,  # applied per risk above threshold
}


class EdgeEngine:
    """SB-Me Edge score: deterministic multi-factor rating (0-100)."""

    @staticmethod
    def calculate(
        projection_score: float,     # 0-1
        matchup_score: float,        # 0-1
        market_alignment: float,     # 0-1
        ownership_leverage: float,   # 0-1 (None → 0.5 default)
        data_quality: float,         # 0-1 (1.0 - confidence deductions)
        confidence: float,           # 0-1
        risk_count: int = 0,         # number of identified risks
    ) -> Tuple[float, dict]:
        components = {
            "projection_strength": projection_score,
            "matchup_quality": matchup_score,
            "market_alignment": market_alignment,
            "ownership_leverage": ownership_leverage or 0.5,
            "data_quality": data_quality,
            "confidence": confidence,
        }
        base = 0.0
        for key, weight in EDGE_WEIGHTS.items():
            if key == "risk_penalty":
                penalty = min(0.25, risk_count * 0.05)
                base += weight * penalty
            else:
                base += weight * components.get(key, 0.5)
        score = round(max(0.0, min(100.0, base * 100.0)), 1)
        return score, components

    @staticmethod
    def tier(edge_score: float) -> str:
        if edge_score >= 85:
            return "Elite Edge"
        elif edge_score >= 70:
            return "Strong Edge"
        elif edge_score >= 55:
            return "Solid Edge"
        elif edge_score >= 40:
            return "Neutral"
        return "Low Confidence"


# ── Projection Change Analyzer ───────────────────────────────

class ProjectionChangeAnalyzer:
    """Compare current vs prior projections with triggering events."""

    @staticmethod
    def analyze(
        entity_id: int,
        entity_type: str,
        current_projection: float,
        previous_projection: Optional[float],
        scout_event_ids: List[str] = None,
        adjustment_factors: List[str] = None,
        current_confidence: float = 0.5,
        previous_confidence: float = 0.5,
    ) -> dict:
        if previous_projection is None:
            return {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "previous_projection": None,
                "current_projection": current_projection,
                "absolute_change": None,
                "percentage_change": None,
                "triggering_events": scout_event_ids or [],
                "adjustment_factors": adjustment_factors or [],
                "confidence_change": 0.0,
                "optimizer_refresh_recommended": False,
            }
        abs_change = current_projection - previous_projection
        pct_change = (abs_change / max(abs(previous_projection), 0.1)) * 100
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "previous_projection": round(previous_projection, 1),
            "current_projection": round(current_projection, 1),
            "absolute_change": round(abs_change, 1),
            "percentage_change": round(pct_change, 1),
            "triggering_events": scout_event_ids or [],
            "adjustment_factors": adjustment_factors or [],
            "confidence_change": round(current_confidence - previous_confidence, 3),
            "optimizer_refresh_recommended": abs(abs_change) > 3.0 or abs(pct_change) > 10,
        }


# ── Confidence Decomposer ────────────────────────────────────

class ConfidenceDecomposer:
    """Break a confidence score into component factors."""

    @staticmethod
    def decompose(
        data_quality: float,
        sample_size: int,
        market_available: bool,
        injury_known: bool,
        data_is_recent: bool,
    ) -> dict:
        return {
            "data_quality": round(data_quality, 3),
            "sample_size": round(min(1.0, sample_size / 20.0), 3),
            "market_alignment": round(0.8 if market_available else 0.3, 3),
            "injury_clarity": round(0.9 if injury_known else 0.4, 3),
            "recency": round(0.9 if data_is_recent else 0.3, 3),
        }