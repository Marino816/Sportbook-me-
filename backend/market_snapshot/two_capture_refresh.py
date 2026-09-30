"""Two-capture refresh test. Continuous fetching stays disabled.

Original remaining cap: 6 HTTP requests and 20 credits total.
Does not overwrite latest_payloads.json used by the local snapshot UI.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from market_snapshot.access import load_key
from market_snapshot.bounded_fetch import OddsImportError, PRIVATE, REGION, FEATURED, get_json, _load_ledger
from market_snapshot.scheduler import CONTINUOUS_FETCH_ENABLED

MAX_HTTP = 6
MAX_CREDITS = 20
SPORT_KEY = "americanfootball_nfl"
PROP_MARKETS = "player_pass_tds,player_pass_yds,player_rush_yds"
CAPTURES_PATH = PRIVATE / "refresh_captures.json"


def _event_id_from_saved() -> str | None:
    path = PRIVATE / "latest_payloads.json"
    if not path.is_file():
        return None
    payloads = json.loads(path.read_text())
    events = (payloads.get("odds") or {}).get(SPORT_KEY) or []
    if not events:
        return None
    return str(events[0].get("id") or "") or None


def _public_rec(rec: dict) -> dict:
    return {
        "path": rec.get("path"),
        "status": rec.get("status"),
        "max_credit_cost": rec.get("max_credit_cost"),
        "actual_credit_cost": rec.get("actual_credit_cost"),
        "sha256": rec.get("sha256"),
        "record_count": rec.get("record_count"),
        "retrieved_at": rec.get("retrieved_at"),
        "usage_headers": rec.get("usage_headers"),
        "url_redacted": rec.get("url_redacted"),
    }


def run_two_capture() -> dict:
    if CONTINUOUS_FETCH_ENABLED:
        raise OddsImportError("refusing to run while continuous fetching is enabled")
    key = load_key()
    if not key:
        raise OddsImportError("ODDS_API_KEY is not configured")
    event_id = _event_id_from_saved()
    if not event_id:
        raise OddsImportError("no saved NFL event id; request not sent")

    featured_cost = 3  # h2h,spreads,totals × region us
    props_cost = 3  # three requested markets × region us (empty body would be 0)
    per_capture = featured_cost + props_cost
    if per_capture * 2 > MAX_CREDITS:
        raise OddsImportError("two captures exceed remaining credit cap; request not sent")

    ledger = _load_ledger()
    budget = [MAX_HTTP, MAX_CREDITS]
    captures = []
    for n in (1, 2):
        featured = get_json(
            f"/v4/sports/{SPORT_KEY}/odds",
            {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"},
            max_credit_cost=featured_cost,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        props = get_json(
            f"/v4/sports/{SPORT_KEY}/events/{event_id}/odds",
            {"regions": REGION, "markets": PROP_MARKETS, "oddsFormat": "american"},
            max_credit_cost=props_cost,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        captures.append({
            "capture": n,
            "featured": _public_rec(featured),
            "props": _public_rec(props),
        })

    report = {
        "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        "cap": {"http": MAX_HTTP, "credits": MAX_CREDITS},
        "http_used": 4,
        "credits_used": sum(
            int(c["featured"].get("actual_credit_cost") or 0) + int(c["props"].get("actual_credit_cost") or 0)
            for c in captures
        ),
        "remaining_headers_last": (captures[-1]["props"].get("usage_headers") or {}),
        "featured_hash_changed": captures[0]["featured"]["sha256"] != captures[1]["featured"]["sha256"],
        "props_hash_changed": captures[0]["props"]["sha256"] != captures[1]["props"]["sha256"],
        "latest_payloads_untouched": True,
        "captures": captures,
        "completed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    CAPTURES_PATH.write_text(json.dumps(report, indent=2) + "\n")
    os.chmod(CAPTURES_PATH, stat.S_IRUSR | stat.S_IWUSR)
    return report


def main() -> int:
    try:
        report = run_two_capture()
    except OddsImportError as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "status": exc.status,
            "continuous_fetch_enabled": CONTINUOUS_FETCH_ENABLED,
        }, indent=2))
        return 2
    print(json.dumps({
        "ok": True,
        "http_used": report["http_used"],
        "credits_used": report["credits_used"],
        "featured_hash_changed": report["featured_hash_changed"],
        "props_hash_changed": report["props_hash_changed"],
        "remaining": report["remaining_headers_last"],
        "continuous_fetch_enabled": report["continuous_fetch_enabled"],
        "latest_payloads_untouched": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
