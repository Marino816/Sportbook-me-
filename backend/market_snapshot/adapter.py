"""Normalize saved Odds API snapshots into Market Tools views. Zero provider HTTP."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from market_snapshot.bounded_fetch import PRIVATE
from market_snapshot.contracts import (
    NOT_LIVE,
    PARLAY_ANALYTICAL_NOTE,
    SNAPSHOT_LABEL,
    american_to_decimal,
    decimal_to_american,
    line_key,
)
from market_snapshot.cost_estimate import estimate_monthly
from market_snapshot.source_record import SOURCE

PERIOD_GAME = "game"


def load_payloads(*, root: Path | None = None) -> dict:
    path = (root or PRIVATE) / "latest_payloads.json"
    if not path.is_file():
        raise FileNotFoundError(f"No saved Odds API snapshot at {path}. Run the bounded fetch first.")
    return json.loads(path.read_text())


def _outcomes(market: dict) -> list[dict]:
    return list(market.get("outcomes") or [])


def flatten_odds(sport_key: str, sport_title: str, events: list) -> list[dict]:
    rows = []
    for event in events or []:
        event_id = event.get("id")
        commence = event.get("commence_time")
        home = event.get("home_team")
        away = event.get("away_team")
        for book in event.get("bookmakers") or []:
            book_key = book.get("key")
            book_title = book.get("title")
            book_update = book.get("last_update")
            for market in book.get("markets") or []:
                market_key = market.get("key")
                market_update = market.get("last_update") or book_update
                for outcome in _outcomes(market):
                    price = outcome.get("price")
                    point = outcome.get("point")
                    rows.append({
                        "event_id": event_id,
                        "sport_key": sport_key,
                        "sport_title": sport_title,
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker_key": book_key,
                        "bookmaker": book_title,
                        "market": market_key,
                        "selection": outcome.get("name"),
                        "player": outcome.get("description"),
                        "line": point,
                        "american": price,
                        "decimal": american_to_decimal(price),
                        "source_timestamp": market_update,
                        "period": PERIOD_GAME,
                        "snapshot": True,
                    })
    return rows


def compare_groups(rows: list[dict]) -> list[dict]:
    buckets: dict[tuple, list] = defaultdict(list)
    for row in rows:
        key = (
            row.get("event_id"),
            row.get("market"),
            (row.get("selection") or ""),
            line_key(row.get("line")),
            row.get("period") or PERIOD_GAME,
            row.get("player") or "",
        )
        buckets[key].append(row)
    groups = []
    for key, items in buckets.items():
        event_id, market, selection, line, period, player = key
        sample = items[0]
        prices = []
        for item in items:
            if item.get("american") is None:
                continue
            prices.append({
                "bookmaker": item.get("bookmaker"),
                "bookmaker_key": item.get("bookmaker_key"),
                "american": item.get("american"),
                "decimal": item.get("decimal"),
                "source_timestamp": item.get("source_timestamp"),
            })
        groups.append({
            "event_id": event_id,
            "sport_title": sample.get("sport_title"),
            "home_team": sample.get("home_team"),
            "away_team": sample.get("away_team"),
            "commence_time": sample.get("commence_time"),
            "market": market,
            "selection": selection,
            "player": player or None,
            "line": sample.get("line"),
            "period": period,
            "book_count": len(prices),
            "prices": prices,
            "missing_books": [i.get("bookmaker") for i in items if i.get("american") is None],
        })
    groups.sort(key=lambda g: (g.get("sport_title") or "", g.get("commence_time") or "", g.get("market") or ""))
    return groups


def flatten_player_props(payload: dict | None, *, requested_market: str | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = flatten_odds(payload.get("sport_key") or "", payload.get("sport_title") or "", [payload])
    for row in rows:
        row["prop_market"] = row.get("market")
        row["requested_market"] = requested_market
    return rows


def parlay_pool(game_rows: list[dict], prop_rows: list[dict]) -> list[dict]:
    pool = []
    seen = set()
    for row in game_rows + prop_rows:
        if row.get("american") is None:
            continue
        token = (
            row.get("event_id"),
            row.get("market"),
            row.get("selection"),
            line_key(row.get("line")),
            row.get("bookmaker_key"),
            row.get("player") or "",
        )
        if token in seen:
            continue
        seen.add(token)
        pool.append({
            "id": "|".join(str(x) for x in token),
            "event_id": row.get("event_id"),
            "sport_title": row.get("sport_title"),
            "label": " ".join(
                x for x in [
                    row.get("away_team"),
                    "@",
                    row.get("home_team"),
                    row.get("market"),
                    row.get("player"),
                    row.get("selection"),
                    str(row.get("line") if row.get("line") is not None else ""),
                    row.get("bookmaker"),
                ] if x not in (None, "")
            ),
            "market": row.get("market"),
            "selection": row.get("selection"),
            "player": row.get("player"),
            "line": row.get("line"),
            "bookmaker": row.get("bookmaker"),
            "american": row.get("american"),
            "decimal": row.get("decimal"),
            "period": row.get("period"),
        })
    return pool


def combine_parlay(legs: list[dict]) -> dict:
    decimals = []
    event_ids = []
    missing = []
    for leg in legs:
        dec = american_to_decimal(leg.get("american"))
        event_ids.append(str(leg.get("event_id") or ""))
        if dec is None:
            missing.append(leg)
            continue
        decimals.append(dec)
    same_game = len([e for e in event_ids if e]) >= 2 and len(set(e for e in event_ids if e)) < len([e for e in event_ids if e])
    if missing or len(decimals) < 2:
        return {
            "ok": False,
            "reason": "Parlay needs at least two selections with quoted American odds.",
            "bookmaker_confirmed_quote": False,
            "analytical_only": True,
            "note": PARLAY_ANALYTICAL_NOTE,
            "same_game": same_game,
        }
    combined = 1.0
    for dec in decimals:
        combined *= dec
    return {
        "ok": True,
        "bookmaker_confirmed_quote": False,
        "analytical_only": True,
        "note": PARLAY_ANALYTICAL_NOTE,
        "same_game": same_game,
        "same_game_warning": (
            "Same-game legs are included in the arithmetic product only. "
            "This is not a bookmaker same-game parlay quote."
            if same_game else None
        ),
        "combined_decimal": round(combined, 4),
        "combined_american": decimal_to_american(combined),
        "leg_count": len(decimals),
        "stake": 100,
        "analytical_payout_at_100": round(100 * combined, 2),
    }


def build_preview(*, root: Path | None = None) -> dict:
    payloads = load_payloads(root=root)
    index = payloads.get("index") or {}
    odds_map = payloads.get("odds") or {}
    titles = {k: t for k, t in (("americanfootball_nfl", "NFL"), ("americanfootball_ncaaf", "NCAAF"), ("baseball_mlb", "MLB"))}
    game_rows = []
    coverage = {}
    sports_payload = payloads.get("sports") or []
    active = {row.get("key"): row for row in sports_payload if isinstance(row, dict)}
    for sport_key, title in titles.items():
        events = odds_map.get(sport_key) or []
        listed = sport_key in active
        rows = flatten_odds(sport_key, title, events if isinstance(events, list) else [])
        game_rows.extend(rows)
        markets = sorted({r["market"] for r in rows if r.get("market")})
        books = sorted({r["bookmaker"] for r in rows if r.get("bookmaker")})
        coverage[title] = {
            "sport_key": sport_key,
            "in_sports_catalog": listed,
            "event_count": len(events) if isinstance(events, list) else 0,
            "price_rows": len(rows),
            "markets_present": markets,
            "bookmakers_present": books,
            "featured_h2h": "h2h" in markets,
            "featured_spreads": "spreads" in markets,
            "featured_totals": "totals" in markets,
        }
        for mkt in ("h2h", "spreads", "totals"):
            if mkt not in markets:
                coverage[title][f"{mkt}_status"] = "unavailable_in_this_snapshot" if isinstance(events, list) else "unknown"
    prop_payload = payloads.get("player_props")
    prop_meta = index.get("player_props") or {}
    prop_rows = flatten_player_props(prop_payload if isinstance(prop_payload, dict) else None, requested_market=prop_meta.get("requested_market"))
    return {
        "development": True,
        "live_data": False,
        "label": SNAPSHOT_LABEL,
        "not_live_label": NOT_LIVE,
        "parlay_note": PARLAY_ANALYTICAL_NOTE,
        "retrieved": {
            "imported_at": index.get("imported_at"),
            "http_requests_used": index.get("http_requests_used"),
            "credits_used_from_headers": index.get("credits_used_from_headers"),
        },
        "source": SOURCE,
        "live_odds": game_rows,
        "compare": compare_groups(game_rows),
        "player_props": prop_rows,
        "player_props_note": index.get("player_props_note"),
        "player_props_requested_market": prop_meta.get("requested_market"),
        "parlay_pool": parlay_pool(game_rows, prop_rows),
        "coverage": coverage,
        "untested": SOURCE["untested_coverage"],
        "compatibility_gaps": SOURCE["compatibility_gaps"],
        "unsupported_period_markets": "unavailable",
        "monthly_usage_estimate": estimate_monthly(),
        "http_requests_used": 0,
    }
