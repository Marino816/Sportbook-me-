"""Server-side scores, schedule, weather, and injury context. No customer-triggered HTTP."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from market_snapshot.compat import parse_internal_event_id
from market_snapshot.context_sources import INJURIES, SCHEDULED_FETCH_ENABLED, SCORES, WEATHER
from market_snapshot.flags import context_fixtures_enabled, is_production
from market_snapshot.venues import indoor_label, venue_for_home

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "context_labeled.json"
PRIVATE_CONTEXT = Path.home() / ".sbme-dev" / "odds-api" / "context" / "latest.json"
EASTERN = ZoneInfo("America/New_York")

STALE_AFTER = {
    "in_progress": 120,
    "final": 3600,
    "scheduled": 900,
    "postponed": 3600,
    "canceled": 86400,
    "delayed": 300,
    "unknown": 900,
}

STATUS_LABELS = {
    "scheduled": "Scheduled",
    "in_progress": "In progress",
    "final": "Final",
    "postponed": "Postponed",
    "canceled": "Canceled",
    "delayed": "Delayed",
    "unknown": "Status unavailable",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def schedule_block(commence_utc: str | None, *, tz: ZoneInfo = EASTERN) -> dict:
    """Preserve UTC. Offer a display conversion. UI still renders the customer's timezone."""
    dt = parse_iso(commence_utc)
    if dt is None:
        return {
            "commence_time_utc": commence_utc,
            "local_timezone": str(tz),
            "local_display": None,
            "timezone_abbreviation": None,
            "display_note": "Start time unavailable.",
        }
    local = dt.astimezone(tz)
    abbr = local.tzname()
    hour12 = local.strftime("%I").lstrip("0") or "12"
    display = f"{local.strftime('%a, %b')} {local.day}, {hour12}:{local.strftime('%M %p')} {abbr}"
    return {
        "commence_time_utc": iso_z(dt),
        "local_timezone": str(tz),
        "local_display": display,
        "timezone_abbreviation": abbr,
        "local_date": local.date().isoformat(),
        "utc_date": dt.date().isoformat(),
        "crosses_local_date": local.date() != dt.date(),
        "display_note": "Times are stored in UTC. The board shows your local timezone.",
    }


def _score_value(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return int(raw) if float(raw).is_integer() else raw
    text = str(raw).strip()
    if text in {"", "null", "None"}:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def status_from_oddsapi(row: dict) -> str:
    """Map documented Odds API fields only. Do not invent postponed/clock."""
    if row.get("status") in STATUS_LABELS:
        return row["status"]
    completed = row.get("completed")
    scores = row.get("scores")
    if completed is True:
        return "final"
    if completed is False and scores is None:
        return "scheduled"
    if completed is False and isinstance(scores, list):
        return "in_progress"
    return "unknown"


def extract_team_scores(row: dict) -> tuple:
    home_name = row.get("home_team")
    away_name = row.get("away_team")
    home_score = None
    away_score = None
    items = row.get("scores")
    if not isinstance(items, list):
        return None, None
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = _score_value(item.get("score"))
        if name == home_name:
            home_score = value
        elif name == away_name:
            away_score = value
    return home_score, away_score


def freshness_status(*, retrieved_at: str | None, source_updated_at: str | None, status: str, now: datetime | None = None) -> str:
    now = now or _utc_now()
    stamp = parse_iso(source_updated_at) or parse_iso(retrieved_at)
    if stamp is None:
        return "unknown"
    limit = STALE_AFTER.get(status, 900)
    return "stale" if (now - stamp) > timedelta(seconds=limit) else "fresh"


def match_score_row(event: dict, scores: list[dict]) -> dict | None:
    """Match by Odds API id + league, then teams and start time. Reject ambiguous."""
    if not scores:
        return None
    parsed = parse_internal_event_id(event.get("id"))
    source_id = parsed.get("source_event_id") if parsed.get("ok") else None
    sport_key = event.get("sport_key") or parsed.get("sport_key")
    id_hits = []
    if source_id:
        for row in scores:
            if row.get("id") != source_id:
                continue
            if sport_key and row.get("sport_key") and row.get("sport_key") != sport_key:
                continue
            id_hits.append(row)
        if len(id_hits) > 1:
            return None
        if len(id_hits) == 1:
            row = id_hits[0]
            if event.get("home_team") and row.get("home_team") and event["home_team"] != row["home_team"]:
                return None
            if event.get("away_team") and row.get("away_team") and event["away_team"] != row["away_team"]:
                return None
            return row
    fallback = []
    home = event.get("home_team")
    away = event.get("away_team")
    start = event.get("commence_time")
    for row in scores:
        if sport_key and row.get("sport_key") and row.get("sport_key") != sport_key:
            continue
        if row.get("home_team") != home or row.get("away_team") != away:
            continue
        if start and row.get("commence_time") and row.get("commence_time") != start:
            continue
        fallback.append(row)
    if len(fallback) == 1:
        return fallback[0]
    return None


def score_block(event: dict, row: dict | None, *, retrieved_at: str | None, now: datetime | None = None) -> dict:
    if row is None:
        return {
            "status": None,
            "status_display": "Score unavailable",
            "home_score": None,
            "away_score": None,
            "period": None,
            "inning": None,
            "clock": None,
            "completed": None,
            "source": SCORES["provider"],
            "source_updated_at": None,
            "retrieved_at": retrieved_at,
            "freshness": "unknown",
            "match": "none",
            "note": "No matched scores row. Missing scores stay null.",
        }
    status = status_from_oddsapi(row)
    home_score, away_score = extract_team_scores(row)
    source_updated = row.get("last_update") or row.get("source_updated_at")
    period = row.get("period")
    inning = row.get("inning")
    clock = row.get("clock")
    return {
        "status": status,
        "status_display": STATUS_LABELS.get(status, "Status unavailable"),
        "home_score": home_score,
        "away_score": away_score,
        "period": period if period not in {None, ""} else None,
        "inning": inning if inning not in {None, ""} else None,
        "clock": clock if clock not in {None, ""} else None,
        "completed": row.get("completed"),
        "source": row.get("source") or SCORES["provider"],
        "source_updated_at": source_updated,
        "retrieved_at": retrieved_at or row.get("retrieved_at"),
        "freshness": freshness_status(
            retrieved_at=retrieved_at or row.get("retrieved_at"),
            source_updated_at=source_updated,
            status=status,
            now=now,
        ),
        "match": "source_id",
        "note": (
            "Period, inning, and clock are shown only when the source supplies them. "
            "The Odds API scores schema does not include those fields."
        ),
    }


def _pop_from_period(period: dict) -> int | None:
    pop = period.get("probabilityOfPrecipitation") or {}
    if isinstance(pop, dict) and pop.get("value") is not None:
        try:
            return int(pop["value"])
        except (TypeError, ValueError):
            return None
    return None


def pick_hourly_period(periods: list, event_dt: datetime) -> dict:
    if not periods:
        return {"unavailable": True, "reason": "Forecast not yet available."}
    parsed = []
    for period in periods:
        start = parse_iso(period.get("startTime"))
        end = parse_iso(period.get("endTime")) or (start + timedelta(hours=1) if start else None)
        if start:
            parsed.append((start, end, period))
    if not parsed:
        return {"unavailable": True, "reason": "Forecast not yet available."}
    last_end = parsed[-1][1] or parsed[-1][0]
    if event_dt > last_end:
        return {"unavailable": True, "reason": "Forecast not yet available."}
    for start, end, period in parsed:
        if end and start <= event_dt < end:
            return {"unavailable": False, "period": period}
        if end is None and start == event_dt.replace(minute=0, second=0, microsecond=0):
            return {"unavailable": False, "period": period}
    nearest = min(parsed, key=lambda item: abs((item[0] - event_dt).total_seconds()))
    return {"unavailable": False, "period": nearest[2]}


def weather_block(event: dict, weather_by_home: dict | None, *, retrieved_at: str | None, now: datetime | None = None) -> dict:
    sport_key = event.get("sport_key")
    indoor = indoor_label(sport_key)
    venue = venue_for_home(event.get("home_team"))
    if indoor:
        return {
            "kind": "indoor",
            "label": indoor,
            "source": "SB ME venue catalog",
            "source_updated_at": None,
            "retrieved_at": retrieved_at,
            "freshness": "fresh",
            "note": "Indoor venue. Outdoor forecast is not shown.",
        }
    if venue and venue.get("roof") == "indoor":
        return {
            "kind": "indoor",
            "label": "Indoor",
            "venue_name": venue.get("name"),
            "source": venue.get("catalog_source"),
            "source_updated_at": None,
            "retrieved_at": retrieved_at,
            "freshness": "fresh",
            "note": "Verified indoor roof in the venue catalog. Outdoor forecast is not shown.",
        }
    if not venue:
        return {
            "kind": "unavailable",
            "label": "Weather unavailable",
            "reason": "No verified venue coordinates for this home team.",
            "source": WEATHER["provider"],
            "retrieved_at": retrieved_at,
            "freshness": "unknown",
        }
    roof_note = None
    if venue.get("roof") == "retractable":
        roof_note = "Retractable roof; open or closed was not supplied."
    payload = (weather_by_home or {}).get(event.get("home_team")) or (weather_by_home or {}).get(venue.get("name"))
    event_dt = parse_iso(event.get("commence_time"))
    if payload is None:
        return {
            "kind": "unavailable",
            "label": "Weather unavailable",
            "venue_name": venue.get("name"),
            "lat": venue.get("lat"),
            "lon": venue.get("lon"),
            "roof": venue.get("roof"),
            "roof_note": roof_note,
            "reason": "No forecast stored for this venue.",
            "source": WEATHER["provider"],
            "retrieved_at": retrieved_at,
            "freshness": "unknown",
        }
    if payload.get("horizon_unavailable"):
        return {
            "kind": "forecast",
            "label": "Forecast not yet available.",
            "venue_name": venue.get("name"),
            "roof": venue.get("roof"),
            "roof_note": roof_note,
            "source": WEATHER["provider"],
            "source_updated_at": payload.get("source_updated_at"),
            "retrieved_at": payload.get("retrieved_at") or retrieved_at,
            "freshness": "unknown",
        }
    periods = payload.get("periods") or []
    if event_dt is None:
        return {
            "kind": "forecast",
            "label": "Forecast not yet available.",
            "reason": "Event start time unavailable.",
            "source": WEATHER["provider"],
            "retrieved_at": retrieved_at,
        }
    picked = pick_hourly_period(periods, event_dt)
    if picked.get("unavailable"):
        return {
            "kind": "forecast",
            "label": "Forecast not yet available.",
            "venue_name": venue.get("name"),
            "roof": venue.get("roof"),
            "roof_note": roof_note,
            "source": WEATHER["provider"],
            "source_updated_at": payload.get("source_updated_at"),
            "retrieved_at": payload.get("retrieved_at") or retrieved_at,
            "freshness": freshness_status(
                retrieved_at=payload.get("retrieved_at") or retrieved_at,
                source_updated_at=payload.get("source_updated_at"),
                status="scheduled",
                now=now,
            ),
        }
    period = picked["period"]
    return {
        "kind": "forecast",
        "label": "Forecast",
        "not_observation": True,
        "venue_name": venue.get("name"),
        "city": venue.get("city"),
        "lat": venue.get("lat"),
        "lon": venue.get("lon"),
        "roof": venue.get("roof"),
        "roof_note": roof_note,
        "temperature": period.get("temperature"),
        "temperature_unit": period.get("temperatureUnit") or "F",
        "wind": " ".join(x for x in [period.get("windSpeed"), period.get("windDirection")] if x),
        "precipitation_probability": _pop_from_period(period),
        "forecast_time": period.get("startTime"),
        "short_forecast": period.get("shortForecast"),
        "source": WEATHER["provider"],
        "source_updated_at": payload.get("source_updated_at") or period.get("startTime"),
        "retrieved_at": payload.get("retrieved_at") or retrieved_at,
        "freshness": freshness_status(
            retrieved_at=payload.get("retrieved_at") or retrieved_at,
            source_updated_at=payload.get("source_updated_at"),
            status="scheduled",
            now=now,
        ),
        "note": "NWS forecast, not a station observation.",
    }


def injury_rows_for_event(event: dict, reports: list[dict]) -> list[dict]:
    out = []
    for row in reports or []:
        if row.get("event_id") and row.get("event_id") != event.get("id"):
            continue
        if row.get("sport_key") and row.get("sport_key") != event.get("sport_key"):
            continue
        team = row.get("team")
        if team and team not in {event.get("home_team"), event.get("away_team")}:
            continue
        certainty = row.get("certainty") or "report"
        out.append({
            "player": row.get("player"),
            "team": team,
            "reported_status": row.get("reported_status"),
            "source_wording": row.get("source_wording") or row.get("reported_status"),
            "certainty": certainty,
            "certainty_label": {
                "confirmed": "Confirmed availability",
                "report": "Report — not confirmed",
                "uncertain": "Uncertain",
            }.get(certainty, "Report — not confirmed"),
            "source": row.get("source"),
            "source_url": row.get("source_url"),
            "published_at": row.get("published_at") or row.get("source_updated_at"),
            "retrieved_at": row.get("retrieved_at"),
            "projection_adjustment": "not_applied",
            "note": row.get("note") or "No report does not mean healthy or available. Projections were not changed.",
        })
    return out


def injury_for_player(player: str | None, team: str | None, reports: list[dict]) -> dict | None:
    if not player:
        return None
    name = player.strip().lower()
    hits = []
    for row in reports or []:
        if (row.get("player") or "").strip().lower() != name:
            continue
        if team and row.get("team") and row.get("team") != team:
            continue
        hits.append(row)
    if len(hits) != 1:
        return None
    return injury_rows_for_event({"id": hits[0].get("event_id"), "sport_key": hits[0].get("sport_key"), "home_team": hits[0].get("team"), "away_team": hits[0].get("team")}, hits)[0]


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def load_collected_context() -> dict:
    return load_json(PRIVATE_CONTEXT)


def load_labeled_fixtures() -> dict:
    return load_json(FIXTURES_PATH)


def _empty_context(event: dict, retrieved_at: str | None) -> dict:
    return {
        "schedule": schedule_block(event.get("commence_time")),
        "score": score_block(event, None, retrieved_at=retrieved_at),
        "weather": weather_block(event, {}, retrieved_at=retrieved_at),
        "injuries": [],
        "injuries_note": "No report does not mean healthy or available.",
        "scheduled_fetch_enabled": SCHEDULED_FETCH_ENABLED,
    }


def attach_event_context(event: dict, bundle: dict, *, now: datetime | None = None) -> dict:
    retrieved = bundle.get("retrieved_at")
    scores = bundle.get("scores") or []
    matched = match_score_row(event, scores)
    weather_by_home = bundle.get("weather_by_home") or {}
    reports = bundle.get("injuries") or []
    event["context"] = {
        "schedule": schedule_block(event.get("commence_time")),
        "score": score_block(event, matched, retrieved_at=retrieved, now=now),
        "weather": weather_block(event, weather_by_home, retrieved_at=retrieved, now=now),
        "injuries": injury_rows_for_event(event, reports),
        "injuries_note": "No report does not mean healthy or available.",
        "scheduled_fetch_enabled": SCHEDULED_FETCH_ENABLED,
        "bundle_label": bundle.get("label"),
    }
    if matched is None:
        event["context"]["score"]["match"] = "none"
    return event


def labeled_demo_events(fixtures: dict) -> list[dict]:
    extra = []
    for row in fixtures.get("demo_events") or []:
        extra.append({
            "id": row["id"],
            "sport_key": row.get("sport_key") or "americanfootball_nfl",
            "sport_title": row.get("sport_title") or "NFL",
            "selector": row.get("selector") or "nfl",
            "home_team": row.get("home_team"),
            "away_team": row.get("away_team"),
            "commence_time": row.get("commence_time"),
            "kind": "game",
            "period": "game",
            "books": [],
            "book_names": [],
            "stale": False,
            "fixture_label": row.get("label"),
            "context_demo": True,
        })
    return extra


def attach_context(preview: dict, *, collected: dict | None = None, fixtures: dict | None = None, now: datetime | None = None) -> dict:
    collected = collected if collected is not None else load_collected_context()
    fixtures = fixtures if fixtures is not None else load_labeled_fixtures()
    include_demo = context_fixtures_enabled() and not is_production()
    events = list(preview.get("events") or [])
    if include_demo:
        existing = {e.get("id") for e in events}
        demos = [row for row in labeled_demo_events(fixtures) if row["id"] not in existing]
        events = demos + events
    live_bundle = {
        "retrieved_at": collected.get("retrieved_at"),
        "scores": collected.get("scores") or [],
        "weather_by_home": collected.get("weather_by_home") or {},
        "injuries": [],
        "label": collected.get("label") or "collected",
    }
    fixture_bundle = {
        "retrieved_at": fixtures.get("retrieved_at"),
        "scores": fixtures.get("scores") or [],
        "weather_by_home": fixtures.get("weather_by_home") or {},
        "injuries": fixtures.get("injuries") or [],
        "label": fixtures.get("label") or "FIXTURE_CONTEXT",
    }
    for event in events:
        if event.get("context_demo") or (include_demo and event.get("fixture_label")):
            attach_event_context(event, fixture_bundle, now=now)
        else:
            attach_event_context(event, live_bundle, now=now)
            if include_demo:
                # Labeled injuries never overlay real events unless event_id matches a fixture id.
                pass
    if include_demo:
        for row in preview.get("player_props") or []:
            inj = injury_for_player(row.get("player"), row.get("home_team") or row.get("away_team"), fixture_bundle["injuries"])
            if inj:
                row["availability"] = inj
    preview["events"] = events
    preview["game_context"] = {
        "scores": SCORES,
        "weather": WEATHER,
        "injuries": INJURIES,
        "scheduled_fetch_enabled": SCHEDULED_FETCH_ENABLED,
        "collected_present": bool(collected.get("scores") or collected.get("weather_by_home")),
        "fixtures_attached": include_demo,
        "postgres_redis": "blocked_until_docker",
    }
    return preview
