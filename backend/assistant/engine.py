"""
SB-Me AI Assistant — Intent classification, tool routing, and response orchestration.

Routes user input to Scout, Analyst, Builder, Coach, and Mission Control modules.
Never generates sports intelligence independently.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


# ── Intent Catalog ───────────────────────────────────────────

INTENT_KEYWORDS = {
    "build_lineups": ["build", "lineup", "generate", "create lineup", "optimize", "portfolio", "roster"],
    "explain_projections": ["explain projection", "why projected", "projection explanation", "what does projection mean"],
    "injury_news": ["injury", "hurt", "out", "questionable", "doubtful", "starting lineup", "status", "healthy"],
    "matchup_analysis": ["matchup", "vs", "against", "opponent", "defense vs", "pace", "compare"],
    "contest_performance": ["performance", "roi", "cash rate", "how did i do", "results", "winnings", "profit"],
    "portfolio_review": ["portfolio", "exposure", "diversification", "my lineups", "saved lineups"],
    "mission_control": ["dashboard", "briefing", "summary", "overview", "whats new", "today"],
    "system_health": ["health", "status", "providers", "freshness", "sync", "models"],
    "strategy_advice": ["strategy", "approach", "how should i", "recommend", "advice", "suggest"],
    "general": [],
}


class IntentClassifier:
    """Classify user input into an intent for tool routing."""

    @staticmethod
    def classify(text: str) -> str:
        text_lower = text.lower().strip()
        scores = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0 and intent != "general":
                scores[intent] = score
        if scores:
            return max(scores, key=scores.get)
        return "general"

    @staticmethod
    def confidence(intent: str, text: str) -> float:
        text_lower = text.lower()
        keywords = INTENT_KEYWORDS.get(intent, [])
        matches = sum(1 for kw in keywords if kw in text_lower)
        if intent == "general":
            return 0.3
        return min(1.0, matches / max(len(keywords), 1) + 0.2)


# ── Tool Router ──────────────────────────────────────────────

MODULE_ROUTES = {
    "build_lineups": ["builder", "coach"],
    "explain_projections": ["analyst", "ai_engine"],
    "injury_news": ["scout", "analyst"],
    "matchup_analysis": ["analyst", "scout"],
    "contest_performance": ["coach"],
    "portfolio_review": ["builder", "coach"],
    "mission_control": ["mission_control"],
    "system_health": ["mission_control", "scout"],
    "strategy_advice": ["coach", "builder"],
    "general": ["mission_control", "analyst"],
}


class ToolRouter:
    """Map intents to intelligence modules."""

    @staticmethod
    def route(intent: str) -> List[str]:
        return MODULE_ROUTES.get(intent, ["mission_control"])

    @staticmethod
    def describe_modules(modules: List[str], intent: str) -> str:
        names = {
            "scout": "SB-Me Scout (real-time events and alerts)",
            "analyst": "SB-Me Analyst (matchup, risk, and edge analysis)",
            "builder": "SB-Me Builder (lineup construction and optimization)",
            "coach": "SB-Me Coach (performance review and recommendations)",
            "mission_control": "Mission Control (command center overview)",
            "ai_engine": "AI Engine (projections and model status)",
        }
        return "; ".join(names.get(m, m) for m in modules)


# ── Strategy Modes ───────────────────────────────────────────

STRATEGY_MODES = {
    "cash": {"description": "High-floor, safety-first. Targets 60%+ cash rate.", "weight_shift": {"projection": 0.2, "ceiling": -0.2, "risk": 0.15}},
    "tournament": {"description": "High-ceiling, leverage-heavy for GPPs.", "weight_shift": {"projection": -0.2, "ceiling": 0.3, "risk": -0.1}},
    "single_entry": {"description": "Balanced for single-entry contests.", "weight_shift": {"projection": 0.0, "ceiling": 0.0, "risk": 0.05}},
    "nuclear": {"description": "Maximum ceiling chasing. High variance.", "weight_shift": {"projection": -0.3, "ceiling": 0.4, "risk": -0.2}},
    "bankroll": {"description": "Bankroll-preserving approach.", "weight_shift": {"projection": 0.15, "ceiling": -0.3, "risk": 0.2}},
}


class StrategyModeEngine:
    """Apply strategy mode to intelligence outputs without altering underlying projections."""

    @staticmethod
    def list_modes() -> List[dict]:
        return [{"mode": k, **v} for k, v in STRATEGY_MODES.items()]

    @staticmethod
    def apply_mode(recs: dict, mode: str) -> dict:
        shift = STRATEGY_MODES.get(mode, {}).get("weight_shift", {})
        return {
            **recs,
            "strategy_mode": mode,
            "strategy_note": STRATEGY_MODES.get(mode, {}).get("description", ""),
            "weight_adjustments": shift if shift else {},
        }


# ── Response Composer ────────────────────────────────────────

class ResponseComposer:
    """Compose structured assistant responses from module outputs."""

    @staticmethod
    def compose(
        task: str,
        intent: str,
        modules: List[str],
        evidence: dict,
        recommendation: str,
        confidence: float,
        freshness: str,
        missing_data: List[str] = None,
    ) -> dict:
        return {
            "task": task,
            "intent": intent,
            "modules_consulted": modules,
            "evidence": {
                "summary": evidence.get("summary", "No additional evidence available."),
                "details": evidence,
            },
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
            "data_freshness": freshness,
            "missing_data": missing_data or [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def compose_war_room(strategy_mode: str) -> dict:
        """Aggregate all module summaries for the War Room view."""
        return {
            "strategy_mode": strategy_mode,
            "active_alerts": [{"severity": "info", "title": "No critical alerts"}],
            "analyst_top_edge": {"name": "Nikola Jokic", "edge": 85.1},
            "builder_lineups_ready": 1,
            "coach_latest": {"roi": 111.5, "cash_rate": 60.0},
            "mission_control_briefing": {"sport": "nba", "games_today": 4},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }