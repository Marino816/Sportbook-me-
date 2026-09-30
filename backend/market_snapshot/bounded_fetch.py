"""Bounded The Odds API import. Max 12 HTTP and 30 credits. No retries or historical calls."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from market_snapshot.access import load_key
from market_snapshot.source_record import SOURCE

HOST = "https://api.the-odds-api.com"
MAX_HTTP = 12
MAX_CREDITS = 30
STOP_STATUS = {401, 403, 429}
PRIVATE = Path.home() / ".sbme-dev" / "odds-api"
LEDGER = PRIVATE / "ledger.json"
USAGE_HEADERS = (
    "x-requests-remaining",
    "x-requests-used",
    "x-requests-last",
)

SPORTS = (
    ("americanfootball_nfl", "NFL"),
    ("americanfootball_ncaaf", "NCAAF"),
    ("baseball_mlb", "MLB"),
)
FEATURED = "h2h,spreads,totals"
REGION = "us"


class OddsImportError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, requests_used: int = 0, credits_used: int = 0):
        super().__init__(message)
        self.status = status
        self.requests_used = requests_used
        self.credits_used = credits_used


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    q = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        if k.lower() in {"apikey", "api_key"}:
            q.append((k, "REDACTED"))
        else:
            q.append((k, v))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_ledger() -> dict:
    if LEDGER.is_file():
        return json.loads(LEDGER.read_text())
    return {"requests": [], "http_count": 0, "credits_charged": 0}


def _save_ledger(ledger: dict) -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")
    os.chmod(LEDGER, stat.S_IRUSR | stat.S_IWUSR)


def _header_map(headers) -> dict[str, str]:
    out = {}
    for key in USAGE_HEADERS:
        val = headers.get(key)
        if val is not None:
            out[key] = str(val)
    return out


def get_json(
    path: str,
    params: dict[str, str],
    *,
    max_credit_cost: int,
    budget: list[int],
    ledger: dict,
    key: str,
) -> dict:
    """budget is [http_left, credits_left]."""
    if max_credit_cost < 0:
        raise OddsImportError("cost uncertain; request not sent", requests_used=MAX_HTTP - budget[0], credits_used=MAX_CREDITS - budget[1])
    if budget[0] <= 0:
        raise OddsImportError("HTTP budget exhausted", requests_used=MAX_HTTP, credits_used=MAX_CREDITS - budget[1])
    if max_credit_cost > budget[1]:
        raise OddsImportError(
            f"credit cost {max_credit_cost} exceeds remaining {budget[1]}",
            requests_used=MAX_HTTP - budget[0],
            credits_used=MAX_CREDITS - budget[1],
        )
    query = {**params, "apiKey": key}
    url = HOST + path + "?" + urlencode(query)
    req = Request(url, headers={"Accept": "application/json"})
    retrieved = _utc()
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = getattr(resp, "status", 200)
            usage = _header_map(resp.headers)
    except HTTPError as exc:
        usage = _header_map(exc.headers or {})
        budget[0] -= 1
        last = _int(usage.get("x-requests-last"), 0)
        budget[1] -= last
        ledger["http_count"] = MAX_HTTP - budget[0]
        ledger["credits_charged"] = MAX_CREDITS - budget[1]
        ledger["requests"].append({
            "path": path,
            "query": {k: v for k, v in params.items()},
            "url_redacted": redact_url(url),
            "status": exc.code,
            "usage_headers": usage,
            "retrieved_at": retrieved,
            "max_credit_cost": max_credit_cost,
        })
        _save_ledger(ledger)
        if exc.code in STOP_STATUS:
            raise OddsImportError(
                f"provider stopped status={exc.code}",
                status=exc.code,
                requests_used=MAX_HTTP - budget[0],
                credits_used=MAX_CREDITS - budget[1],
            ) from None
        raise OddsImportError(
            f"HTTP {exc.code}",
            status=exc.code,
            requests_used=MAX_HTTP - budget[0],
            credits_used=MAX_CREDITS - budget[1],
        ) from None
    except URLError as exc:
        raise OddsImportError(f"network error: {exc.reason}", requests_used=MAX_HTTP - budget[0], credits_used=MAX_CREDITS - budget[1]) from None

    budget[0] -= 1
    last = _int(usage.get("x-requests-last"), 0)
    budget[1] -= last
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8") or "null")
    rec = {
        "path": path,
        "query": {k: v for k, v in params.items()},
        "url_redacted": redact_url(url),
        "status": status,
        "usage_headers": usage,
        "retrieved_at": retrieved,
        "max_credit_cost": max_credit_cost,
        "actual_credit_cost": last,
        "sha256": digest,
        "record_count": len(payload) if isinstance(payload, list) else (1 if payload else 0),
    }
    ledger["http_count"] = MAX_HTTP - budget[0]
    ledger["credits_charged"] = MAX_CREDITS - budget[1]
    ledger["requests"].append({k: rec[k] for k in rec if k != "payload"})
    dest = PRIVATE / "responses"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{digest}.json").write_text(json.dumps(payload, indent=2) + "\n")
    (dest / f"{digest}.meta.json").write_text(json.dumps(rec, indent=2) + "\n")
    os.chmod(dest / f"{digest}.json", stat.S_IRUSR | stat.S_IWUSR)
    os.chmod(dest / f"{digest}.meta.json", stat.S_IRUSR | stat.S_IWUSR)
    _save_ledger(ledger)
    rec["payload"] = payload
    rec["body_path"] = str(dest / f"{digest}.json")
    return rec


def _int(raw, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def run_bounded_fetch(*, force: bool = False) -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    index_path = PRIVATE / "import_index.json"
    if index_path.is_file() and not force:
        return json.loads(index_path.read_text())
    key = load_key()
    if not key:
        raise OddsImportError("ODDS_API_KEY is not configured")
    ledger = _load_ledger()
    already_http = int(ledger.get("http_count") or 0)
    already_credits = int(ledger.get("credits_charged") or 0)
    if already_http >= MAX_HTTP or already_credits >= MAX_CREDITS:
        raise OddsImportError(
            "prior replacement-test usage already at the assignment cap",
            requests_used=already_http,
            credits_used=already_credits,
        )
    budget = [MAX_HTTP - already_http, MAX_CREDITS - already_credits]
    calls: list[dict] = []

    sports = get_json("/v4/sports/", {}, max_credit_cost=0, budget=budget, ledger=ledger, key=key)
    calls.append(sports)

    odds_calls = []
    for sport_key, title in SPORTS:
        rec = get_json(
            f"/v4/sports/{sport_key}/odds",
            {
                "regions": REGION,
                "markets": FEATURED,
                "oddsFormat": "american",
            },
            max_credit_cost=3,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        rec["sport_title"] = title
        rec["sport_key"] = sport_key
        odds_calls.append(rec)
        calls.append(rec)

    prop_call = None
    prop_note = "no in-season event available for a player-prop sample"
    nfl_events = odds_calls[0].get("payload") or []
    mlb_events = odds_calls[2].get("payload") or []
    candidate = None
    market = None
    sport_key = None
    if isinstance(nfl_events, list) and nfl_events:
        candidate = nfl_events[0]
        market = "player_pass_tds"
        sport_key = "americanfootball_nfl"
    elif isinstance(mlb_events, list) and mlb_events:
        candidate = mlb_events[0]
        market = "batter_hits"
        sport_key = "baseball_mlb"
    if candidate and market and sport_key:
        event_id = candidate.get("id")
        if not event_id:
            raise OddsImportError("event id missing; player-prop cost cannot be calculated")
        prop_call = get_json(
            f"/v4/sports/{sport_key}/events/{event_id}/odds",
            {
                "regions": REGION,
                "markets": market,
                "oddsFormat": "american",
            },
            max_credit_cost=1,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        prop_call["sport_key"] = sport_key
        prop_call["event_id"] = event_id
        prop_call["requested_market"] = market
        calls.append(prop_call)
        payload = prop_call.get("payload") or {}
        books = payload.get("bookmakers") if isinstance(payload, dict) else []
        prop_note = "player-prop sample returned" if books else "player-prop market returned no bookmakers (not treated as zero coverage beyond this event)"

    index = {
        "development": True,
        "live_data": False,
        "label": "Snapshot",
        "http_requests_used": MAX_HTTP - budget[0],
        "credits_used_from_headers": MAX_CREDITS - budget[1],
        "prior_http_before_this_run": already_http,
        "prior_credits_before_this_run": already_credits,
        "max_http": MAX_HTTP,
        "max_credits": MAX_CREDITS,
        "region": REGION,
        "featured_markets": FEATURED.split(","),
        "calls": [{k: v for k, v in c.items() if k != "payload"} for c in calls],
        "odds": [{k: v for k, v in c.items() if k != "payload"} for c in odds_calls],
        "player_props": None if not prop_call else {k: v for k, v in prop_call.items() if k != "payload"},
        "player_props_note": prop_note,
        "source": SOURCE,
        "imported_at": _utc(),
        "http_retries": 0,
        "historical_requests": 0,
    }
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    os.chmod(index_path, stat.S_IRUSR | stat.S_IWUSR)
    (PRIVATE / "latest_payloads.json").write_text(json.dumps({
        "sports": sports["payload"],
        "odds": {c["sport_key"]: c["payload"] for c in odds_calls},
        "player_props": None if not prop_call else prop_call["payload"],
        "index": {k: v for k, v in index.items() if k != "source"},
    }, indent=2) + "\n")
    os.chmod(PRIVATE / "latest_payloads.json", stat.S_IRUSR | stat.S_IWUSR)
    return index


def main() -> int:
    report = run_bounded_fetch()
    print(json.dumps({
        "http_requests_used": report["http_requests_used"],
        "credits_used_from_headers": report["credits_used_from_headers"],
        "player_props_note": report["player_props_note"],
        "calls": [
            {
                "path": c["path"],
                "status": c["status"],
                "max_credit_cost": c["max_credit_cost"],
                "actual_credit_cost": c.get("actual_credit_cost"),
                "usage_headers": c.get("usage_headers"),
                "record_count": c.get("record_count"),
            }
            for c in report["calls"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
