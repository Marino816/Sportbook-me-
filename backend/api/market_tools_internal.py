"""Provider-independent Market Tools internal API. Auth + plan entitlement. Zero provider HTTP in snapshot mode."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.utils import wrap_data
from models.database import get_db
from models.domain import User
from sqlalchemy.ext.asyncio import AsyncSession
from market_snapshot.entitlement import plan_entitlement, require_market_tools_entitlement
from market_snapshot.flags import fixture_ingest_allowed
from market_snapshot.provider import flag_status, serves_oddsapi, market_tools_provider

router = APIRouter(tags=["SB-Me Market Tools Internal"])

ALLOWED_FIXTURES = {
    "fixture_a_baseline.json",
    "fixture_a_refresh_same_price.json",
    "fixture_b_price_change.json",
}


class ParlayInternalRequest(BaseModel):
    leg_ids: list[str] = Field(default_factory=list)
    legs: list[dict] = Field(default_factory=list)
    stake: float = 100.0


class ResolveRequest(BaseModel):
    event_id: str = ""
    id: str = ""
    legs: list[dict] = Field(default_factory=list)


def _require_oddsapi_serve() -> None:
    if not serves_oddsapi():
        raise HTTPException(
            status_code=404,
            detail="Internal Odds API Market Tools are available only in snapshot mode or when MARKET_TOOLS_ODDSAPI_ENABLED=true.",
        )


@router.get("/internal/status")
async def market_tools_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from market_snapshot.cache import stats
    from market_snapshot.cutover import activation_state
    from market_snapshot.scheduler import CONTINUOUS_FETCH_ENABLED, CONFIG

    entitled = await plan_entitlement(user, db)
    provider = market_tools_provider()
    flags = flag_status()
    payload = {
        "provider": provider,
        "snapshot": flags["snapshot"],
        "development_only_switch": True,
        "oddsapi_enabled": flags["oddsapi_enabled"],
        "collect_enabled": flags["collect_enabled"],
        "cutover_active": flags["cutover_active"],
        "auth": {
            "user_id": user.id,
            "is_pro": bool(getattr(user, "is_pro", False)),
            "role": getattr(user, "role", "user"),
            "authenticated": True,
            "entitled": entitled["entitled"],
            "plan": entitled["plan"],
            "plan_status": entitled["status"],
        },
        "entitlement": entitled,
        "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        "browsing_triggers_upstream": False,
        "unsupported": {
            "movement": "unavailable",
            "period_markets": "unavailable",
            "alternate_markets": "unavailable",
            "sgp_quotes": "unavailable",
        },
        "labels": {
            "fair_odds": "Market-derived fair odds",
            "consensus": "Sportsbook consensus",
            "notice": "Saved odds—not live",
        },
        "activation": activation_state(),
    }
    if serves_oddsapi():
        payload["cache"] = stats()
        payload["config"] = {"enabled": CONFIG["enabled"], "browsing_triggers_upstream": CONFIG["browsing_triggers_upstream"]}
    return wrap_data(payload, source="cached" if serves_oddsapi() else "sgo_nested_cache")


@router.get("/internal/snapshot")
async def market_tools_snapshot(user: User = Depends(require_market_tools_entitlement)):
    _require_oddsapi_serve()
    from market_snapshot.cache import public_preview, stats

    data = public_preview()
    data["auth"] = {
        "user_id": user.id,
        "is_pro": bool(getattr(user, "is_pro", False)),
        "entitled": True,
    }
    data["cache"] = stats()
    return wrap_data(data, source="cached")


@router.post("/internal/parlay")
async def market_tools_parlay(body: ParlayInternalRequest, user: User = Depends(require_market_tools_entitlement)):
    _require_oddsapi_serve()
    from market_snapshot.cache import parlay_from_body, stats

    result = parlay_from_body(body.model_dump())
    result["cache"] = stats()
    result["user_id"] = user.id
    return wrap_data(result, source="cached")


@router.post("/internal/resolve")
async def market_tools_resolve(body: ResolveRequest, user: User = Depends(require_market_tools_entitlement)):
    _require_oddsapi_serve()
    from market_snapshot.cache import resolve_saved

    if body.legs:
        return wrap_data({
            "legs": [resolve_saved(leg) for leg in body.legs],
            "sgo_event_id": None,
        }, source="cached")
    raw = body.id or body.event_id
    return wrap_data(resolve_saved(raw), source="cached")


@router.post("/internal/fixtures/{name}")
async def market_tools_load_fixture(name: str, user: User = Depends(require_market_tools_entitlement)):
    """Load a labeled local fixture into the shared cache. No provider HTTP. Dev ingest only."""
    _require_oddsapi_serve()
    if not fixture_ingest_allowed():
        raise HTTPException(status_code=404, detail="Fixture ingest is off.")
    filename = name if name.endswith(".json") else f"{name}.json"
    if filename not in ALLOWED_FIXTURES:
        raise HTTPException(status_code=400, detail="Unknown labeled fixture.")
    from market_snapshot.collector import load_labeled_fixture

    result = load_labeled_fixture(filename)
    result["not_customer_data"] = True
    return wrap_data(result, source="fixture")


@router.post("/internal/restore-saved-preview")
async def market_tools_restore_saved(user: User = Depends(require_market_tools_entitlement)):
    """Replace labeled-fixture cache with the saved Odds API snapshot. Zero provider HTTP."""
    _require_oddsapi_serve()
    if not fixture_ingest_allowed():
        raise HTTPException(status_code=404, detail="Fixture ingest is off.")
    from market_snapshot.cache import restore_saved_preview, stats

    preview = restore_saved_preview()
    return wrap_data({
        "restored": True,
        "ingest_source": preview.get("ingest_source"),
        "event_count": len(preview.get("events") or []),
        "unavailable": preview.get("unavailable", False),
        "cache": stats(),
        "not_customer_data": False,
    }, source="saved_snapshot")
