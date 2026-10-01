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
    """Project Odds API cache rows onto existing consumer contracts. Never invent SGO IDs."""
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
    ctx = ev.get("context") or {}
    score = ctx.get("score") or {}
    home_score = score.get("home_score")
    away_score = score.get("away_score")
    status = score.get("status")
    has_score = home_score is not None or away_score is not None or status in {"in_progress", "final"}
    return {
        "game_id": ev.get("id"),
        "id": ev.get("id"),
        "event_id": ev.get("id"),
        "home_team_name": ev.get("home_team"),
        "away_team_name": ev.get("away_team"),
        "start_time": ev.get("commence_time"),
        "start_time_utc": (ctx.get("schedule") or {}).get("commence_time_utc") or ev.get("commence_time"),
        "status": status,
        "status_display": score.get("status_display"),
        "home_score": home_score,
        "away_score": away_score,
        "period": score.get("period"),
        "inning": score.get("inning"),
        "clock": score.get("clock"),
        "weather": ctx.get("weather"),
        "injuries": ctx.get("injuries") or [],
        "total_line": (totals.get("over") or {}).get("line"),
        "spread_line": (spreads.get("home") or {}).get("line"),
        "moneyline_home": home_ml,
        "moneyline_away": away_ml,
        "odds": odds,
        "sgo_event_id": None,
        "movement": "unavailable",
        "live_score": "available" if has_score else "unavailable",
        "source_timestamp": score.get("source_updated_at") or (h2h.get("home") or {}).get("source_timestamp"),
        "retrieved_at": score.get("retrieved_at") or (h2h.get("home") or {}).get("retrieved_at"),
        "installed_mobile_tested": False,
    }


def assistant_event_row(ev: dict, sport: str) -> dict:
    ctx = ev.get("context") or {}
    score = ctx.get("score") or {}
    home_score = score.get("home_score")
    away_score = score.get("away_score")
    status = score.get("status")
    has_score = home_score is not None or away_score is not None or status in {"in_progress", "final"}
    return {
        "event_id": ev.get("id"),
        "league": sport,
        "start_time": ev.get("commence_time"),
        "start_time_utc": (ctx.get("schedule") or {}).get("commence_time_utc") or ev.get("commence_time"),
        "status": status,
        "status_display": score.get("status_display") or "unavailable",
        "home_team": ev.get("home_team"),
        "away_team": ev.get("away_team"),
        "home_score": home_score,
        "away_score": away_score,
        "period": score.get("period"),
        "inning": score.get("inning"),
        "clock": score.get("clock"),
        "weather": ctx.get("weather"),
        "injuries": ctx.get("injuries") or [],
        "sgo_event_id": None,
        "live_score": "available" if has_score else "unavailable",
        "installed_mobile_tested": False,
    }


def assistant_market_equivalents(ev: dict) -> dict:
    """Map Odds API book quotes onto assistant fair/consensus fields. No SGP or team props."""
    from market_snapshot.analysis import consensus_prices

    books = ev.get("books") or []
    fair = None
    for book in books:
        if book.get("fair_h2h"):
            fair = {
                "source": "oddsapi_devig",
                "method": "proportional_overround_removal",
                "h2h": book.get("fair_h2h"),
                "spreads": book.get("fair_spreads"),
                "totals": book.get("fair_totals"),
                "note": "Market-derived from Odds API bookmaker prices on this event. Not an SGO fairOdds nested object.",
            }
            break
    prices = []
    for book in books:
        h2h = book.get("h2h") or {}
        for side in ("home", "away", "draw"):
            quote = h2h.get(side)
            if quote and quote.get("american") is not None:
                prices.append({
                    "bookmaker_key": book.get("bookmaker_key"),
                    "bookmaker": book.get("bookmaker"),
                    "american": quote.get("american"),
                    "selection": side,
                })
    consensus = {}
    for side in ("home", "away", "draw"):
        side_prices = [p for p in prices if p["selection"] == side]
        if side_prices:
            consensus[side] = consensus_prices(side_prices)
    return {
        "fair_odds": fair if fair else "unavailable",
        "fair_odds_reason": None if fair else "Incomplete bookmaker outcome set; fair odds were not invented.",
        "book_consensus": consensus or "unavailable",
        "team_props": [],
        "sgp_quote": "unavailable",
        "movement": "unavailable",
    }


def filter_events_for_league(events: list[dict], league: str) -> list[dict]:
    selector = league_to_selector(league)
    if not selector:
        return []
    return [e for e in events or [] if (e.get("selector") or "") == selector]
