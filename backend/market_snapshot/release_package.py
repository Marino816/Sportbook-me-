"""Deployment package for Odds API Market Tools. Importing does not change production."""

from __future__ import annotations

from market_snapshot.cutover import (
    COMPATIBLE_CONSUMERS,
    CUTOVER_ENV,
    FEATURE_IMPACT,
    INCOMPATIBLE_CONSUMERS,
    ROLLBACK_ENV,
    activation_state,
)
from market_snapshot.scheduler import CONFIG, DEFAULT_DAILY_CREDIT_LIMIT, DEFAULT_MONTHLY_CREDIT_LIMIT, quota_breakdown


CUTOVER_ENV_WITH_QUOTA = {
    **CUTOVER_ENV,
    "MARKET_TOOLS_MONTHLY_CREDIT_LIMIT": str(DEFAULT_MONTHLY_CREDIT_LIMIT),
    "MARKET_TOOLS_DAILY_CREDIT_LIMIT": str(DEFAULT_DAILY_CREDIT_LIMIT),
    "MARKET_TOOLS_CONTEXT_COLLECT": "false",
    "MARKET_TOOLS_FIXTURE_INGEST": "false",
}


ROLLBACK_STEPS = (
    "Set MARKET_TOOLS_ODDSAPI_ENABLED=false and MARKET_TOOLS_ODDSAPI_COLLECT=false on the FastAPI process (same as ROLLBACK_ENV).",
    "Leave MARKET_TOOLS_PROVIDER=sgo. Existing SGO nested cache serving resumes for Market Tools consumers that still read SGO.",
    "Do not delete Redis key sbme:mt:oddsapi:preview; rollback does not require a Redis flush.",
    "Do not cancel SportsGameOdds in this assignment. Do not purchase Odds API credits as part of rollback.",
    "Web layout stays the approved 4-tab Market Tools. No store submission and no mobile rebuild is required to roll backend flags back.",
)


DEPLOYMENT_CONFIGURATION = {
    "applied": False,
    "production_unchanged": True,
    "process": "Railway FastAPI (or equivalent) environment variables only. No git push/merge in this assignment.",
    "cutover_env": dict(CUTOVER_ENV_WITH_QUOTA),
    "rollback_env": dict(ROLLBACK_ENV),
    "collection": {
        "on_cutover": True,
        "scheduler_continuous_fetch_code_default": CONFIG["enabled"],
        "quota": quota_breakdown(),
        "monthly_credit_limit": DEFAULT_MONTHLY_CREDIT_LIMIT,
        "daily_credit_limit": DEFAULT_DAILY_CREDIT_LIMIT,
        "note": (
            "configured_limit is busiest_30_day + 25% contingency. "
            "effective_collection_stop equals configured_limit. Reserve is not held back a second time."
        ),
    },
    "flags_not_to_enable_here": [
        "MARKET_TOOLS_FIXTURE_INGEST",
        "MARKET_TOOLS_CONTEXT_COLLECT",
        "BCDFS_SCHEDULER_ENABLED if currently off in production",
    ],
}


CUSTOMER_VISIBLE_FEATURE_IMPACT = tuple(
    {"surface": row["surface"], "class": row["class"], "note": row["note"]}
    for row in FEATURE_IMPACT
)


def release_package() -> dict:
    quota = quota_breakdown()
    return {
        "reviewable": True,
        "applied": False,
        "production_unchanged": True,
        "no_push_merge_or_deploy": True,
        "deployment_configuration": DEPLOYMENT_CONFIGURATION,
        "quota_settings": {
            "MARKET_TOOLS_MONTHLY_CREDIT_LIMIT": DEFAULT_MONTHLY_CREDIT_LIMIT,
            "MARKET_TOOLS_DAILY_CREDIT_LIMIT": DEFAULT_DAILY_CREDIT_LIMIT,
            **quota,
        },
        "rollback_env": dict(ROLLBACK_ENV),
        "rollback_steps": list(ROLLBACK_STEPS),
        "customer_visible_feature_impact": list(CUSTOMER_VISIBLE_FEATURE_IMPACT),
        "compatible_consumers": list(COMPATIBLE_CONSUMERS),
        "incompatible_consumers": list(INCOMPATIBLE_CONSUMERS),
        "activation_state": activation_state(),
    }
