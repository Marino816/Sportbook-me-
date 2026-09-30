"""Project Odds API cache rows onto existing consumer contracts. Never invent SGO IDs."""

from __future__ import annotations

from market_snapshot.leagues import SPORT_SELECTOR


def unavailable(*, capability: str, reason: str, **extra) -> dict:
    return {
        "unavailable": True,
        "capability": capability,
        "reason": reason,
        "sgo_event_id": None,
        **extra,
    }


def league_to_selector(league: str) -> str | None:
    raw = (league or "").strip().lower()
    aliases = {
        "mlb": "mlb",
        "nfl": "nfl",
        "nba": "nba",
        "nhl": "nhl",
        "ncaaf": "ncaaf",
        "ncaab": "ncaab",
        "wnba": "wnba",
        "epl": "soccer",
        "mls": "soccer",
        "la_liga": "soccer",
        "bundesliga": "soccer",
        "fr_ligue_1": "soccer",
        "it_serie_a": "soccer",
        "uefa_champions_league": "soccer",
    }
    if raw in aliases:
        return aliases[raw]
    for row in SPORT_SELECTOR:
        if row.get("id") == raw:
            return raw
    return None


def event_card_to_mobile_game(ev: dict) -> dict:
    """Preserve the mobile live-odds Game fields. Scores and movement stay unavailable."""
    books = ev.get("books") or []
    first = books[0] if books else {}
    h2h = first.get("h2h") or {}
    spreads = first.get("spreads") or {}
    totals = first.get("totals") or {}
    home_ml = (h2h.get("home") or {}).get("american")
    away_ml = (h2h.get("away") or {}).get("american")
    odds = []
    for book in books:
        bh = book.get("h2h") or {}
        odds.append({
            "bookmaker_name": book.get("bookmaker"),
            "sportsbook": book.get("bookmaker"),
            "moneyline_home": (bh.get("home") or {}).get("american"),
            "moneyline_away": (bh.get("away") or {}).get("american"),
            "movements": [],
        })
    return {
        "game_id": ev.get("id"),
        "id": ev.get("id"),
        "event_id": ev.get("id"),
        "home_team_name": ev.get("home_team"),
        "away_team_name": ev.get("away_team"),
        "start_time": ev.get("commence_time"),
        "status": None,
        "home_score": None,
        "away_score": None,
        "total_line": (totals.get("over") or {}).get("line"),
        "spread_line": (spreads.get("home") or {}).get("line"),
        "moneyline_home": home_ml,
        "moneyline_away": away_ml,
        "odds": odds,
        "sgo_event_id": None,
        "movement": "unavailable",
        "live_score": "unavailable",
        "source_timestamp": (h2h.get("home") or {}).get("source_timestamp"),
        "retrieved_at": (h2h.get("home") or {}).get("retrieved_at"),
    }


def assistant_event_row(ev: dict, sport: str) -> dict:
    return {
        "event_id": ev.get("id"),
        "league": sport,
        "start_time": ev.get("commence_time"),
        "status": None,
        "status_display": "unavailable",
        "home_team": ev.get("home_team"),
        "away_team": ev.get("away_team"),
        "home_score": None,
        "away_score": None,
        "sgo_event_id": None,
        "live_score": "unavailable",
    }


def filter_events_for_league(events: list[dict], league: str) -> list[dict]:
    selector = league_to_selector(league)
    if not selector:
        return []
    return [e for e in events or [] if (e.get("selector") or "") == selector]
