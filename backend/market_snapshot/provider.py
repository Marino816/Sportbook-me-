"""Market Tools provider switch. SGO remains the default."""

from __future__ import annotations

from market_snapshot.flags import (  # noqa: F401
    PROVIDER_ODDSAPI,
    PROVIDER_SGO,
    PROVIDER_SNAPSHOT,
    blocks_sgo,
    collect_enabled,
    flag_status,
    market_tools_provider,
    oddsapi_enabled,
    serves_oddsapi,
    snapshot_mode,
)


def is_snapshot() -> bool:
    return snapshot_mode()


def snapshot_blocks_sgo() -> bool:
    """When Odds API snapshot or flagged Odds API serving is on, do not call SGO."""
    return blocks_sgo()
