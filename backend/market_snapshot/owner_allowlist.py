"""Request-scoped owner allowlist for Market Tools HTTP. Collection stays off.

Unset MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS is a no-op. Do not set
MARKET_TOOLS_ODDSAPI_ENABLED to simulate owner access.

Owner Odds API serving also requires Market Tools subscription entitlement.
Other customers stay on SportsGameOdds while global flags are off.
"""

from __future__ import annotations

import os


def owner_account_allowlist() -> frozenset[str]:
    raw = os.getenv("MARKET_TOOLS_ODDSAPI_ACCOUNT_IDS", "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def owner_account_allows_oddsapi(user) -> bool:
    """True only for an authenticated allowlisted account while global flags stay off.

    Collection is never enabled by this hook.
    """
    from market_snapshot.flags import collect_enabled, oddsapi_enabled

    if oddsapi_enabled() or collect_enabled():
        return False
    allow = owner_account_allowlist()
    if not allow or user is None:
        return False
    uid = str(getattr(user, "id", "") or "").strip().lower()
    email = str(getattr(user, "email", "") or "").strip().lower()
    return bool(uid and uid in allow) or bool(email and email in allow)


async def request_serves_oddsapi(user=None, db=None) -> bool:
    """Odds API Market Tools HTTP for this request only.

    Global cutover still uses serves_oddsapi(). Owner allowlist is additional,
    request-scoped, and ignored unless the account is Market Tools entitled.
    """
    from market_snapshot.flags import serves_oddsapi

    if serves_oddsapi():
        return True
    if not owner_account_allows_oddsapi(user) or db is None:
        return False
    from market_snapshot.entitlement import plan_entitlement

    info = await plan_entitlement(user, db)
    return bool(info.get("entitled"))
