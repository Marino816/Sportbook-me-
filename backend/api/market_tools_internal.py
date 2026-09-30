"""Provider-independent Market Tools internal API. Auth required. Zero provider HTTP in snapshot mode."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.utils import wrap_data
from models.domain import User
from market_snapshot.provider import is_snapshot, market_tools_provider

router = APIRouter(tags=["SB-Me Market Tools Internal"])


class ParlayInternalRequest(BaseModel):
    leg_ids: list[str] = Field(default_factory=list)
    legs: list[dict] = Field(default_factory=list)
    stake: float = 100.0


class ResolveRequest(BaseModel):
    event_id: str = ""
    id: str = ""
    legs: list[dict] = Field(default_factory=list)


def _require_snapshot() -> None:
    if not is_snapshot():
        raise HTTPException(
            status_code=404,
            detail="Internal snapshot API is available only when MARKET_TOOLS_PROVIDER=oddsapi_snapshot.",
        )


@router.get("/internal/status")
async def market_tools_status(user: User = Depends(get_current_user)):
    from market_snapshot.cache import stats
    from market_snapshot.scheduler import CONTINUOUS_FETCH_ENABLED, CONFIG

    provider = market_tools_provider()
    payload = {
        "provider": provider,
        "snapshot": provider == "oddsapi_snapshot",
        "development_only_switch": True,
        "auth": {"user_id": user.id, "is_pro": bool(getattr(user, "is_pro", False)), "role": getattr(user, "role", "user")},
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
    }
    if is_snapshot():
        payload["cache"] = stats()
        payload["config"] = {"enabled": CONFIG["enabled"], "browsing_triggers_upstream": CONFIG["browsing_triggers_upstream"]}
    return wrap_data(payload, source="cached" if is_snapshot() else "sgo_nested_cache")


@router.get("/internal/snapshot")
async def market_tools_snapshot(user: User = Depends(get_current_user)):
    _require_snapshot()
    from market_snapshot.cache import public_preview, stats

    data = public_preview()
    data["auth"] = {"user_id": user.id, "is_pro": bool(getattr(user, "is_pro", False))}
    data["cache"] = stats()
    return wrap_data(data, source="cached")


@router.post("/internal/parlay")
async def market_tools_parlay(body: ParlayInternalRequest, user: User = Depends(get_current_user)):
    _require_snapshot()
    from market_snapshot.cache import parlay_from_body, stats

    result = parlay_from_body(body.model_dump())
    result["cache"] = stats()
    result["user_id"] = user.id
    return wrap_data(result, source="cached")


@router.post("/internal/resolve")
async def market_tools_resolve(body: ResolveRequest, user: User = Depends(get_current_user)):
    _require_snapshot()
    from market_snapshot.cache import resolve_saved

    if body.legs:
        return wrap_data({
            "legs": [resolve_saved(leg) for leg in body.legs],
            "sgo_event_id": None,
        }, source="cached")
    raw = body.id or body.event_id
    return wrap_data(resolve_saved(raw), source="cached")
