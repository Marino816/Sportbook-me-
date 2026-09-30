"""Development-only Market Tools provider switch. Defaults to existing SGO behavior."""

from __future__ import annotations

import os

PROVIDER_SGO = "sgo"
PROVIDER_SNAPSHOT = "oddsapi_snapshot"


def market_tools_provider() -> str:
    """Return the active Market Tools data provider.

    Production always uses existing SGO behavior. Snapshot mode is local
    development only and never implied by an empty env var.
    """
    if os.getenv("NODE_ENV", "").strip().lower() == "production":
        return PROVIDER_SGO
    raw = (os.getenv("MARKET_TOOLS_PROVIDER") or PROVIDER_SGO).strip().lower()
    if raw in {PROVIDER_SNAPSHOT, "oddsapi", "snapshot"}:
        return PROVIDER_SNAPSHOT
    return PROVIDER_SGO


def is_snapshot() -> bool:
    return market_tools_provider() == PROVIDER_SNAPSHOT


def snapshot_blocks_sgo() -> bool:
    """When the local snapshot replacement is on, do not call SGO."""
    return is_snapshot()
