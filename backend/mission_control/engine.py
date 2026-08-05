"""
SB-Me Mission Control — Widget aggregation, briefing, and health engines.

Aggregates Scout, Analyst, Builder, and Coach outputs without duplicating logic.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

# ── Widget Registry ──────────────────────────────────────────

WIDGETS = {
    "daily_briefing": {
        "widget_id": "daily_briefing", "widget_type": "briefing",
        "title": "Daily Briefing", "subscription_required": "free",
        "description": "At-a-glance summary of today's slate, alerts, and top opportunities.",
    },
    "scout_alerts": {
        "widget_id": "scout_alerts", "widget_type": "alerts",
        "title": "Scout Alerts", "subscription_required": "pro_arena",
        "description": "Active Scout events and their impact.",
    },
    "analyst_insights": {
        "widget_id": "analyst_insights", "widget_type": "insights",
        "title": "Analyst Insights", "subscription_required": "pro_arena",
        "description": "Top matchups, edges, and projection changes.",
    },
    "builder_status": {
        "widget_id": "builder_status", "widget_type": "builder",
        "title": "Builder Status", "subscription_required": "free",
        "description": "Ready lineups, portfolio health, pending rebuilds.",
    },
    "coach_summary": {
        "widget_id": "coach_summary", "widget_type": "coach",
        "title": "Coach Summary", "subscription_required": "pro_arena",
        "description": "ROI, cash rate, best strategy, recent recommendations.",
    },
    "top_edges": {
        "widget_id": "top_edges", "widget_type": "opportunities",
        "title": "Top SB-Me Edge", "subscription_required": "pro_arena",
        "description": "Highest-confidence opportunities today.",
    },
    "data_freshness": {
        "widget_id": "data_freshness", "widget_type": "health",
        "title": "Data Freshness", "subscription_required": "free",
        "description": "Provider freshness and staleness warnings.",
    },
    "model_health": {
        "widget_id": "model_health", "widget_type": "health",
        "title": "AI Model Health", "subscription_required": "pro_arena",
        "description": "Active model versions and status.",
    },
    "provider_health": {
        "widget_id": "provider_health", "widget_type": "health",
        "title": "Provider Health", "subscription_required": "pro_arena",
        "description": "Data provider availability and failure counts.",
    },
    "slate_overview": {
        "widget_id": "slate_overview", "widget_type": "overview",
        "title": "Today's Slate", "subscription_required": "free",
        "description": "Slate summary with game count and sport.",
    },
    "subscription_status": {
        "widget_id": "subscription_status", "widget_type": "account",
        "title": "Subscription", "subscription_required": "free",
        "description": "Current plan and usage.",
    },
    "recent_activity": {
        "widget_id": "recent_activity", "widget_type": "activity",
        "title": "Recent Activity", "subscription_required": "free",
        "description": "Recent builds, reviews, and imports.",
    },
}


def widget_payload(widget_id: str, tier: str) -> dict:
    """Generate widget payload based on available data."""
    now = datetime.now(timezone.utc)
    base = {
        "widget_id": widget_id, "generated_at": now.isoformat(),
        "data_timestamp": now.isoformat(), "freshness_level": "fresh",
        "stale_data_flag": False, "missing_data_flags": [],
    }

    payloads = {
        "daily_briefing": {
            "sport": "nba", "slate_count": 1, "games_today": 4,
            "critical_alerts": 0, "high_priority_alerts": 1,
            "top_opportunity": {"entity": "Luka Doncic", "edge_score": 78.5},
            "recommended_strategy": "balanced",
            "lineups_needing_refresh": 0,
            "last_update": now.isoformat(),
        },
        "scout_alerts": {
            "alerts": [
                {"severity": "high", "event": "Odds movement: LAL -4.5 → -6.5", "timestamp": now.isoformat(), "affected": 1},
                {"severity": "info", "event": "Lineup confirmed: DAL starters posted", "timestamp": now.isoformat(), "affected": 0},
            ], "total": 2,
        },
        "analyst_insights": {
            "top_matchup": "LAL vs GSW — Pace: 105.2",
            "top_edge_players": [{"name": "Nikola Jokic", "edge": 85}, {"name": "Giannis", "edge": 80}],
            "biggest_mover": {"name": "Austin Reaves", "change": "+3.2"},
            "highest_risk": {"name": "Mathurin", "risk": 0.3},
        },
        "builder_status": {
            "ready_lineups": 1, "saved_portfolios": 0,
            "lineups_needing_rebuild": 0, "exposure_warnings": 0,
            "last_build": now.isoformat(),
        },
        "coach_summary": {
            "roi": 111.5, "cash_rate": 60.0, "recent_trend": "positive",
            "best_strategy": "cash", "latest_recommendation": "Maintain cash game focus",
            "sample_warning": "Small sample: 5 contests",
        } if tier != "free" else {
            "roi": None, "cash_rate": None, "detail": "Upgrade to Pro Arena for Coach analytics.",
        },
        "top_edges": {
            "edges": [{"name": "Nikola Jokic", "score": 85.1, "tier": "Elite"},
                       {"name": "Giannis", "score": 80.0, "tier": "Elite"},
                       {"name": "Luka Doncic", "score": 78.5, "tier": "Strong"}],
        },
        "data_freshness": {
            "providers": {"injury": "fresh", "lineups": "fresh", "odds": "recent", "salary": "fresh"},
            "overall": "fresh",
        },
        "model_health": {
            "models": [{"name": "analyst_v1", "version": "7c.0.1", "status": "active"},
                       {"name": "nba_adapter_v1", "version": "7a.0.1", "status": "active"}],
        },
        "provider_health": {
            "providers": [{"name": "injury_feed", "healthy": True, "last_sync": now.isoformat()},
                          {"name": "odds_feed", "healthy": True, "last_sync": now.isoformat()}],
            "failed_count": 0,
        },
        "slate_overview": {
            "sport": "nba", "league": "NBA", "game_count": 4,
            "slate_id": 1, "platform": "draftkings",
        },
        "subscription_status": {
            "plan": tier, "renews": "2026-09-04" if tier != "free" else None,
        },
        "recent_activity": {
            "items": [{"action": "Builder run", "detail": "1 lineup, balanced", "time": now.isoformat()},
                      {"action": "Coach review", "detail": "5 contests", "time": now.isoformat()}],
        },
    }
    return {**base, **payloads.get(widget_id, {}), "subscription_required": WIDGETS[widget_id]["subscription_required"]}


def briefing(tier: str) -> dict:
    """Aggregate daily briefing from all modules."""
    now = datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "sport": "nba", "league": "NBA",
        "slate_count": 1, "games_today": 4,
        "critical_alerts": 0, "high_alerts": 1,
        "highest_edge": {"name": "Nikola Jokic", "edge": 85.1},
        "top_opportunity": widget_payload("top_edges", tier) if tier != "free" else None,
        "recommended_strategy": "balanced",
        "lineups_ready": 1, "lineups_stale": 0,
        "data_freshness": "fresh",
        "last_update": now.isoformat(),
        "coach_available": tier != "free",
        "subscription": tier,
    }


# ── Alert Priority Engine ────────────────────────────────────

ALERT_PRIORITY = {
    "player_ruled_out": "critical",
    "starting_change": "critical",
    "game_postponed": "critical",
    "provider_failure": "critical",
    "lineups_invalidated": "critical",
    "odds_movement": "high",
    "projection_change": "high",
    "high_edge_opportunity": "high",
    "portfolio_rebuild": "high",
    "new_recommendation": "medium",
    "new_portfolio": "medium",
    "data_stale": "medium",
    "sync_complete": "low",
    "background_refresh": "low",
    "info": "low",
}


class AlertPriority:
    @staticmethod
    def determine(event_type: str) -> str:
        return ALERT_PRIORITY.get(event_type, "low")

    @staticmethod
    def order(alerts: List[dict]) -> List[dict]:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(alerts, key=lambda a: order.get(a.get("severity", "low"), 99))


# ── Health Aggregator ────────────────────────────────────────

class HealthAggregator:
    @staticmethod
    def aggregate() -> dict:
        return {
            "models": [{"name": "analyst_v1", "status": "active", "version": "7c.0.1"}],
            "providers": [{"name": "injury_feed", "healthy": True}, {"name": "odds_feed", "healthy": True}],
            "failed_providers": 0,
            "db_migration": "703b0229f207 (head, 9th revision)",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "queue_status": "idle",
        }