"""Provider-independent snapshot contracts for Market Tools preview."""

from __future__ import annotations

from datetime import datetime, timezone

SNAPSHOT_LABEL = "Snapshot"
NOT_LIVE = "Saved provider snapshot — not a live update"
PARLAY_ANALYTICAL_NOTE = (
    "Combined price is an SB ME arithmetic product of decimal conversions. "
    "It is not a bookmaker-confirmed parlay quote. Same-game selections are not a confirmed SGP price."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def american_to_decimal(american: int | float | None) -> float | None:
    if american is None:
        return None
    try:
        n = int(american)
    except (TypeError, ValueError):
        return None
    if n > 0:
        return round(1.0 + n / 100.0, 4)
    if n < 0:
        return round(1.0 + 100.0 / abs(n), 4)
    return None


def decimal_to_american(decimal: float | None) -> int | None:
    if decimal is None or decimal <= 1.0:
        return None
    if decimal >= 2.0:
        return int(round((decimal - 1.0) * 100))
    return int(round(-100.0 / (decimal - 1.0)))


def line_key(point) -> str:
    if point is None or point == "":
        return ""
    try:
        return f"{float(point):g}"
    except (TypeError, ValueError):
        return str(point)
