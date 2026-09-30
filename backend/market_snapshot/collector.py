"""Production-capable Odds API collector. HTTP only when MARKET_TOOLS_ODDSAPI_COLLECT is on."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from market_snapshot.cache import replace_from_payloads, stats
from market_snapshot.flags import collect_enabled, oddsapi_enabled
from market_snapshot.scheduler import quota_allows

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FEATURED = "h2h,spreads,totals"
REGION = "us"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def collect(*, used_month: int = 0, used_day: int = 0, max_credit_cost: int = 3) -> dict:
    """Scheduled collection. Browsing never calls this.

    Returns skipped with zero HTTP unless both feature flags are on.
    """
    if not oddsapi_enabled() or not collect_enabled():
        return {
            "ok": False,
            "skipped": True,
            "http_requests": 0,
            "reason": "MARKET_TOOLS_ODDSAPI_COLLECT is off (and/or MARKET_TOOLS_ODDSAPI_ENABLED is off)",
            "browsing_triggers_upstream": False,
        }
    if not quota_allows(max_credit_cost, used_month, used_day):
        return {
            "ok": False,
            "skipped": True,
            "http_requests": 0,
            "reason": "quota_stop",
            "browsing_triggers_upstream": False,
        }
    from market_snapshot.access import load_key
    from market_snapshot.bounded_fetch import OddsImportError, get_json, _load_ledger

    key = load_key()
    if not key:
        return {"ok": False, "skipped": True, "http_requests": 0, "reason": "ODDS_API_KEY missing"}
    ledger = _load_ledger()
    budget = [1, max_credit_cost]
    rec = get_json(
        "/v4/sports/americanfootball_nfl/odds",
        {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"},
        max_credit_cost=max_credit_cost,
        budget=budget,
        ledger=ledger,
        key=key,
    )
    payloads = {
        "sports": [{"key": "americanfootball_nfl", "title": "NFL"}],
        "odds": {"americanfootball_nfl": rec.get("payload") or []},
        "retrieved_at": rec.get("retrieved_at") or _utc(),
        "index": {"imported_at": rec.get("retrieved_at"), "http_requests_used": 1},
    }
    preview = replace_from_payloads(
        payloads,
        retrieved_at=payloads["retrieved_at"],
        fixture_label=None,
        source="collector",
    )
    return {
        "ok": True,
        "skipped": False,
        "http_requests": 1,
        "status": rec.get("status"),
        "generation": preview.get("generation"),
        "cache": stats(),
    }


def load_labeled_fixture(name: str) -> dict:
    """Replace shared cache from a labeled local fixture. No provider HTTP."""
    path = FIXTURE_DIR / name
    payloads = json.loads(path.read_text())
    if not payloads.get("not_customer_data"):
        raise ValueError(f"{name} is not marked not_customer_data")
    label = payloads.get("label") or name
    retrieved = payloads.get("retrieved_at") or _utc()
    preview = replace_from_payloads(
        payloads,
        retrieved_at=retrieved,
        fixture_label=label,
        source="fixture",
    )
    home = _home_h2h(preview)
    return {
        "ok": True,
        "http_requests": 0,
        "label": label,
        "retrieved_at": preview.get("retrieved_at"),
        "source_timestamp": home.get("source_timestamp") if home else None,
        "american": home.get("american") if home else None,
        "generation": preview.get("generation"),
        "cache_backend": preview.get("cache_backend"),
        "event_id": (preview.get("events") or [{}])[0].get("id"),
    }


def _home_h2h(preview: dict) -> dict | None:
    for event in preview.get("events") or []:
        for book in event.get("books") or []:
            quote = (book.get("h2h") or {}).get("home")
            if quote:
                return quote
    return None


def verify_fixture_replacement() -> dict:
    """Load A then B. Prove cache and snapshot payload prices change. Zero HTTP."""
    from market_snapshot.cache import public_preview, reset_for_tests

    reset_for_tests()
    first = load_labeled_fixture("fixture_a_baseline.json")
    after_a = public_preview()
    second = load_labeled_fixture("fixture_b_price_change.json")
    after_b = public_preview()
    home_a = _home_h2h(after_a)
    home_b = _home_h2h(after_b)
    return {
        "http_requests": 0,
        "fixture_a": first,
        "fixture_b": second,
        "price_changed": (home_a or {}).get("american") != (home_b or {}).get("american"),
        "source_timestamp_changed": (home_a or {}).get("source_timestamp") != (home_b or {}).get("source_timestamp"),
        "retrieved_at_changed": after_a.get("retrieved_at") != after_b.get("retrieved_at"),
        "source_timestamp_distinct_from_retrieved_a": (home_a or {}).get("source_timestamp") != after_a.get("retrieved_at"),
        "source_timestamp_distinct_from_retrieved_b": (home_b or {}).get("source_timestamp") != after_b.get("retrieved_at"),
        "generation_advanced": (after_b.get("generation") or 0) > (after_a.get("generation") or 0),
        "ui_payload_home_american_a": (home_a or {}).get("american"),
        "ui_payload_home_american_b": (home_b or {}).get("american"),
        "labels": [first.get("label"), second.get("label")],
        "not_customer_data": True,
    }
