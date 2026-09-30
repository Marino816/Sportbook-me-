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
from market_snapshot.leagues import (
    LEAGUES,
    MARKET_PERIOD,
    PROP_MARKET_NAMES,
    SPORT_SELECTOR,
    league_by_key,
)
from market_snapshot.source_record import SOURCE


def load_payloads(*, root: Path | None = None) -> dict:
    path = (root or PRIVATE) / "latest_payloads.json"
    if not path.is_file():
        raise FileNotFoundError(f"No saved Odds API snapshot at {path}. Run the bounded fetch first.")
    return json.loads(path.read_text())


def _outcomes(market: dict) -> list[dict]:
    return list(market.get("outcomes") or [])


def _period_for_market(market_key: str | None) -> str:
    key = market_key or ""
    markers = ("_h1", "_h2", "_q1", "_q2", "_q3", "_q4", "_p1", "_p2", "_p3", "_1st_", "_s1", "_s2")
    if any(m in key for m in markers):
        return key
    return MARKET_PERIOD


def flatten_odds(sport_key: str, sport_title: str, events: list) -> list[dict]:
    meta = league_by_key(sport_key) or {}
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
                period = _period_for_market(market_key)
                for outcome in _outcomes(market):
                    price = outcome.get("price")
                    point = outcome.get("point")
                    selection = outcome.get("name")
                    player = outcome.get("description")
                    if meta.get("kind") == "outright" and not player:
                        player = selection
                    rows.append({
                        "id": "|".join(str(x) for x in (
                            event_id,
                            market_key,
                            selection,
                            line_key(point),
                            book_key,
                            player or "",
                            period,
                        )),
                        "event_id": event_id,
                        "sport_key": sport_key,
                        "sport_title": sport_title,
                        "sport_group": meta.get("sport_group") or sport_title,
                        "selector": meta.get("selector"),
                        "kind": meta.get("kind") or "match",
                        "commence_time": commence,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker_key": book_key,
                        "bookmaker": book_title,
                        "market": market_key,
                        "market_label": (meta.get("labels") or {}).get(market_key) or market_key,
                        "selection": selection,
                        "player": player,
                        "line": point,
                        "american": price,
                        "decimal": american_to_decimal(price),
                        "source_timestamp": market_update,
                        "period": period,
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
            row.get("period") or MARKET_PERIOD,
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
        best = None
        if prices:
            best_val = max(p["american"] for p in prices)
            best = [p["bookmaker"] for p in prices if p["american"] == best_val]
            for p in prices:
                p["best_listed"] = p["american"] == best_val
        groups.append({
            "event_id": event_id,
            "sport_title": sample.get("sport_title"),
            "sport_group": sample.get("sport_group"),
            "selector": sample.get("selector"),
            "kind": sample.get("kind"),
            "home_team": sample.get("home_team"),
            "away_team": sample.get("away_team"),
            "commence_time": sample.get("commence_time"),
            "market": market,
            "market_label": sample.get("market_label"),
            "selection": selection,
            "player": player or None,
            "line": sample.get("line"),
            "period": period,
            "book_count": len(prices),
            "prices": prices,
            "best_listed_price": best,
            "best_listed_tie": bool(best and len(best) > 1),
            "missing_books": [i.get("bookmaker") for i in items if i.get("american") is None],
        })
    groups.sort(key=lambda g: (g.get("sport_title") or "", g.get("commence_time") or "", g.get("market") or ""))
    return groups


def flatten_player_props(payload: dict | None, *, requested_market: str | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = flatten_odds(payload.get("sport_key") or "", payload.get("sport_title") or "", [payload])
    readable = PROP_MARKET_NAMES.get(requested_market or "", requested_market)
    for row in rows:
        row["prop_market"] = row.get("market")
        row["requested_market"] = requested_market
        row["market_label"] = PROP_MARKET_NAMES.get(row.get("market") or "", readable or row.get("market"))
    return rows


def _quote(row: dict) -> dict | None:
    if row.get("american") is None:
        return None
    return {
        "id": "|".join(str(x) for x in (
            row.get("event_id"),
            row.get("market"),
            row.get("selection"),
            line_key(row.get("line")),
            row.get("bookmaker_key"),
            row.get("player") or "",
            row.get("period"),
        )),
        "american": row.get("american"),
        "decimal": row.get("decimal"),
        "line": row.get("line"),
        "source_timestamp": row.get("source_timestamp"),
        "bookmaker": row.get("bookmaker"),
        "bookmaker_key": row.get("bookmaker_key"),
        "period": row.get("period"),
    }


def build_event_cards(rows: list[dict]) -> list[dict]:
    events: dict[str, dict] = {}
    for row in rows:
        eid = str(row.get("event_id") or "")
        if not eid:
            continue
        event = events.setdefault(eid, {
            "id": eid,
            "sport_key": row.get("sport_key"),
            "sport_title": row.get("sport_title"),
            "sport_group": row.get("sport_group"),
            "selector": row.get("selector"),
            "kind": row.get("kind") or "match",
            "commence_time": row.get("commence_time"),
            "home_team": row.get("home_team"),
            "away_team": row.get("away_team"),
            "period": row.get("period") or MARKET_PERIOD,
            "books": {},
        })
        bkey = row.get("bookmaker_key") or row.get("bookmaker") or "unknown"
        book = event["books"].setdefault(bkey, {
            "bookmaker_key": row.get("bookmaker_key"),
            "bookmaker": row.get("bookmaker"),
            "h2h": {},
            "spreads": {},
            "totals": {},
            "outrights": [],
        })
        quote = _quote(row)
        market = row.get("market")
        selection = row.get("selection") or ""
        if market == "h2h" and quote:
            side = "draw" if selection.lower() == "draw" else (
                "home" if selection == row.get("home_team") else (
                    "away" if selection == row.get("away_team") else selection
                )
            )
            book["h2h"][side] = {**quote, "selection": selection}
        elif market == "spreads" and quote:
            side = "home" if selection == row.get("home_team") else (
                "away" if selection == row.get("away_team") else selection
            )
            book["spreads"][side] = {**quote, "selection": selection}
        elif market == "totals" and quote:
            side = selection.lower() if selection.lower() in {"over", "under"} else selection
            book["totals"][side] = {**quote, "selection": selection}
        elif market == "outrights" and quote:
            book["outrights"].append({
                **quote,
                "player": row.get("player") or selection,
                "selection": selection,
            })
    cards = []
    for event in events.values():
        books = list(event["books"].values())
        for book in books:
            book["outrights"].sort(key=lambda r: r.get("american") or 0, reverse=True)
        event["books"] = books
        event["book_names"] = sorted({b.get("bookmaker") for b in books if b.get("bookmaker")})
        cards.append(event)
    cards.sort(key=lambda e: (e.get("commence_time") or "", e.get("sport_title") or ""))
    return cards


def parlay_conflict(a: dict, b: dict) -> bool:
    if a.get("event_id") != b.get("event_id"):
        return False
    if (a.get("period") or MARKET_PERIOD) != (b.get("period") or MARKET_PERIOD):
        return False
    if a.get("market") != b.get("market"):
        return False
    if a.get("market") == "h2h":
        return (a.get("selection") or "") != (b.get("selection") or "")
    if a.get("market") in {"spreads", "totals"}:
        return line_key(a.get("line")) == line_key(b.get("line")) and (a.get("selection") or "") != (b.get("selection") or "")
    if a.get("market") == "outrights":
        return (a.get("player") or a.get("selection")) != (b.get("player") or b.get("selection"))
    return False


def parlay_duplicate(a: dict, b: dict) -> bool:
    return (
        a.get("event_id") == b.get("event_id")
        and a.get("market") == b.get("market")
        and (a.get("selection") or "") == (b.get("selection") or "")
        and line_key(a.get("line")) == line_key(b.get("line"))
        and (a.get("period") or MARKET_PERIOD) == (b.get("period") or MARKET_PERIOD)
        and (a.get("player") or "") == (b.get("player") or "")
    )


def combine_parlay(legs: list[dict]) -> dict:
    if len(legs) < 2:
        return {
            "ok": False,
            "reason": "Select at least two legs.",
            "bookmaker_confirmed_quote": False,
            "combined_suppressed": True,
        }
    for i, left in enumerate(legs):
        for right in legs[i + 1:]:
            if parlay_duplicate(left, right):
                return {
                    "ok": False,
                    "reason": "Duplicate selection. The same event, market, selection, line, and period is already on the slip.",
                    "bookmaker_confirmed_quote": False,
                    "combined_suppressed": True,
                    "duplicate": True,
                }
            if parlay_conflict(left, right):
                return {
                    "ok": False,
                    "reason": "Conflicting selections on the same event and market were not added together.",
                    "bookmaker_confirmed_quote": False,
                    "combined_suppressed": True,
                    "conflict": True,
                }
    decimals = []
    missing = []
    event_ids = []
    books = set()
    for leg in legs:
        event_ids.append(str(leg.get("event_id") or ""))
        if leg.get("bookmaker"):
            books.add(leg.get("bookmaker"))
        dec = american_to_decimal(leg.get("american"))
        if dec is None:
            missing.append(leg)
            continue
        decimals.append(dec)
    same_game = len([e for e in event_ids if e]) >= 2 and len(set(e for e in event_ids if e)) < len([e for e in event_ids if e])
    mixed_books = len(books) > 1
    if missing or len(decimals) < 2:
        return {
            "ok": False,
            "reason": "Parlay needs at least two selections with quoted American odds.",
            "bookmaker_confirmed_quote": False,
            "analytical_only": True,
            "combined_suppressed": True,
            "note": PARLAY_ANALYTICAL_NOTE,
            "same_game": same_game,
            "mixed_books": mixed_books,
        }
    if same_game:
        return {
            "ok": False,
            "reason": "Same-game combinations have no verified sportsbook pricing method in this preview. Combined odds are not shown.",
            "bookmaker_confirmed_quote": False,
            "combined_suppressed": True,
            "same_game": True,
            "mixed_books": mixed_books,
            "leg_count": len(legs),
        }
    combined = 1.0
    for dec in decimals:
        combined *= dec
    return {
        "ok": True,
        "bookmaker_confirmed_quote": False,
        "analytical_only": True,
        "combined_suppressed": False,
        "label": "Illustrative combined odds—not a sportsbook quote.",
        "note": PARLAY_ANALYTICAL_NOTE,
        "same_game": False,
        "mixed_books": mixed_books,
        "mixed_book_note": "Selections come from more than one sportsbook." if mixed_books else None,
        "combined_decimal": round(combined, 4),
        "combined_american": decimal_to_american(combined),
        "leg_count": len(decimals),
    }


def _coverage_row(league: dict, catalog: dict, odds_map: dict, tested_keys: set[str]) -> dict:
    key = league["key"]
    events = odds_map.get(key)
    in_catalog = key in catalog
    tested = key in tested_keys
    event_list = events if isinstance(events, list) else []
    rows = flatten_odds(key, league["title"], event_list) if tested else []
    markets_present = {r["market"] for r in rows if r.get("market")}
    market_status = {}
    for mkt in league["markets"]:
        if not tested:
            market_status[mkt] = "not_tested"
        elif mkt in markets_present:
            market_status[mkt] = "present"
        elif tested and isinstance(events, list) and not event_list:
            market_status[mkt] = "no_events_returned"
        else:
            market_status[mkt] = "unavailable_in_this_snapshot"
    if not in_catalog and not tested:
        status = "documented_not_in_catalog"
    elif not tested:
        status = "not_tested"
    elif not event_list:
        status = "no_events_returned"
    else:
        status = "tested"
    return {
        "key": key,
        "title": league["title"],
        "sport_group": league["sport_group"],
        "kind": league["kind"],
        "documented": True,
        "in_catalog": in_catalog,
        "tested": tested,
        "status": status,
        "event_count": len(event_list) if tested else None,
        "markets": market_status,
        "labels": league.get("labels"),
        "bookmakers": sorted({r.get("bookmaker") for r in rows if r.get("bookmaker")}) if tested else [],
        "note": league.get("docs_note") or league.get("golf_coverage"),
        "empty_does_not_prove_no_coverage": status == "no_events_returned",
    }


def build_preview(*, root: Path | None = None) -> dict:
    payloads = load_payloads(root=root)
    index = payloads.get("index") or {}
    odds_map = payloads.get("odds") or {}
    sports_payload = payloads.get("sports") or []
    catalog = {row.get("key"): row for row in sports_payload if isinstance(row, dict)}
    tested_keys = {k for k, v in odds_map.items() if isinstance(v, list)}
    game_rows = []
    for league in LEAGUES:
        events = odds_map.get(league["key"])
        if not isinstance(events, list):
            continue
        game_rows.extend(flatten_odds(league["key"], league["title"], events))
    coverage = [_coverage_row(league, catalog, odds_map, tested_keys) for league in LEAGUES]
    prop_payload = payloads.get("player_props")
    prop_meta = index.get("player_props") or {}
    prop_rows = flatten_player_props(
        prop_payload if isinstance(prop_payload, dict) else None,
        requested_market=prop_meta.get("requested_market"),
    )
    expansion = index.get("expansion") or {}
    soccer_leagues = [
        {"id": row["key"], "label": row["title"]}
        for row in LEAGUES if row["selector"] == "soccer"
    ]
    quote_index = {row["id"]: row for row in game_rows + prop_rows if row.get("id")}
    return {
        "development": True,
        "live_data": False,
        "label": SNAPSHOT_LABEL,
        "notice": "Preview • Saved odds • Not live.",
        "not_live_label": NOT_LIVE,
        "odds_format_default": "american",
        "parlay_note": "Illustrative combined odds—not a sportsbook quote.",
        "retrieved": {
            "imported_at": index.get("imported_at"),
            "http_requests_used": index.get("http_requests_used"),
            "credits_used_from_headers": index.get("credits_used_from_headers"),
            "expansion_http": expansion.get("additional_http_requests"),
            "expansion_credits": expansion.get("additional_credits"),
            "remaining_credits_header": expansion.get("remaining_credits_header"),
        },
        "source": SOURCE,
        "sport_selector": list(SPORT_SELECTOR),
        "soccer_leagues": soccer_leagues,
        "events": build_event_cards(game_rows),
        "compare": compare_groups(game_rows),
        "player_props": prop_rows,
        "player_props_note": index.get("player_props_note") or "Player props were sampled for one NFL pass-touchdowns market only. Other sports and markets are untested.",
        "player_props_requested_market": prop_meta.get("requested_market"),
        "player_props_market_label": PROP_MARKET_NAMES.get(prop_meta.get("requested_market") or "", prop_meta.get("requested_market")),
        "player_props_untested": True,
        "quote_index": quote_index,
        "coverage": coverage,
        "coverage_by_title": {row["title"]: row for row in coverage},
        "untested": SOURCE["untested_coverage"],
        "compatibility_gaps": SOURCE["compatibility_gaps"],
        "golf_coverage_note": "Golf in this preview is documented tournament-winner markets only. Weekly PGA Tour coverage is not claimed.",
        "unsupported_period_markets": "unavailable",
        "monthly_usage_estimate": estimate_monthly(),
        "http_requests_used": 0,
    }
