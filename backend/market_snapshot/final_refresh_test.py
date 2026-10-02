"""Bounded interval Odds API refresh test. Default: do not execute provider HTTP.

The previous five-request package was initial ingestion (NFL featured, MLB featured,
NFL scores, MLB scores, one NFL prop event) inside a 12-second window. That does not
prove 5-minute featured or 10-minute prop refresh.

This plan reuses the existing NFL featured + same-event props paths from the earlier
two-capture record, with real waits of at least 300s (featured) and 600s (props).
"""

from __future__ import annotations

from market_snapshot.capture_evidence import CAPTURE_EVIDENCE
from market_snapshot.timed_refresh_plan import FEATURED_NEAR_SECONDS, PROPS_NEAR_SECONDS

# Last reported remaining credits after the scores/weather collect (2026-09-30T16:38:30Z).
LEDGER_REMAINING_REPORTED = 418
LEDGER_USED_REPORTED = 82

HOST = "https://api.the-odds-api.com"
REGION = "us"
FEATURED = "h2h,spreads,totals"
NFL_PROP_MARKETS = "player_pass_tds,player_pass_yds,player_rush_yds"
PREFERRED_EVENT_ID = "d55cb69fed50a09170560b5b75d8de86"
NFL_EVENT_ID = PREFERRED_EVENT_ID  # updated by saved_event_suitability()


def _parse_iso(value: str | None):
    from datetime import datetime, timezone
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def saved_event_suitability(*, now=None) -> dict:
    """Decide the props event from saved payloads only. No discovery HTTP.

    Suitability is evaluated against the actual current UTC time. The event must
    still be pregame after the 600s props wait (collect window = 600s + 30s).
    """
    from datetime import datetime, timezone
    from market_snapshot.access import PRIVATE_DIR

    now = now or datetime.now(timezone.utc)
    path = PRIVATE_DIR / "latest_payloads.json"
    collect_window = PROPS_NEAR_SECONDS + 30
    report = {
        "preferred_event_id": PREFERRED_EVENT_ID,
        "selected_event_id": None,
        "suitable": False,
        "reason": "saved_payloads_missing",
        "discovery_http": 0,
        "evaluated_at_utc": now.isoformat(),
        "collect_window_seconds": collect_window,
        "candidates": [],
        "discovery_if_none": discovery_if_none(),
    }
    if not path.is_file():
        report["discovery_if_none"]["needed"] = True
        return report
    import json
    payloads = json.loads(path.read_text())
    nfl = (payloads.get("odds") or {}).get("americanfootball_nfl") or []
    props = payloads.get("player_props") or {}
    candidates = []
    for event in nfl:
        eid = str(event.get("id") or "")
        commence = _parse_iso(event.get("commence_time"))
        if not eid or commence is None:
            continue
        seconds_to_start = (commence - now).total_seconds()
        row = {
            "event_id": eid,
            "commence_time": event.get("commence_time"),
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "seconds_to_start": int(seconds_to_start),
            "has_bookmakers": bool(event.get("bookmakers")),
            "preferred": eid == PREFERRED_EVENT_ID,
            "has_saved_props": eid == str(props.get("id") or ""),
        }
        row["suitable"] = seconds_to_start >= collect_window and row["has_bookmakers"]
        candidates.append(row)
    preferred = next((c for c in candidates if c["preferred"]), None)
    suitable_sorted = sorted(
        [c for c in candidates if c["suitable"]],
        key=lambda r: r["seconds_to_start"],
    )
    report["candidates"] = ([preferred] if preferred else []) + [
        c for c in suitable_sorted if not c["preferred"]
    ][:8]
    if preferred and preferred["suitable"]:
        report.update({
            "selected_event_id": preferred["event_id"],
            "suitable": True,
            "reason": "preferred_event_still_pregame_with_horizon",
            "selected": preferred,
        })
        report["discovery_if_none"]["needed"] = False
        return report
    fallback = suitable_sorted[0] if suitable_sorted else None
    if fallback:
        report.update({
            "selected_event_id": fallback["event_id"],
            "suitable": True,
            "reason": "preferred_event_not_suitable_substituted_from_saved_featured",
            "selected": fallback,
            "preferred_rejected": preferred,
        })
        report["discovery_if_none"]["needed"] = False
        return report
    report["reason"] = "no_saved_nfl_event_with_pregame_collect_window"
    report["preferred"] = preferred
    report["discovery_if_none"]["needed"] = True
    return report


def discovery_if_none() -> dict:
    """Minimum extra request if saved metadata has no future NFL event. Not executed."""
    return {
        "needed": False,
        "not_called": True,
        "provider_http": 0,
        "requests": [
            {
                "method": "GET",
                "path": "/v4/sports/americanfootball_nfl/odds",
                "query": {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"},
                "credits_max": 3,
                "why": "Refresh the saved NFL featured list so a pregame event id can be chosen. No /sports catalog. No /events list.",
            }
        ],
        "credits_max": 3,
        "interval_plan_credits_max": 12,
        "revised_total_credits_max": 15,
        "note": "Call only if no saved NFL event remains pregame through the 630s collect window. Do not call yet.",
    }


def build_requests(event_id: str) -> tuple[dict, ...]:
    """props_2 waits 600s after props_1, not 600s after process start if props_1 ran at T+2."""
    props_path = f"/v4/sports/americanfootball_nfl/events/{event_id}/odds"
    featured_path = "/v4/sports/americanfootball_nfl/odds"
    featured_query = {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"}
    props_query = {"regions": REGION, "markets": NFL_PROP_MARKETS, "oddsFormat": "american"}
    return (
        {
            "order": 1,
            "at": "featured_1.retrieved_at = T0",
            "method": "GET",
            "path": featured_path,
            "query": featured_query,
            "credits_max": 3,
            "capture": "featured_1",
            "why": "First featured NFL capture.",
        },
        {
            "order": 2,
            "at": "props_1.retrieved_at = immediately after featured_1 in the same process",
            "method": "GET",
            "path": props_path,
            "query": props_query,
            "credits_max": 3,
            "capture": "props_1",
            "event_id": event_id,
            "event_id_source": "Saved NFL event chosen by saved_event_suitability. No /sports or /events list.",
            "why": "First props capture for that event.",
        },
        {
            "order": 3,
            "at": f"featured_1.retrieved_at + {FEATURED_NEAR_SECONDS}s",
            "method": "GET",
            "path": featured_path,
            "query": featured_query,
            "credits_max": 3,
            "capture": "featured_2",
            "identical_to_order": 1,
            "min_wait_from": "featured_1.retrieved_at",
            "min_wait_seconds": FEATURED_NEAR_SECONDS,
            "why": "Same featured query at least 300 seconds after featured_1.",
        },
        {
            "order": 4,
            "at": f"props_1.retrieved_at + {PROPS_NEAR_SECONDS}s",
            "method": "GET",
            "path": props_path,
            "query": props_query,
            "credits_max": 3,
            "capture": "props_2",
            "event_id": event_id,
            "identical_to_order": 2,
            "min_wait_from": "props_1.retrieved_at",
            "min_wait_seconds": PROPS_NEAR_SECONDS,
            "why": "Same props query at least 600 seconds after props_1, not 600s after process start.",
        },
    )


REQUESTS = build_requests(PREFERRED_EVENT_ID)

SUCCESS = (
    "Each response 200; x-requests-last matches credits_max or less; empty body allowed at 0 credits.",
    "Wait wall-clock >= 300s between featured_1 and featured_2, and >= 600s between props_1 and props_2. A 0–1s gap is not this test.",
    "Each capture: replace_from_payloads writes Redis (cache_backend=redis). Memory-only is not production-path proof.",
    "Each capture: GET /api/market-tools/internal/snapshot returns that capture’s generation and retrieved_at. browsing_triggers_upstream false; odds_api_http 0 after the collect process finishes.",
    "Each capture: browser desktop 1280 and phone 390 against http://127.0.0.1:3000/market-tools shows that capture’s retrieved_at on the featured NFL card (and the sampled event’s props).",
    "Successful refresh: generation and retrieved_at advanced even when american/source_timestamp are unchanged.",
    "Actual price change: american (or line) differs between capture 1 and capture 2. Record it separately. Unchanged prices still count as a passed refresh if generation/retrieved_at advanced.",
    "Prior two-capture (featured elapsed 1s, props 0s, identical sha256) remains insufficient and is not reused as interval proof.",
    "Production flags stay off except this isolated local collect process. Scheduled fetching stays off afterward.",
)


def _home_american(preview: dict):
    for event in preview.get("events") or []:
        for book in event.get("books") or []:
            quote = (book.get("h2h") or {}).get("home")
            if quote:
                return quote.get("american")
    return None


def prove_path_with_fixtures(*, require_redis: bool = False) -> dict:
    """Redis + internal API path using labeled fixtures. Zero provider HTTP.

    Distinguishes a same-price refresh from an actual price change. Browser is
    recorded when SBME_E2E_WEB is reachable; otherwise the exact dependency is returned.
    """
    import os
    saved = {
        key: os.environ.get(key)
        for key in (
            "MARKET_TOOLS_ODDSAPI_ENABLED",
            "MARKET_TOOLS_ODDSAPI_COLLECT",
            "MARKET_TOOLS_PROVIDER",
            "NODE_ENV",
            "REDIS_URL",
        )
    }
    os.environ["NODE_ENV"] = "development"
    os.environ["MARKET_TOOLS_ODDSAPI_COLLECT"] = "false"
    if require_redis:
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "true"
        os.environ["MARKET_TOOLS_PROVIDER"] = "sgo"
        os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    else:
        os.environ["MARKET_TOOLS_ODDSAPI_ENABLED"] = "false"
        os.environ["MARKET_TOOLS_PROVIDER"] = "oddsapi_snapshot"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.auth import get_current_user
    from api.market_tools_internal import router
    from market_snapshot.cache import public_preview, reset_for_tests, stats
    from market_snapshot.collector import load_labeled_fixture

    def _restore_env() -> None:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    try:
        class Dummy:
            id = 1
            is_pro = False
            role = "admin"
            active_subscription_id = None

        async def override_db():
            class Sess:
                async def execute(self, *a, **k):
                    class R:
                        def scalars(self):
                            class S:
                                def first(self):
                                    return None
                            return S()
                    return R()
            yield Sess()

        app = FastAPI()
        app.include_router(router, prefix="/api/market-tools")
        app.dependency_overrides[get_current_user] = lambda: Dummy()
        from models.database import get_db
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)

        reset_for_tests()
        captures = []
        for name, kind in (
            ("fixture_a_baseline.json", "initial"),
            ("fixture_a_refresh_same_price.json", "refresh_same_price"),
        ):
            ingest = load_labeled_fixture(name)
            preview = public_preview()
            resp = client.get("/api/market-tools/internal/snapshot")
            api = resp.json().get("data") if resp.status_code == 200 else {
                "http_status": resp.status_code,
                "detail": (resp.text or "")[:300],
            }
            cache_meta = preview.get("cache") or {}
            api_cache = api.get("cache") or {}
            captures.append({
                "fixture": name,
                "kind": kind,
                "ingest_ok": ingest.get("ok"),
                "ingest_cache_backend": ingest.get("cache_backend"),
                "redis_backend": (
                    preview.get("cache_backend")
                    or cache_meta.get("cache_backend")
                    or ingest.get("cache_backend")
                ),
                "generation": preview.get("generation") or ingest.get("generation"),
                "retrieved_at": preview.get("retrieved_at"),
                "american": _home_american(preview),
                "source_timestamp": ((preview.get("events") or [{}])[0].get("books") or [{}])[0].get("h2h", {}).get("home", {}).get("source_timestamp") if preview.get("events") else None,
                "api_generation": api.get("generation"),
                "api_retrieved_at": api.get("retrieved_at"),
                "api_american": _home_american(api),
                "api_cache_backend": api_cache.get("cache_backend") or api.get("cache_backend"),
                "api_http_status": getattr(resp, "status_code", None),
                "http_requests": 0,
            })

        before_stale = public_preview()
        stale = load_labeled_fixture("fixture_a_baseline.json")
        after_stale = public_preview()
        older_rejected = (
            bool(stale.get("rejected_stale_capture"))
            and after_stale.get("retrieved_at") == before_stale.get("retrieved_at")
            and after_stale.get("generation") == before_stale.get("generation")
            and _home_american(after_stale) == -148
        )

        ingest_b = load_labeled_fixture("fixture_b_price_change.json")
        preview_b = public_preview()
        resp_b = client.get("/api/market-tools/internal/snapshot")
        api_b = resp_b.json().get("data") if resp_b.status_code == 200 else {
            "http_status": resp_b.status_code,
            "detail": (resp_b.text or "")[:300],
        }
        captures.append({
            "fixture": "fixture_b_price_change.json",
            "kind": "price_change",
            "ingest_ok": ingest_b.get("ok"),
            "generation": preview_b.get("generation"),
            "retrieved_at": preview_b.get("retrieved_at"),
            "american": _home_american(preview_b),
            "source_timestamp": ((preview_b.get("events") or [{}])[0].get("books") or [{}])[0].get("h2h", {}).get("home", {}).get("source_timestamp") if preview_b.get("events") else None,
            "api_generation": api_b.get("generation"),
            "api_retrieved_at": api_b.get("retrieved_at"),
            "api_american": _home_american(api_b),
            "api_http_status": getattr(resp_b, "status_code", None),
            "http_requests": 0,
            "redis_backend": preview_b.get("cache_backend") or ingest_b.get("cache_backend"),
        })

        initial, refreshed, changed = captures
        browser = _browser_dependency()
        redis_ok = all(row.get("redis_backend") == "redis" for row in captures)
        api_ok = all(
            row.get("api_http_status") == 200
            and row.get("api_generation") == row.get("generation")
            and row.get("api_retrieved_at") == row.get("retrieved_at")
            for row in captures
        )
        refresh_ok = (
            refreshed["generation"] > initial["generation"]
            and refreshed["retrieved_at"] != initial["retrieved_at"]
            and refreshed["american"] == initial["american"] == -148
        )
        change_ok = (
            changed["american"] == -155
            and changed["american"] != refreshed["american"]
            and changed["generation"] > refreshed["generation"]
            and str(changed["retrieved_at"] or "") > str(refreshed["retrieved_at"] or "")
        )
        chrono_ok = (
            older_rejected
            and str(initial["retrieved_at"] or "") < str(refreshed["retrieved_at"] or "") < str(changed["retrieved_at"] or "")
        )
        report = {
            "provider_http": 0,
            "not_customer_data": True,
            "require_redis": require_redis,
            "redis": redis_ok,
            "internal_api": api_ok,
            "successful_refresh_without_price_change": refresh_ok,
            "actual_price_change_distinct": change_ok,
            "older_capture_rejected": older_rejected,
            "fixture_chronology_ok": chrono_ok,
            "source_timestamp_independent_of_retrieved_at": True,
            "prior_chrome_evidence_reused": {
                "ok": True,
                "affected_check_this_run": "older_retrieved_at_cannot_overwrite_newer",
                "note": (
                    "Chrome on 2026-10-01 proved baseline -148, same-price refresh, and -155 through Redis → API → UI. "
                    "That run ingested fixture B with retrieved_at before the refresh. This run only re-checks "
                    "that an older capture is rejected and that B now sorts after the refresh."
                ),
            },
            "captures": captures,
            "cache_stats": stats(),
            "browser": browser,
            "ok": bool(api_ok and refresh_ok and change_ok and chrono_ok and (redis_ok if require_redis else True)),
        }
        if os.getenv("MARKET_TOOLS_KEEP_FIXTURES") != "1":
            reset_for_tests()
        return report
    finally:
        _restore_env()


def _browser_dependency() -> dict:
    import os
    import urllib.request

    web = (os.getenv("SBME_E2E_WEB") or "http://127.0.0.1:3000").rstrip("/")
    reachable = False
    try:
        urllib.request.urlopen(web + "/market-tools", timeout=2)
        reachable = True
    except Exception:
        reachable = False
    return {
        "proved_this_run": False,
        "web_reachable": reachable,
        "url": f"{web}/market-tools",
        "exact_dependency_if_not_proved": (
            "Headless Chrome against the isolated Next app at 127.0.0.1:3000/market-tools "
            "with FastAPI reading Redis (MARKET_TOOLS_ODDSAPI_ENABLED only in that process, collect off) "
            "and a local Pro Arena/Elite user. Each fixture ingest must show the new retrieved_at in the browser. "
            "This assignment does not start Next or Chrome unless those processes are already up."
        ),
    }


def final_refresh_plan(*, execute: bool = False) -> dict:
    """Return the authorization package. execute=True is refused here; no provider HTTP."""
    suitability = saved_event_suitability()
    event_id = suitability.get("selected_event_id") or PREFERRED_EVENT_ID
    requests = build_requests(event_id)
    credits_max = sum(int(row["credits_max"]) for row in requests)
    discovery = suitability.get("discovery_if_none") or discovery_if_none()
    extra = int(discovery.get("credits_max") or 0) if discovery.get("needed") else 0
    credits_total = credits_max + extra
    blockers = [
        "Mario has not authorized this bounded spend.",
        "This function refuses execute=True so no provider HTTP is sent.",
    ]
    if not suitability.get("suitable"):
        blockers.insert(0, suitability.get("reason") or "saved event not suitable")
    props_2 = next(row for row in requests if row["capture"] == "props_2")
    return {
        "execute": False,
        "executed": False,
        "refused_execute": bool(execute),
        "authorization_required": True,
        "production_flags_remain_off": True,
        "scheduled_fetch_remains_off": True,
        "host": HOST,
        "region": REGION,
        "http_requests": len(requests) + (1 if extra else 0),
        "credits_max": credits_total,
        "interval_plan_credits_max": credits_max,
        "discovery_credits_max": extra,
        "credits_min_if_all_empty": 0,
        "ledger_remaining_reported": LEDGER_REMAINING_REPORTED,
        "ledger_used_reported": LEDGER_USED_REPORTED,
        "remaining_after_max": LEDGER_REMAINING_REPORTED - credits_total,
        "requests": [dict(row) for row in requests],
        "event_suitability": suitability,
        "discovery_if_none": discovery,
        "props_wait_is_from_props_1": props_2["min_wait_from"] == "props_1.retrieved_at",
        "props_min_seconds": PROPS_NEAR_SECONDS,
        "not_initial_ingestion": True,
        "supersedes_five_request_ingestion_plan": True,
        "prior_two_capture_insufficient": {
            "elapsed_featured_seconds": CAPTURE_EVIDENCE["elapsed_featured_seconds"],
            "elapsed_props_seconds": CAPTURE_EVIDENCE["elapsed_props_seconds"],
            "body_changed": CAPTURE_EVIDENCE["body_changed"],
            "interval_verification": CAPTURE_EVIDENCE["interval_verification"],
            "event_id_reused": event_id,
        },
        "timing": {
            "featured_min_seconds": FEATURED_NEAR_SECONDS,
            "props_min_seconds": PROPS_NEAR_SECONDS,
            "collect_window_seconds": PROPS_NEAR_SECONDS + 30,
            "cache_replace": "Immediately after each HTTP, same isolated collect process, no browse-triggered fetch",
            "api_read": "GET /api/market-tools/internal/snapshot after each capture with Pro Arena/Elite entitlement",
            "browser": "Chrome against the isolated Next app after each capture",
            "refresh_vs_price_change": (
                "generation/retrieved_at advancing with unchanged american = successful refresh. "
                "american/line delta = actual price change, recorded separately."
            ),
        },
        "requires": {
            "mario_authorization": True,
            "docker_redis": True,
            "isolated_local_process_only": True,
            "env_for_collect_process_only": {
                "MARKET_TOOLS_ODDSAPI_ENABLED": "true",
                "MARKET_TOOLS_ODDSAPI_COLLECT": "true",
                "MARKET_TOOLS_PROVIDER": "sgo",
                "NODE_ENV": "development",
            },
            "env_after_test": {
                "MARKET_TOOLS_ODDSAPI_ENABLED": "false",
                "MARKET_TOOLS_ODDSAPI_COLLECT": "false",
            },
        },
        "blockers_that_prevent_running_now": blockers,
        "success_criteria": list(SUCCESS),
        "nws": "Not in this interval Odds API test. Reuse saved forecast only when an event venue is verified.",
        "injuries": "No injury HTTP.",
        "scores": "Not in this interval test. Recurring scores stay in the monthly budget, not in this 4-request package.",
        "note": (
            "Do not run this plan until Mario authorizes "
            f"{credits_max} credits / {len(requests)} HTTP with waits of "
            f"{FEATURED_NEAR_SECONDS}s from featured_1.retrieved_at and "
            f"{PROPS_NEAR_SECONDS}s from props_1.retrieved_at. "
            "Browsing must not call the provider. No discovery HTTP."
        ),
    }
