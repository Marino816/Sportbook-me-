"""Odds API bookmaker keys vs the SB ME catalog. Never treat keys as SGO ids."""

from __future__ import annotations

from market_snapshot.consumers import unavailable

# Display-name matches only. Unknown keys stay unmapped.
ODDSAPI_KEY_TO_CATALOG_NAME = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "williamhill_us": "William Hill",
    "bovada": "Bovada",
    "betrivers": "BetRivers",
    "pointsbetus": "PointsBet",
    "caesars": "Caesars",
}


def map_oddsapi_book_key(key: str | None) -> dict:
    raw = (key or "").strip().lower()
    if not raw:
        return unavailable(
            capability="oddsapi_book_key",
            reason="Empty Odds API bookmaker key. Nothing was invented.",
            bookmaker_key=key,
        )
    name = ODDSAPI_KEY_TO_CATALOG_NAME.get(raw)
    if not name:
        return unavailable(
            capability="oddsapi_book_key",
            reason=f"No catalog mapping for Odds API book key {raw!r}. Nothing was invented.",
            bookmaker_key=raw,
        )
    return {
        "unavailable": False,
        "bookmaker_key": raw,
        "catalog_name": name,
        "sgo_id": None,
    }
