"""Shared Market Tools Odds API cache. Browsing never triggers upstream HTTP."""

from __future__ import annotations

import json
from threading import Lock

from market_snapshot.adapter import build_preview, combine_parlay
from market_snapshot.compat import resolve_event, resolve_selection

REDIS_PREVIEW_KEY = "sbme:mt:oddsapi:preview"

_LOCK = Lock()
_PREVIEW: dict | None = None
_HITS = 0
_PARLAY_CALLS = 0
_PROVIDER_HTTP = 0
_GENERATION = 0
_BACKEND = "memory"


def reset_for_tests() -> None:
    global _PREVIEW, _HITS, _PARLAY_CALLS, _PROVIDER_HTTP, _GENERATION, _BACKEND
    with _LOCK:
        _PREVIEW = None
        _HITS = 0
        _PARLAY_CALLS = 0
        _PROVIDER_HTTP = 0
        _GENERATION = 0
        _BACKEND = "memory"
    client = _redis()
    if client is not None:
        try:
            client.delete(REDIS_PREVIEW_KEY)
        except Exception:
            pass


def _redis():
    try:
        from providers.redis_client import get_redis_client
        return get_redis_client()
    except Exception:
        return None


def _store(preview: dict) -> str:
    encoded = json.dumps(preview)
    client = _redis()
    if client is not None:
        try:
            client.set(REDIS_PREVIEW_KEY, encoded)
            return "redis"
        except Exception:
            pass
    return "memory"


def _load_redis() -> dict | None:
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(REDIS_PREVIEW_KEY)
    except Exception:
        return None
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def replace_from_payloads(
    payloads: dict,
    *,
    retrieved_at: str | None = None,
    fixture_label: str | None = None,
    source: str = "replace",
) -> dict:
    """Replace the shared cache. Never calls a provider."""
    global _PREVIEW, _GENERATION, _BACKEND
    preview = build_preview(payloads=payloads, retrieved_at=retrieved_at, fixture_label=fixture_label)
    preview["http_requests_used"] = 0
    preview["browsing_triggers_upstream"] = False
    preview["ingest_source"] = source
    with _LOCK:
        _GENERATION += 1
        preview["generation"] = _GENERATION
        backend = _store(preview)
        preview["cache_backend"] = backend
        _BACKEND = backend
        _PREVIEW = preview
        return preview


def get_preview(*, root=None) -> dict:
    global _PREVIEW, _HITS, _BACKEND
    with _LOCK:
        if root is not None:
            preview = build_preview(root=root)
            preview["http_requests_used"] = 0
            preview["browsing_triggers_upstream"] = False
            _PREVIEW = preview
            _HITS += 1
            return _PREVIEW
        if _PREVIEW is None:
            cached = _load_redis()
            if cached is not None:
                _PREVIEW = cached
                _BACKEND = "redis"
            else:
                preview = build_preview()
                preview["http_requests_used"] = 0
                preview["browsing_triggers_upstream"] = False
                preview["ingest_source"] = "saved_snapshot"
                preview["generation"] = _GENERATION
                backend = _store(preview)
                preview["cache_backend"] = backend
                _BACKEND = backend
                _PREVIEW = preview
        _HITS += 1
        return _PREVIEW


def public_preview() -> dict:
    payload = dict(get_preview())
    payload.pop("quote_index", None)
    payload["http_requests_used"] = 0
    payload["cache"] = stats()
    return payload


def stats() -> dict:
    return {
        "cache_hits": _HITS,
        "parlay_calls": _PARLAY_CALLS,
        "provider_http_this_process": _PROVIDER_HTTP,
        "browsing_triggers_upstream": False,
        "odds_api_http": 0,
        "sgo_http": 0,
        "generation": _GENERATION,
        "cache_backend": _BACKEND,
    }


def parlay_from_body(body: dict) -> dict:
    global _PARLAY_CALLS
    preview = get_preview()
    index = preview.get("quote_index") or {}
    events = preview.get("events") or []
    resolved_legs, unavailable = _legs_from_body(body, index, events)
    _PARLAY_CALLS += 1
    if unavailable:
        return {
            "ok": False,
            "unavailable": True,
            "reason": "One or more selections could not be mapped. Nothing was substituted.",
            "unavailable_legs": unavailable,
            "bookmaker_confirmed_quote": False,
            "combined_suppressed": True,
            "http_requests_used": 0,
        }
    result = combine_parlay(resolved_legs)
    result["http_requests_used"] = 0
    result["legs"] = [
        {
            "id": leg.get("id"),
            "event_id": leg.get("event_id"),
            "internal_event_id": leg.get("internal_event_id") or leg.get("event_id"),
            "source_event_id": leg.get("source_event_id"),
            "sgo_event_id": None,
            "market": leg.get("market"),
            "selection": leg.get("selection"),
            "player": leg.get("player"),
            "line": leg.get("line"),
            "bookmaker": leg.get("bookmaker"),
            "bookmaker_key": leg.get("bookmaker_key"),
            "american": leg.get("american"),
            "period": leg.get("period"),
            "source_timestamp": leg.get("source_timestamp"),
            "retrieved_at": leg.get("retrieved_at"),
        }
        for leg in resolved_legs
    ]
    return result


def _legs_from_body(body: dict, index: dict, events: list[dict]) -> tuple[list[dict], list[dict]]:
    raw_ids = body.get("leg_ids") or []
    raw_legs = body.get("legs") or []
    resolved: list[dict] = []
    unavailable: list[dict] = []
    items = list(raw_ids) + list(raw_legs)
    if not items:
        return [], []
    for item in items:
        if isinstance(item, str):
            quote = index.get(item)
            if quote:
                resolved.append(quote)
            else:
                unavailable.append(resolve_selection({"id": item}, index, events))
            continue
        if not isinstance(item, dict):
            unavailable.append({"unavailable": True, "reason": "Malformed selection."})
            continue
        mapped = resolve_selection(item, index, events)
        if mapped.get("unavailable"):
            unavailable.append(mapped)
            continue
        quote = index.get(mapped.get("id") or item.get("id"))
        if quote:
            resolved.append(quote)
        else:
            unavailable.append({
                "unavailable": True,
                "reason": "Selection is not in this snapshot. Nothing was substituted.",
                "saved_id": item.get("id"),
                "saved_event_id": item.get("event_id"),
                "sgo_event_id": None,
            })
    return resolved, unavailable


def resolve_saved(raw: str | dict) -> dict:
    preview = get_preview()
    if isinstance(raw, str):
        event = resolve_event(raw, preview.get("events") or [])
        if event.get("found"):
            return event
        return resolve_selection({"event_id": raw, "id": raw}, preview.get("quote_index") or {}, preview.get("events") or [])
    return resolve_selection(raw, preview.get("quote_index") or {}, preview.get("events") or [])
