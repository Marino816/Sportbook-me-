"""Corrected refresh-test record. Do not execute provider HTTP here."""

from __future__ import annotations

from market_snapshot.capture_evidence import CAPTURE_EVIDENCE
from market_snapshot.scheduler import CONFIG

# Scenario A near-window intervals from the costed refresh config.
FEATURED_NEAR_SECONDS = 300
PROPS_NEAR_SECONDS = 600


def timed_refresh_plan() -> dict:
    """A later assignment may run this. This function does not send HTTP."""
    return {
        "executable_now": False,
        "provider_http": 0,
        "why_not_now": "This assignment forbids additional provider requests.",
        "minimum_wait_between_captures_seconds": {
            "featured_near_window": FEATURED_NEAR_SECONDS,
            "props_near_window": PROPS_NEAR_SECONDS,
        },
        "prior_captures_insufficient": CAPTURE_EVIDENCE["interval_verification"],
        "later_procedure": [
            "Keep MARKET_TOOLS_ODDSAPI_COLLECT=false and browsing_triggers_upstream=false.",
            f"Capture 1: one featured NFL /odds request (max cost 3) and optionally one event props request.",
            f"Wait at least {FEATURED_NEAR_SECONDS}s (featured) and {PROPS_NEAR_SECONDS}s (props) of real time.",
            "Capture 2: repeat the same paths.",
            "Compare bookmaker last_update (source_timestamp) separately from retrieved_at.",
            "Identical bodies after a 0–1s gap do not prove freshness; only a wait >= the configured interval can.",
        ],
        "config_stale_after_seconds": CONFIG.get("stale_after_seconds"),
    }
