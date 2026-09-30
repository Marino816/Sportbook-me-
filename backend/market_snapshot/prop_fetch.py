"""Bounded player-prop samples. Max 15 additional HTTP and 50 additional credits."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone, date

from market_snapshot.access import load_key
from market_snapshot.bounded_fetch import PRIVATE, OddsImportError, REGION, _load_ledger, _utc, get_json

PROP_MAX_HTTP = 15
PROP_MAX_CREDITS = 50
PROP_INDEX = PRIVATE / "props_index.json"

# Documented production-aligned featured props. Event odds cost = unique markets returned × regions.
# Max cost before send = number of markets specified.
SAMPLES = (
    {
        "sport_key": "americanfootball_nfl",
        "markets": ("player_pass_yds", "player_rush_yds", "player_receptions"),
        "reuse_event": True,
        "note": "Additional NFL markets on the saved nearest event. player_pass_tds already saved.",
    },
    {
        "sport_key": "basketball_nba",
        "markets": ("player_points", "player_rebounds", "player_assists"),
    },
    {
        "sport_key": "icehockey_nhl",
        "markets": ("player_points", "player_goals", "player_assists"),
        "possible_preseason_before": "2026-10-07",
    },
    {
        "sport_key": "baseball_mlb",
        "markets": ("batter_hits", "batter_home_runs", "pitcher_strikeouts"),
    },
    {
        "sport_key": "basketball_wnba",
        "markets": ("player_points", "player_rebounds", "player_assists"),
    },
    {
        "sport_key": "americanfootball_ncaaf",
        "markets": ("player_pass_yds", "player_rush_yds"),
        "docs": "NCAAF player props are documented with NFL/CFL keys. Do not assume NBA-style markets.",
    },
    {
        "sport_key": "soccer_epl",
        "markets": ("player_shots_on_target", "player_assists"),
        "docs": "Soccer props documented for EPL, Ligue 1, Bundesliga, Serie A, La Liga, and MLS only.",
    },
)


def _nearest_event(events: list) -> dict | None:
    now = datetime.now(timezone.utc)
    scored = []
    for event in events or []:
        raw = event.get("commence_time")
        if not raw or not event.get("id"):
            continue
        try:
            start = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        scored.append((abs((start - now).total_seconds()), start, event))
    if not scored:
        return None
    scored.sort(key=lambda row: row[0])
    return scored[0][2]


def _season_label(sport_key: str, event: dict, spec: dict) -> str:
    cutoff = spec.get("possible_preseason_before")
    raw = event.get("commence_time") or ""
    if cutoff and raw:
        try:
            start = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            if start < date.fromisoformat(cutoff):
                return "possible_preseason_not_confirmed_regular_season"
        except ValueError:
            pass
    return "as_listed_on_sport_key"


def _write_payloads(samples: list, payloads: dict, payloads_path, index: dict | None = None) -> None:
    payloads["player_props_samples"] = samples
    if index is not None:
        payloads.setdefault("index", {})
        payloads["index"]["props"] = {k: v for k, v in index.items() if k != "calls"}
        PROP_INDEX.write_text(json.dumps(index, indent=2) + "\n")
        os.chmod(PROP_INDEX, stat.S_IRUSR | stat.S_IWUSR)
    payloads_path.write_text(json.dumps(payloads) + "\n")
    os.chmod(payloads_path, stat.S_IRUSR | stat.S_IWUSR)


def run_prop_fetch(*, force: bool = False) -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    payloads_path = PRIVATE / "latest_payloads.json"
    if not payloads_path.is_file():
        raise OddsImportError("saved snapshot missing")
    if PROP_INDEX.is_file() and not force:
        return json.loads(PROP_INDEX.read_text())
    payloads = json.loads(payloads_path.read_text())
    odds_map = payloads.get("odds") or {}
    existing = payloads.get("player_props")
    samples = []
    if isinstance(payloads.get("player_props_samples"), list) and payloads["player_props_samples"]:
        samples = payloads["player_props_samples"]
    elif isinstance(existing, dict) and existing.get("id"):
        samples.append({
            "sport_key": existing.get("sport_key") or "americanfootball_nfl",
            "event_id": existing.get("id"),
            "requested_markets": ["player_pass_tds"],
            "returned_markets": sorted({m.get("key") for b in existing.get("bookmakers") or [] for m in b.get("markets") or [] if m.get("key")}),
            "reused": True,
            "payload": existing,
            "season_label": "as_listed_on_sport_key",
            "note": "Reused saved NFL player_pass_tds sample. Not a new HTTP request.",
        })
    already = {
        (s.get("sport_key"), tuple(s.get("requested_markets") or []))
        for s in samples
        if not s.get("reused")
    }
    key = load_key()
    if not key:
        raise OddsImportError("ODDS_API_KEY is not configured")
    ledger = _load_ledger()
    prior_http = int(ledger.get("http_count") or 0)
    prior_credits = int(ledger.get("credits_charged") or 0)
    budget = [PROP_MAX_HTTP, PROP_MAX_CREDITS]
    calls = []
    skipped = [
        {
            "sport_key": "basketball_ncaab",
            "reason": "documented_with_nba_wnba_prop_keys_but_no_saved_ncaab_events",
            "requested_markets": ["player_points", "player_rebounds", "player_assists"],
        }
    ]
    stop_reason = None

    def snapshot_index():
        additional_http = int(ledger.get("http_count") or 0) - prior_http
        additional_credits = int(ledger.get("credits_charged") or 0) - prior_credits
        remaining = None
        if calls:
            remaining = (calls[-1].get("usage_headers") or {}).get("x-requests-remaining")
        return {
            "assignment": "player-props",
            "additional_http_requests": additional_http,
            "additional_credits": additional_credits,
            "remaining_credits_header": remaining,
            "max_additional_http": PROP_MAX_HTTP,
            "max_additional_credits": PROP_MAX_CREDITS,
            "calls": calls,
            "skipped": skipped,
            "samples": [{k: v for k, v in s.items() if k != "payload"} for s in samples],
            "imported_at": _utc(),
            "http_retries": 0,
            "historical_requests": 0,
            "one_event_is_not_league_coverage": True,
            "stop_reason": stop_reason,
        }

    for spec in SAMPLES:
        sport_key = spec["sport_key"]
        markets = list(spec["markets"])
        if (sport_key, tuple(markets)) in already:
            continue
        events = odds_map.get(sport_key) or []
        event = _nearest_event(events)
        if not event:
            skipped.append({"sport_key": sport_key, "reason": "no_saved_event_id", "requested_markets": markets})
            continue
        max_cost = len(markets)
        if max_cost > budget[1] or budget[0] <= 0:
            skipped.append({"sport_key": sport_key, "reason": "assignment_budget_stop", "requested_markets": markets, "max_credit_cost": max_cost})
            stop_reason = "assignment_budget_stop"
            break
        try:
            rec = get_json(
                f"/v4/sports/{sport_key}/events/{event['id']}/odds",
                {"regions": REGION, "markets": ",".join(markets), "oddsFormat": "american"},
                max_credit_cost=max_cost,
                budget=budget,
                ledger=ledger,
                key=key,
            )
        except OddsImportError as exc:
            stop_reason = str(exc)
            skipped.append({
                "sport_key": sport_key,
                "reason": stop_reason,
                "requested_markets": markets,
                "max_credit_cost": max_cost,
            })
            index = snapshot_index()
            _write_payloads(samples, payloads, payloads_path, index)
            return index
        payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
        books = payload.get("bookmakers") or []
        returned = sorted({m.get("key") for b in books for m in (b.get("markets") or []) if m.get("key")})
        players = sorted({o.get("description") or o.get("name") for b in books for m in (b.get("markets") or []) for o in (m.get("outcomes") or []) if o.get("description") or o.get("name")})
        sample = {
            "sport_key": sport_key,
            "event_id": event.get("id"),
            "away_team": event.get("away_team"),
            "home_team": event.get("home_team"),
            "commence_time": event.get("commence_time"),
            "requested_markets": markets,
            "returned_markets": returned,
            "missing_markets": [m for m in markets if m not in returned],
            "bookmakers": sorted({b.get("title") for b in books if b.get("title")}),
            "player_count": len(players),
            "season_label": _season_label(sport_key, event, spec),
            "docs": spec.get("docs"),
            "note": spec.get("note"),
            "usage_headers": rec.get("usage_headers"),
            "actual_credit_cost": rec.get("actual_credit_cost"),
            "max_credit_cost": max_cost,
            "retrieved_at": rec.get("retrieved_at"),
            "reused": False,
            "payload": payload,
        }
        samples.append(sample)
        calls.append({k: v for k, v in rec.items() if k != "payload"})
        _write_payloads(samples, payloads, payloads_path)

    index = snapshot_index()
    _write_payloads(samples, payloads, payloads_path, index)
    return index


def main() -> int:
    report = run_prop_fetch()
    print(json.dumps({
        "additional_http_requests": report["additional_http_requests"],
        "additional_credits": report["additional_credits"],
        "remaining_credits_header": report["remaining_credits_header"],
        "skipped": report["skipped"],
        "samples": report["samples"],
        "calls": [
            {
                "path": c.get("path"),
                "status": c.get("status"),
                "max_credit_cost": c.get("max_credit_cost"),
                "actual_credit_cost": c.get("actual_credit_cost"),
                "usage_headers": c.get("usage_headers"),
            }
            for c in report["calls"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
