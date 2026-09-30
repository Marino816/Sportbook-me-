"""Server-side Market Tools provider flags. Defaults preserve SGO."""

from __future__ import annotations

import os

PROVIDER_SGO = "sgo"
PROVIDER_SNAPSHOT = "oddsapi_snapshot"
PROVIDER_ODDSAPI = "oddsapi"


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def is_production() -> bool:
    return os.getenv("NODE_ENV", "").strip().lower() == "production"


def snapshot_mode() -> bool:
    """Development-only saved-payload mode. Ignored in production."""
    if is_production():
        return False
    raw = (os.getenv("MARKET_TOOLS_PROVIDER") or PROVIDER_SGO).strip().lower()
    return raw in {PROVIDER_SNAPSHOT, "snapshot"}


def oddsapi_enabled() -> bool:
    """Production-capable Odds API serving flag. Default OFF."""
    return _truthy("MARKET_TOOLS_ODDSAPI_ENABLED", False)


def collect_enabled() -> bool:
    """Collector/tick flag. Default OFF. Requires oddsapi_enabled."""
    return oddsapi_enabled() and _truthy("MARKET_TOOLS_ODDSAPI_COLLECT", False)


def serves_oddsapi() -> bool:
    return snapshot_mode() or oddsapi_enabled()


def blocks_sgo() -> bool:
    return serves_oddsapi()


def market_tools_provider() -> str:
    if snapshot_mode():
        return PROVIDER_SNAPSHOT
    if oddsapi_enabled():
        return PROVIDER_ODDSAPI
    return PROVIDER_SGO


def flag_status() -> dict:
    return {
        "provider": market_tools_provider(),
        "sgo_default": market_tools_provider() == PROVIDER_SGO,
        "snapshot": snapshot_mode(),
        "snapshot_development_only": True,
        "oddsapi_enabled": oddsapi_enabled(),
        "collect_enabled": collect_enabled(),
        "browsing_triggers_upstream": False,
        "cutover_active": oddsapi_enabled() and is_production(),
        "production": is_production(),
    }
