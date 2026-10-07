"""Market Tools provider switch. SGO remains the default."""

from __future__ import annotations

from market_snapshot.flags import (  # noqa: F401
    PROVIDER_ODDSAPI,
    PROVIDER_SGO,
    PROVIDER_SNAPSHOT,
    blocks_sgo,
    collect_enabled,
    fixture_ingest_allowed,
    flag_status,
    market_tools_provider,
    oddsapi_enabled,
    requires_shared_redis,
    serves_oddsapi,
    snapshot_mode,
)
from market_snapshot.owner_allowlist import (  # noqa: F401
    owner_account_allowlist,
    owner_account_allows_oddsapi,
    request_serves_oddsapi,
)


async def request_market_tools_provider(user=None, db=None) -> str:
    """Request-scoped provider label for Market Tools HTTP.

    Global flags stay off during the owner test. Allowlisted entitled
    requests report oddsapi so the website switches UI; everyone else
    keeps the global SGO label.
    """
    if await request_serves_oddsapi(user, db):
        return PROVIDER_SNAPSHOT if snapshot_mode() else PROVIDER_ODDSAPI
    return market_tools_provider()


def is_snapshot() -> bool:
    return snapshot_mode()


def snapshot_blocks_sgo() -> bool:
    """When Odds API snapshot or flagged Odds API serving is on, do not call SGO."""
    return blocks_sgo()
