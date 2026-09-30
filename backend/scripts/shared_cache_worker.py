"""One-shot Redis cache worker for isolated verification. Zero provider HTTP."""

from __future__ import annotations

import json
import os
import sys


def _home_american(preview: dict):
    for event in preview.get("events") or []:
        for book in event.get("books") or []:
            quote = (book.get("h2h") or {}).get("home")
            if quote:
                return quote.get("american")
    return None


def main() -> int:
    os.environ.setdefault("MARKET_TOOLS_ODDSAPI_ENABLED", "true")
    os.environ.setdefault("MARKET_TOOLS_ODDSAPI_COLLECT", "false")
    os.environ.setdefault("MARKET_TOOLS_PROVIDER", "sgo")
    from market_snapshot.cache import acquire_collect_lock, public_preview, release_collect_lock, reset_for_tests
    from market_snapshot.collector import load_labeled_fixture

    cmd = sys.argv[1] if len(sys.argv) > 1 else "read"
    if cmd == "reset":
        reset_for_tests()
        print(json.dumps({"ok": True, "op": "reset"}))
        return 0
    if cmd == "ingest":
        name = sys.argv[2]
        result = load_labeled_fixture(name)
        preview = public_preview()
        print(json.dumps({
            "ok": result.get("ok"),
            "american": result.get("american") or _home_american(preview),
            "label": result.get("label") or preview.get("fixture_label"),
            "cache_backend": preview.get("cache_backend") or result.get("cache_backend"),
            "unavailable": preview.get("unavailable", False),
            "http_requests": 0,
            "generation": preview.get("generation"),
        }))
        return 0
    if cmd == "read":
        preview = public_preview()
        print(json.dumps({
            "unavailable": preview.get("unavailable", False),
            "reason": preview.get("reason"),
            "stale": preview.get("stale", False),
            "american": _home_american(preview),
            "cache_backend": preview.get("cache_backend") or (preview.get("cache") or {}).get("cache_backend"),
            "events": len(preview.get("events") or []),
            "http_requests": 0,
            "generation": preview.get("generation"),
            "fixture_label": preview.get("fixture_label"),
        }))
        return 0
    if cmd == "lock":
        ok, reason = acquire_collect_lock()
        print(json.dumps({"acquired": ok, "reason": reason, "http_requests": 0}))
        return 0
    if cmd == "unlock":
        release_collect_lock()
        print(json.dumps({"ok": True, "op": "unlock"}))
        return 0
    print(json.dumps({"error": f"unknown command {cmd}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
