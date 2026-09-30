"""One-shot bounded scores and weather collection. Scheduled fetching stays off.

Cost is calculated before any data-provider HTTP. No retries, polling, or historical Odds API.
Injury HTTP is not sent: commercial permission was not established.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from market_snapshot.access import load_key
from market_snapshot.bounded_fetch import OddsImportError, _load_ledger, get_json
from market_snapshot.context_sources import ASSIGNMENT_BUDGET, INJURIES, SCHEDULED_FETCH_ENABLED
from market_snapshot.venues import venue_for_home

PRIVATE = Path.home() / ".sbme-dev" / "odds-api"
CONTEXT_DIR = PRIVATE / "context"
CONTEXT_LATEST = CONTEXT_DIR / "latest.json"
NWS_HOST = "https://api.weather.gov"
NWS_UA = "SportsBookMe-MarketTools-Local/1.0 (local-dev; context-bounded-sample)"
MAX_HTTP = 12
MAX_ODDS_CREDITS = 10


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cost_plan() -> dict:
    return {
        **ASSIGNMENT_BUDGET,
        "scheduled_fetch_enabled": SCHEDULED_FETCH_ENABLED,
        "injuries": INJURIES,
        "calculated_before_http": True,
    }


def _nws_get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": NWS_UA, "Accept": "application/geo+json"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8") or "{}")


def _save_context(payload: dict) -> None:
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_LATEST.write_text(json.dumps(payload, indent=2) + "\n")
    os.chmod(CONTEXT_LATEST, stat.S_IRUSR | stat.S_IWUSR)


def _pick_outdoor_home(score_rows: list[dict]) -> dict | None:
    preferred = ("Atlanta Braves", "Cleveland Browns", "New York Yankees", "San Diego Padres")
    by_name = {}
    for row in score_rows:
        home = row.get("home_team")
        venue = venue_for_home(home)
        if venue and venue.get("roof") == "outdoor":
            by_name[home] = {**venue, "event": row}
    for name in preferred:
        if name in by_name:
            return by_name[name]
    return next(iter(by_name.values()), None)


def collect_bounded(*, execute: bool = False) -> dict:
    """If execute is false, return the cost plan only. No HTTP."""
    plan = cost_plan()
    report = {
        "plan": plan,
        "executed": False,
        "http_used": 0,
        "odds_credits_used": 0,
        "remaining_credits_header": None,
        "stopped": None,
        "requests": [],
    }
    if not execute:
        return report
    if SCHEDULED_FETCH_ENABLED:
        report["stopped"] = "scheduled_fetch_must_stay_off"
        return report

    key = load_key()
    if not key:
        raise OddsImportError("ODDS_API_KEY is not configured")

    ledger = _load_ledger()
    budget = [MAX_HTTP, MAX_ODDS_CREDITS]
    http_used = 0
    credits_used = 0
    scores: list[dict] = []
    requests = []
    remaining = None

    for sport_key in ("americanfootball_nfl", "baseball_mlb"):
        rec = get_json(
            f"/v4/sports/{sport_key}/scores",
            {"daysFrom": "1"},
            max_credit_cost=2,
            budget=budget,
            ledger=ledger,
            key=key,
        )
        http_used += 1
        last = int(rec.get("actual_credit_cost") or 0)
        credits_used += last
        remaining = (rec.get("usage_headers") or {}).get("x-requests-remaining")
        payload = rec.get("payload") if isinstance(rec.get("payload"), list) else []
        for row in payload:
            if isinstance(row, dict):
                scores.append(row)
        requests.append({
            "source": "The Odds API",
            "path": rec.get("path"),
            "status": rec.get("status"),
            "actual_credit_cost": last,
            "record_count": rec.get("record_count"),
            "remaining": remaining,
        })

    weather_by_home: dict = {}
    venue = _pick_outdoor_home(scores)
    if venue is None:
        requests.append({
            "source": "National Weather Service",
            "path": None,
            "status": "skipped",
            "reason": "No outdoor catalog venue matched a scores row.",
        })
    else:
        points_url = f"{NWS_HOST}/points/{venue['lat']:.4f},{venue['lon']:.4f}"
        try:
            points = _nws_get(points_url)
            http_used += 1
            budget[0] -= 1
            forecast_url = ((points.get("properties") or {}).get("forecastHourly"))
            requests.append({
                "source": "National Weather Service",
                "path": "/points/{lat},{lon}",
                "status": 200,
                "home_team": venue.get("home_team"),
                "venue": venue.get("name"),
            })
            if not forecast_url:
                report["stopped"] = "nws_points_missing_hourly_url"
            else:
                hourly = _nws_get(forecast_url)
                http_used += 1
                budget[0] -= 1
                periods = ((hourly.get("properties") or {}).get("periods")) or []
                updated = (hourly.get("properties") or {}).get("updateTime")
                weather_by_home[venue["home_team"]] = {
                    "retrieved_at": _utc(),
                    "source_updated_at": updated,
                    "grid": forecast_url,
                    "periods": [
                        {
                            "startTime": p.get("startTime"),
                            "endTime": p.get("endTime"),
                            "temperature": p.get("temperature"),
                            "temperatureUnit": p.get("temperatureUnit"),
                            "windSpeed": p.get("windSpeed"),
                            "windDirection": p.get("windDirection"),
                            "shortForecast": p.get("shortForecast"),
                            "probabilityOfPrecipitation": p.get("probabilityOfPrecipitation"),
                        }
                        for p in periods
                        if isinstance(p, dict)
                    ],
                }
                requests.append({
                    "source": "National Weather Service",
                    "path": "forecastHourly",
                    "status": 200,
                    "period_count": len(periods),
                    "kind": "forecast",
                })
        except HTTPError as exc:
            http_used += 1
            requests.append({
                "source": "National Weather Service",
                "path": "nws",
                "status": exc.code,
                "stopped": True,
            })
            report["stopped"] = f"nws_http_{exc.code}"
        except URLError as exc:
            requests.append({
                "source": "National Weather Service",
                "path": "nws",
                "status": "network_error",
                "reason": str(exc.reason),
            })
            report["stopped"] = "nws_network"

    retrieved = _utc()
    payload = {
        "label": "COLLECTED_CONTEXT",
        "retrieved_at": retrieved,
        "scores": scores,
        "weather_by_home": weather_by_home,
        "injuries": [],
        "injuries_blocked": INJURIES,
        "scheduled_fetch_enabled": False,
        "http_used": http_used,
        "odds_credits_used": credits_used,
        "remaining_credits_header": remaining,
        "requests": requests,
    }
    _save_context(payload)
    report.update({
        "executed": True,
        "http_used": http_used,
        "odds_credits_used": credits_used,
        "remaining_credits_header": remaining,
        "requests": requests,
        "score_rows": len(scores),
        "weather_homes": list(weather_by_home),
        "saved": str(CONTEXT_LATEST),
        "injuries_http": 0,
    })
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bounded Market Tools context collect")
    parser.add_argument("--execute", action="store_true", help="Send the planned data-provider HTTP")
    args = parser.parse_args()
    result = collect_bounded(execute=args.execute)
    print(json.dumps({
        "plan_http": result["plan"]["planned_http_total"],
        "plan_credits": result["plan"]["planned_odds_credits_max"],
        **{k: v for k, v in result.items() if k != "plan"},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
