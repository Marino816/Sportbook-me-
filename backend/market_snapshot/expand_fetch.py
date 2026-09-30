"""Bounded expansion sample for newly requested leagues. Max 20 HTTP and 50 additional credits."""

from __future__ import annotations

import json
import os
import stat

from market_snapshot.access import load_key
from market_snapshot.bounded_fetch import (
    PRIVATE,
    OddsImportError,
    REGION,
    _load_ledger,
    _utc,
    get_json,
)
from market_snapshot.leagues import LEAGUES

EXPAND_MAX_HTTP = 20
EXPAND_MAX_CREDITS = 50
EXPAND_INDEX = PRIVATE / "expansion_index.json"


def _catalog_map(sports: list) -> dict:
    return {row.get("key"): row for row in sports if isinstance(row, dict)}


def run_expansion_fetch(*, force: bool = False) -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    payloads_path = PRIVATE / "latest_payloads.json"
    if not payloads_path.is_file():
        raise OddsImportError("saved snapshot missing; reuse NFL/NCAAF/MLB before expanding")
    payloads = json.loads(payloads_path.read_text())
    if EXPAND_INDEX.is_file() and not force:
        return json.loads(EXPAND_INDEX.read_text())

    sports = payloads.get("sports") or []
    catalog = _catalog_map(sports)
    odds_map = dict(payloads.get("odds") or {})
    key = load_key()
    if not key:
        raise OddsImportError("ODDS_API_KEY is not configured")

    ledger = _load_ledger()
    prior_http = int(ledger.get("http_count") or 0)
    prior_credits = int(ledger.get("credits_charged") or 0)
    budget = [EXPAND_MAX_HTTP, EXPAND_MAX_CREDITS]
    calls: list[dict] = []
    skipped: list[dict] = []

    for league in LEAGUES:
        sport_key = league["key"]
        if league.get("reuse_saved"):
            skipped.append({"key": sport_key, "reason": "reused_saved_response", "title": league["title"]})
            continue
        listed = catalog.get(sport_key)
        if listed is None and not league.get("sample_if_missing_from_catalog", True):
            skipped.append({
                "key": sport_key,
                "reason": "documented_but_not_in_saved_in_season_catalog",
                "title": league["title"],
                "note": league.get("docs_note"),
            })
            continue
        if listed is None:
            skipped.append({
                "key": sport_key,
                "reason": "not_in_saved_catalog_not_sampled",
                "title": league["title"],
            })
            continue
        markets = ",".join(league["markets"])
        max_cost = len(league["markets"])
        rec = get_json(
            f"/v4/sports/{sport_key}/odds",
            {
                "regions": REGION,
                "markets": markets,
                "oddsFormat": "american",
            },
            max_credit_cost=max_cost,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        rec["sport_key"] = sport_key
        rec["sport_title"] = league["title"]
        rec["kind"] = league["kind"]
        calls.append({k: v for k, v in rec.items() if k != "payload"})
        payload = rec.get("payload")
        odds_map[sport_key] = payload if isinstance(payload, list) else []

    additional_http = int(ledger.get("http_count") or 0) - prior_http
    additional_credits = int(ledger.get("credits_charged") or 0) - prior_credits
    remaining = None
    if calls:
        remaining = (calls[-1].get("usage_headers") or {}).get("x-requests-remaining")
    index = {
        "development": True,
        "live_data": False,
        "assignment": "expanded-sports",
        "additional_http_requests": additional_http,
        "additional_credits": additional_credits,
        "prior_http": prior_http,
        "prior_credits": prior_credits,
        "max_additional_http": EXPAND_MAX_HTTP,
        "max_additional_credits": EXPAND_MAX_CREDITS,
        "remaining_credits_header": remaining,
        "region": REGION,
        "calls": calls,
        "skipped": skipped,
        "imported_at": _utc(),
        "http_retries": 0,
        "historical_requests": 0,
        "continuous_refresh": False,
    }
    EXPAND_INDEX.write_text(json.dumps(index, indent=2) + "\n")
    os.chmod(EXPAND_INDEX, stat.S_IRUSR | stat.S_IWUSR)

    payloads["odds"] = odds_map
    payloads.setdefault("index", {})
    payloads["index"]["expansion"] = {k: v for k, v in index.items() if k != "calls"}
    payloads["index"]["expansion_calls"] = calls
    payloads_path.write_text(json.dumps(payloads) + "\n")
    os.chmod(payloads_path, stat.S_IRUSR | stat.S_IWUSR)
    return index


def main() -> int:
    report = run_expansion_fetch()
    print(json.dumps({
        "additional_http_requests": report["additional_http_requests"],
        "additional_credits": report["additional_credits"],
        "remaining_credits_header": report["remaining_credits_header"],
        "skipped": report["skipped"],
        "calls": [
            {
                "path": c.get("path"),
                "sport_key": c.get("sport_key"),
                "status": c.get("status"),
                "max_credit_cost": c.get("max_credit_cost"),
                "actual_credit_cost": c.get("actual_credit_cost"),
                "record_count": c.get("record_count"),
                "usage_headers": c.get("usage_headers"),
            }
            for c in report["calls"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
