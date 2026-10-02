"""Authorized 4-request / 12-credit timed Odds API refresh. Mario authorized 2026-10-02.

No discovery HTTP. No retries. Failed attempts count toward the cap. Production flags stay off.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from market_snapshot.access import PRIVATE_DIR, load_key
from market_snapshot.bounded_fetch import OddsImportError, _load_ledger, get_json, redact_url
from market_snapshot.final_refresh_test import (
    HOST,
    build_requests,
    saved_event_suitability,
    _parse_iso,
)
from market_snapshot.timed_refresh_plan import FEATURED_NEAR_SECONDS, PROPS_NEAR_SECONDS

AUTHORIZED = True
MAX_HTTP = 4
MAX_CREDITS = 12
RESULT_PATH = PRIVATE_DIR / "timed_refresh_result.json"
REDACTED_REPO_PATH = Path(__file__).resolve().parent / "timed_refresh_result.redacted.json"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _wait_until(start_iso: str | None, min_seconds: int) -> dict:
    start = _parse_iso(start_iso)
    now = datetime.now(timezone.utc)
    if start is None:
        time.sleep(min_seconds)
        return {"waited_seconds": min_seconds, "from": start_iso, "reason": "unparsed_start_slept_full"}
    elapsed = (now - start).total_seconds()
    remaining = min_seconds - elapsed
    if remaining > 0:
        time.sleep(remaining + 0.25)
        waited = remaining + 0.25
    else:
        waited = 0.0
    return {
        "waited_seconds": round(waited, 3),
        "elapsed_before_wait": round(elapsed, 3),
        "required_seconds": min_seconds,
        "from": start_iso,
        "resumed_at": _utc(),
    }


def _event_in_featured(payload, event_id: str) -> dict | None:
    if not isinstance(payload, list):
        return None
    for row in payload:
        if isinstance(row, dict) and str(row.get("id") or "") == event_id:
            return row
    return None


def _usage(rec: dict) -> dict:
    headers = rec.get("usage_headers") or {}
    return {
        "status": rec.get("status"),
        "retrieved_at": rec.get("retrieved_at"),
        "sha256": rec.get("sha256"),
        "record_count": rec.get("record_count"),
        "url_redacted": rec.get("url_redacted") or redact_url(HOST + rec.get("path", "")),
        "x-requests-last": headers.get("x-requests-last"),
        "x-requests-remaining": headers.get("x-requests-remaining"),
        "x-requests-used": headers.get("x-requests-used"),
        "actual_credit_cost": rec.get("actual_credit_cost"),
        "path": rec.get("path"),
    }


def _source_stamps(event: dict | None) -> list[str]:
    stamps = []
    if not event:
        return stamps
    for book in event.get("bookmakers") or []:
        if book.get("last_update"):
            stamps.append(str(book.get("last_update")))
        for market in book.get("markets") or []:
            if market.get("last_update"):
                stamps.append(str(market.get("last_update")))
    return stamps


def _prop_coverage(payload) -> dict:
    if not payload:
        return {
            "empty": True,
            "players": 0,
            "markets": [],
            "bookmakers": 0,
            "note": "Empty props body. This is a coverage gap, not a passing props interval test.",
        }
    books = payload.get("bookmakers") if isinstance(payload, dict) else None
    if not books:
        return {
            "empty": True,
            "players": 0,
            "markets": [],
            "bookmakers": 0,
            "note": "Props response had no bookmakers. Coverage gap, not a passing props test.",
        }
    markets = []
    players = set()
    for book in books:
        for market in book.get("markets") or []:
            key = market.get("key")
            if key:
                markets.append(key)
            for outcome in market.get("outcomes") or []:
                name = outcome.get("description") or outcome.get("name")
                if name:
                    players.add(name)
    unique_markets = sorted(set(markets))
    return {
        "empty": False,
        "players": len(players),
        "markets": unique_markets,
        "bookmakers": len(books),
        "note": None,
    }


def _write_redis(featured_list, props_payload, retrieved_at: str, label: str) -> dict:
    os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "true"
    os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    os.environ.setdefault("NODE_ENV", "development")
    from market_snapshot.cache import public_preview, replace_from_payloads, stats

    if isinstance(props_payload, dict):
        props_payload = dict(props_payload)
        props_payload.setdefault("sport_key", "americanfootball_nfl")
    payloads = {
        "sports": [{"key": "americanfootball_nfl", "title": "NFL", "active": True}],
        "odds": {"americanfootball_nfl": featured_list or []},
        "player_props": props_payload if isinstance(props_payload, dict) else None,
        "retrieved_at": retrieved_at,
        "index": {"imported_at": retrieved_at, "http_requests_used": 0},
    }
    preview = replace_from_payloads(payloads, retrieved_at=retrieved_at, source=label)
    pub = public_preview()
    return {
        "ok": not preview.get("unavailable") and not preview.get("rejected_stale_capture"),
        "cache_backend": pub.get("cache_backend") or preview.get("cache_backend"),
        "generation": pub.get("generation") or preview.get("generation"),
        "retrieved_at": pub.get("retrieved_at"),
        "event_count": len(pub.get("events") or []),
        "player_props": len(pub.get("player_props") or []),
        "rejected_stale_capture": bool(preview.get("rejected_stale_capture")),
        "unavailable": bool(preview.get("unavailable")),
        "stats": stats(),
    }


def execute_authorized_timed_test() -> dict:
    """Run the 4 HTTP / 12 credit interval test. No retries. No discovery."""
    if not AUTHORIZED:
        return {"executed": False, "reason": "not_authorized"}
    key = load_key()
    if not key:
        return {"executed": False, "reason": "ODDS_API_KEY missing", "provider_http": 0}

    suitability = saved_event_suitability()
    report = {
        "authorized": True,
        "executed_at": _utc(),
        "production_flags_remain_off": True,
        "max_http": MAX_HTTP,
        "max_credits": MAX_CREDITS,
        "provider_http": 0,
        "credits_used": 0,
        "captures": [],
        "waits": [],
        "event_suitability": {
            k: suitability.get(k)
            for k in ("selected_event_id", "suitable", "reason", "evaluated_at_utc", "discovery_http")
        },
        "selected": suitability.get("selected"),
        "retries": 0,
        "discovery_http": 0,
        "ok": False,
    }
    if not suitability.get("suitable"):
        report["reason"] = suitability.get("reason")
        report["stopped"] = "no_suitable_saved_event"
        _save(report)
        return report

    event_id = suitability["selected_event_id"]
    requests = build_requests(event_id)
    ledger = _load_ledger()
    budget = [MAX_HTTP, MAX_CREDITS]
    featured_list = []
    props_payload = None
    confirmed_event = None
    http_before = int(ledger.get("http_count") or 0)
    credits_before = int(ledger.get("credits_charged") or 0)

    def _call(row: dict) -> dict:
        rec = get_json(
            row["path"],
            row["query"],
            max_credit_cost=int(row["credits_max"]),
            budget=budget,
            ledger=ledger,
            key=key,
        )
        report["provider_http"] = int(ledger.get("http_count") or 0) - http_before
        report["credits_used"] = int(ledger.get("credits_charged") or 0) - credits_before
        return rec

    try:
        featured_1_spec = requests[0]
        rec1 = _call(featured_1_spec)
        featured_list = rec1.get("payload") if isinstance(rec1.get("payload"), list) else []
        found = _event_in_featured(featured_list, event_id)
        if found is None:
            cache = _write_redis(featured_list, None, rec1["retrieved_at"], "timed_featured_1")
            report["captures"].append({
                "capture": "featured_1",
                **_usage(rec1),
                "event_confirmed": False,
                "featured_event_count": len(featured_list),
                "cache": cache,
            })
            report["stopped"] = "saved_event_missing_from_featured_1"
            report["props_test"] = "not_run"
            report["ok_note"] = "No extra discovery or retries. Remaining budget unused."
            _save(report)
            return report
        confirmed_event = found
        cache1 = _write_redis(featured_list, None, rec1["retrieved_at"], "timed_featured_1")
        report["captures"].append({
            "capture": "featured_1",
            **_usage(rec1),
            "event_confirmed": True,
            "event_id": event_id,
            "home_team": confirmed_event.get("home_team"),
            "away_team": confirmed_event.get("away_team"),
            "commence_time": confirmed_event.get("commence_time"),
            "bookmakers": len(confirmed_event.get("bookmakers") or []),
            "source_timestamps": _source_stamps(confirmed_event),
            "cache": cache1,
        })
        report["confirmed_event_id"] = event_id

        props_1_spec = next(r for r in requests if r["capture"] == "props_1")
        rec2 = _call(props_1_spec)
        props_payload = rec2.get("payload") if isinstance(rec2.get("payload"), dict) else rec2.get("payload")
        props_cov = _prop_coverage(props_payload if isinstance(props_payload, dict) else None)
        cache2 = _write_redis(featured_list, props_payload if isinstance(props_payload, dict) else None, rec2["retrieved_at"], "timed_props_1")
        report["captures"].append({
            "capture": "props_1",
            **_usage(rec2),
            "event_id": event_id,
            "coverage": props_cov,
            "cache": cache2,
        })
        report["props_1_empty"] = bool(props_cov.get("empty"))

        wait_f = _wait_until(rec1["retrieved_at"], FEATURED_NEAR_SECONDS)
        report["waits"].append({"name": "featured", **wait_f})
        featured_2_spec = next(r for r in requests if r["capture"] == "featured_2")
        rec3 = _call(featured_2_spec)
        featured_list = rec3.get("payload") if isinstance(rec3.get("payload"), list) else []
        found2 = _event_in_featured(featured_list, event_id)
        cache3 = _write_redis(featured_list, props_payload if isinstance(props_payload, dict) else None, rec3["retrieved_at"], "timed_featured_2")
        report["captures"].append({
            "capture": "featured_2",
            **_usage(rec3),
            "event_still_present": bool(found2),
            "elapsed_from_featured_1_seconds": round(
                ((_parse_iso(rec3["retrieved_at"]) - _parse_iso(rec1["retrieved_at"])).total_seconds()
                 if _parse_iso(rec3["retrieved_at"]) and _parse_iso(rec1["retrieved_at"]) else -1),
                3,
            ),
            "source_timestamps": _source_stamps(found2),
            "body_changed": rec3.get("sha256") != rec1.get("sha256"),
            "cache": cache3,
        })

        wait_p = _wait_until(rec2["retrieved_at"], PROPS_NEAR_SECONDS)
        report["waits"].append({"name": "props", **wait_p})
        props_2_spec = next(r for r in requests if r["capture"] == "props_2")
        rec4 = _call(props_2_spec)
        props_payload = rec4.get("payload") if isinstance(rec4.get("payload"), dict) else rec4.get("payload")
        props_cov2 = _prop_coverage(props_payload if isinstance(props_payload, dict) else None)
        cache4 = _write_redis(featured_list, props_payload if isinstance(props_payload, dict) else None, rec4["retrieved_at"], "timed_props_2")
        elapsed_p = -1
        if _parse_iso(rec4["retrieved_at"]) and _parse_iso(rec2["retrieved_at"]):
            elapsed_p = (_parse_iso(rec4["retrieved_at"]) - _parse_iso(rec2["retrieved_at"])).total_seconds()
        report["captures"].append({
            "capture": "props_2",
            **_usage(rec4),
            "event_id": event_id,
            "coverage": props_cov2,
            "elapsed_from_props_1_seconds": round(elapsed_p, 3),
            "body_changed": rec4.get("sha256") != rec2.get("sha256"),
            "cache": cache4,
        })
        report["props_2_empty"] = bool(props_cov2.get("empty"))
        featured_elapsed = report["captures"][2]["elapsed_from_featured_1_seconds"]
        props_interval_ok = elapsed_p >= PROPS_NEAR_SECONDS
        featured_interval_ok = featured_elapsed >= FEATURED_NEAR_SECONDS
        props_covered = (not report["props_1_empty"]) or (not report["props_2_empty"])
        report["interval"] = {
            "featured_ok": featured_interval_ok,
            "props_wait_ok": props_interval_ok,
            "props_coverage_ok": props_covered,
            "featured_elapsed_seconds": featured_elapsed,
            "props_elapsed_seconds": round(elapsed_p, 3),
        }
        report["props_test"] = "passed" if props_covered and props_interval_ok else "coverage_gap_or_interval_fail"
        report["ok"] = bool(
            featured_interval_ok
            and report["provider_http"] <= MAX_HTTP
            and report["credits_used"] <= MAX_CREDITS
            and cache4.get("cache_backend") == "redis"
        )
        report["props_passing_interval_test"] = bool(props_covered and props_interval_ok)
        if not props_covered:
            report["ok_note"] = (
                "Featured interval and Redis path may pass. Empty props is a coverage gap, "
                "not a passing props refresh test."
            )
        report["internal_api"] = _prove_internal_api(
            retrieved_at=rec4["retrieved_at"],
            event_id=event_id,
            home=confirmed_event.get("home_team") if confirmed_event else None,
            away=confirmed_event.get("away_team") if confirmed_event else None,
        )
        report["chrome"] = _prove_chrome(
            retrieved_at=rec4["retrieved_at"],
            event_id=event_id,
            home=confirmed_event.get("home_team") if confirmed_event else None,
            away=confirmed_event.get("away_team") if confirmed_event else None,
        )
        restored = _restore_preview()
        report["preview_restored"] = restored
        report["path_proved"] = bool(
            cache4.get("cache_backend") == "redis"
            and (report["internal_api"] or {}).get("ok")
            and (report["chrome"] or {}).get("ok")
        )
        report["ok"] = bool(report["ok"] and report["path_proved"])
    except OddsImportError as exc:
        report["stopped"] = str(exc)
        report["status"] = exc.status
        report["provider_http"] = int(ledger.get("http_count") or 0) - http_before
        report["credits_used"] = int(ledger.get("credits_charged") or 0) - credits_before
        report["retries"] = 0
    _save(report)
    return report


def _load_e2e_env() -> None:
    path = PRIVATE_DIR / "e2e.env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _prove_internal_api(*, retrieved_at: str, event_id: str, home, away) -> dict:
    _load_e2e_env()
    api = (os.environ.get("SBME_E2E_API") or "http://127.0.0.1:8010/api").rstrip("/")
    email = os.environ.get("SBME_E2E_EMAIL") or ""
    password = os.environ.get("SBME_E2E_PASSWORD") or ""
    if not email or not password:
        return {"ok": False, "blocker": "e2e credentials missing"}
    from market_snapshot.e2e_chrome import _api_login
    import urllib.request
    token = _api_login(api, email, password)
    if not token:
        return {"ok": False, "blocker": "login_failed", "api": api}
    req = urllib.request.Request(
        f"{api}/market-tools/internal/snapshot",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "blocker": str(exc), "api": api}
    data = body.get("data") or {}
    events = data.get("events") or []
    match = next((e for e in events if str(e.get("source_event_id") or e.get("id") or "").endswith(event_id) or event_id in str(e.get("id") or "")), None)
    if match is None and home:
        match = next((e for e in events if e.get("home_team") == home and e.get("away_team") == away), None)
    return {
        "ok": bool(
            data.get("cache_backend") == "redis"
            and data.get("retrieved_at")
            and match
        ),
        "api": api,
        "cache_backend": data.get("cache_backend"),
        "retrieved_at": data.get("retrieved_at"),
        "generation": data.get("generation"),
        "event_count": len(events),
        "player_props": len(data.get("player_props") or []),
        "event_found": bool(match),
        "home_team": (match or {}).get("home_team"),
        "away_team": (match or {}).get("away_team"),
        "expected_retrieved_at": retrieved_at,
        "retrieved_at_matches": data.get("retrieved_at") == retrieved_at,
        "browsing_triggers_upstream": data.get("browsing_triggers_upstream"),
    }


def _prove_chrome(*, retrieved_at: str, event_id: str, home, away) -> dict:
    _load_e2e_env()
    os.environ.setdefault("SBME_E2E_WEB", "http://127.0.0.1:3001")
    os.environ.setdefault("SBME_E2E_API", "http://127.0.0.1:8010/api")
    try:
        from market_snapshot.e2e_chrome import prove_live_snapshot_in_chrome
        return prove_live_snapshot_in_chrome(
            retrieved_at=retrieved_at,
            event_id=event_id,
            home=home,
            away=away,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "blocker": str(exc)}


def _restore_preview() -> dict:
    os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "true"
    os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
    from market_snapshot.cache import restore_saved_preview, stats
    preview = restore_saved_preview()
    return {
        "ok": not preview.get("unavailable"),
        "ingest_source": preview.get("ingest_source"),
        "cache_backend": preview.get("cache_backend"),
        "event_count": len(preview.get("events") or []),
        "retrieved_at": preview.get("retrieved_at"),
        "stats": stats(),
    }


def _save(report: dict) -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n")
    os.chmod(RESULT_PATH, 0o600)
    redacted = json.loads(json.dumps(report, default=str))
    REDACTED_REPO_PATH.write_text(json.dumps(redacted, indent=2) + "\n")


def main() -> int:
    report = execute_authorized_timed_test()
    print(json.dumps({
        "ok": report.get("ok"),
        "provider_http": report.get("provider_http"),
        "credits_used": report.get("credits_used"),
        "confirmed_event_id": report.get("confirmed_event_id"),
        "props_test": report.get("props_test"),
        "interval": report.get("interval"),
        "stopped": report.get("stopped"),
        "captures": [
            {
                "capture": c.get("capture"),
                "status": c.get("status"),
                "retrieved_at": c.get("retrieved_at"),
                "x-requests-last": c.get("x-requests-last"),
                "x-requests-remaining": c.get("x-requests-remaining"),
                "cache_backend": (c.get("cache") or {}).get("cache_backend"),
                "event_confirmed": c.get("event_confirmed"),
                "empty_props": (c.get("coverage") or {}).get("empty"),
            }
            for c in report.get("captures") or []
        ],
    }, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
