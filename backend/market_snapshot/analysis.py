"""Market-derived fair odds, consensus, and snapshot arbitrage. No provider HTTP."""

from __future__ import annotations

from statistics import median

from market_snapshot.contracts import american_to_decimal, decimal_to_american, line_key
from market_snapshot.leagues import MARKET_PERIOD

FAIR_LABEL = "Market-derived fair odds"
ARB_LABEL = "Historical price discrepancy—not verified live."
DEVIG_METHOD = (
    "Proportional overround removal: each outcome's implied probability is divided by the "
    "sum of implied probabilities from the same bookmaker, market, line, and period."
)
CONSENSUS_METHOD = (
    "Median vig-inclusive implied probability across unique bookmakers for the same "
    "event, market, selection, line, and period. Duplicate book records are not "
    "independent observations. This is not a complete outcome distribution and is "
    "not de-vigged."
)


def implied_probability(american) -> float | None:
    if american is None:
        return None
    try:
        a = int(american)
    except (TypeError, ValueError):
        return None
    if a > 0:
        return 100.0 / (a + 100.0)
    if a < 0:
        return abs(a) / (abs(a) + 100.0)
    return None


def fair_from_complete(americans: list) -> dict | None:
    imps = [implied_probability(a) for a in americans]
    if any(p is None for p in imps) or len(imps) < 2:
        return None
    total = sum(imps)
    if total <= 0:
        return None
    fair_probs = [p / total for p in imps]
    summed = round(sum(fair_probs), 6)
    fair_decimal = [round(1.0 / p, 4) if p > 0 else None for p in fair_probs]
    fair_american = [decimal_to_american(d) if d else None for d in fair_decimal]
    return {
        "method": DEVIG_METHOD,
        "label": FAIR_LABEL,
        "overround": round(total - 1.0, 4),
        "fair_probabilities": [round(p, 4) for p in fair_probs],
        "probability_sum": summed,
        "normalized": True,
        "includes_bookmaker_margin": False,
        "raw_implied_includes_margin": True,
        "fair_american": fair_american,
        "fair_decimal": fair_decimal,
        "sbme_predictive": False,
    }


def _ts_range(timestamps: list[str]) -> dict:
    present = [t for t in timestamps if t]
    return {
        "earliest": min(present) if present else None,
        "latest": max(present) if present else None,
        "missing_timestamps": len(present) != len(timestamps),
    }


def consensus_prices(prices: list[dict]) -> dict | None:
    """prices: unique bookmaker observations for one selection/line/period."""
    by_book: dict[str, dict] = {}
    for row in prices:
        key = row.get("bookmaker_key") or row.get("bookmaker")
        if not key or row.get("american") is None:
            continue
        by_book[str(key)] = row
    unique = list(by_book.values())
    imps = [implied_probability(r.get("american")) for r in unique]
    imps = [p for p in imps if p is not None]
    if len(imps) < 2:
        return None
    mid = float(median(imps))
    if mid <= 0 or mid >= 1:
        return None
    rng = _ts_range([r.get("source_timestamp") for r in unique])
    return {
        "method": CONSENSUS_METHOD,
        "book_count": len(unique),
        "american": decimal_to_american(round(1.0 / mid, 4)),
        "decimal": round(1.0 / mid, 4),
        "implied_probability": round(mid, 4),
        "includes_bookmaker_margin": True,
        "is_complete_distribution": False,
        "normalized": False,
        "equivalent_market": {
            "event": True,
            "market": True,
            "selection": True,
            "line": True,
            "period": True,
            "player": True,
        },
        "settlement_rules": "unconfirmed",
        "timestamp_range": rng,
        "label": "Book consensus (median vig-inclusive implied probability — not de-vigged)",
    }


def attach_fair_to_books(event: dict) -> None:
    for book in event.get("books") or []:
        h2h = book.get("h2h") or {}
        soccer = bool(h2h.get("draw"))
        if soccer:
            sides = ["away", "draw", "home"]
        else:
            sides = ["away", "home"]
        quotes = [h2h.get(s) for s in sides]
        if any(q is None or q.get("american") is None for q in quotes):
            book["fair_h2h"] = None
            book["fair_h2h_unavailable"] = "incomplete_outcome_set"
        else:
            result = fair_from_complete([q["american"] for q in quotes])
            if result:
                mapped = {sides[i]: {"american": result["fair_american"][i], "decimal": result["fair_decimal"][i], "probability": result["fair_probabilities"][i]} for i in range(len(sides))}
                book["fair_h2h"] = {**result, "sides": mapped}
            else:
                book["fair_h2h"] = None
        for market_key, needed in (("spreads", ["away", "home"]), ("totals", ["over", "under"])):
            block = book.get(market_key) or {}
            quotes = [block.get(s) for s in needed]
            attr = f"fair_{market_key}"
            if any(q is None or q.get("american") is None for q in quotes):
                book[attr] = None
                continue
            lines = {line_key(q.get("line")) for q in quotes}
            if len(lines) != 1:
                book[attr] = None
                continue
            result = fair_from_complete([q["american"] for q in quotes])
            book[attr] = result


def enrich_compare_groups(groups: list[dict]) -> list[dict]:
    for group in groups:
        group["consensus"] = consensus_prices(group.get("prices") or [])
        group["equivalent_market"] = {
            "event_id": group.get("event_id"),
            "market": group.get("market"),
            "selection": group.get("selection"),
            "line": group.get("line"),
            "period": group.get("period"),
            "player": group.get("player"),
        }
        integer = False
        try:
            integer = float(group.get("line")).is_integer() if group.get("line") not in (None, "") else False
        except (TypeError, ValueError):
            integer = False
        group["settlement_rules"] = "unconfirmed"
        group["settlement_compatible"] = False if integer or group.get("period") not in {None, "", MARKET_PERIOD, "game"} else None
        if integer:
            group["settlement_note"] = "Integer line may push/void. Missing settlement rules are not treated as confirmed compatibility."
        group["fair_odds_note"] = (
            "Fair odds are a normalized complete-set distribution per sportsbook after proportional margin removal. "
            "Consensus on this row includes bookmaker margin and is not that distribution."
        )
    return groups


def _best(prices: list[dict]) -> dict | None:
    quoted = [p for p in prices if p.get("american") is not None]
    if not quoted:
        return None
    return max(quoted, key=lambda p: p["american"])


def scan_arbitrage(groups: list[dict], events: list[dict]) -> list[dict]:
    """Cross-book snapshot discrepancies. Not live and not guaranteed profit."""
    found = []
    soccer_events = {e["id"] for e in events if e.get("selector") == "soccer"}
    buckets: dict[tuple, dict] = {}
    for g in groups:
        key = (g.get("event_id"), g.get("market"), g.get("period") or MARKET_PERIOD, line_key(g.get("line")), g.get("player") or "")
        buckets.setdefault(key, {})[g.get("selection")] = g
    for key, by_sel in buckets.items():
        event_id, market, period, line, player = key
        if market == "spreads":
            continue
        if market == "h2h" and event_id in soccer_events:
            needed = None
            # identify home/away/draw by scanning selections later
            sels = list(by_sel.values())
            names = {g.get("selection") for g in sels}
            if "Draw" not in names and not any((g.get("selection") or "").lower() == "draw" for g in sels):
                continue
            draw = next((g for g in sels if (g.get("selection") or "").lower() == "draw"), None)
            others = [g for g in sels if g is not draw]
            if draw is None or len(others) != 2:
                continue
            bests = [_best(g.get("prices") or []) for g in (others[0], others[1], draw)]
            if any(b is None for b in bests):
                continue
            books = {b.get("bookmaker_key") or b.get("bookmaker") for b in bests}
            if len(books) < 2:
                continue
            if _unsuitable_ts(bests):
                continue
            decs = [american_to_decimal(b["american"]) for b in bests]
            if any(d is None or d <= 1 for d in decs):
                continue
            implied = sum(1.0 / d for d in decs)
            if implied >= 1.0:
                continue
            found.append(_arb_row(event_id, "h2h", period, line, bests, implied, "3-way including draw"))
            continue
        if market == "h2h" and event_id not in soccer_events:
            if len(by_sel) != 2:
                continue
            pair = list(by_sel.values())
            found.extend(_two_way(event_id, market, period, line, pair, push=False))
        if market == "totals":
            if len(by_sel) != 2:
                continue
            pair = list(by_sel.values())
            push = _integer_line(line)
            found.extend(_two_way(event_id, market, period, line, pair, push=push))
    found.extend(_spread_arbs(groups))
    return found[:40]


def _spread_arbs(groups: list[dict]) -> list[dict]:
    buckets: dict[tuple, list] = {}
    for g in groups:
        if g.get("market") != "spreads":
            continue
        try:
            mag = abs(float(g.get("line")))
        except (TypeError, ValueError):
            continue
        key = (g.get("event_id"), g.get("period") or MARKET_PERIOD, f"{mag:g}")
        buckets.setdefault(key, []).append(g)
    out = []
    for (event_id, period, mag), items in buckets.items():
        if len(items) != 2:
            continue
        out.extend(_two_way(event_id, "spreads", period, mag, items, push=_integer_line(mag)))
    return out


def _integer_line(line: str) -> bool:
    if not line:
        return False
    try:
        return float(line).is_integer()
    except (TypeError, ValueError):
        return False


def _unsuitable_ts(bests: list[dict]) -> bool:
    times = [b.get("source_timestamp") for b in bests]
    if any(not t for t in times):
        return True
    try:
        return abs(_hours(min(times), max(times))) > 2
    except Exception:
        return True


def _hours(a: str, b: str) -> float:
    from datetime import datetime
    def parse(raw: str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return (parse(b) - parse(a)).total_seconds() / 3600.0


def _two_way(event_id, market, period, line, pair, *, push: bool) -> list[dict]:
    bests = [_best(g.get("prices") or []) for g in pair]
    if any(b is None for b in bests):
        return []
    if _unsuitable_ts(bests):
        return []
    books = {b.get("bookmaker_key") or b.get("bookmaker") for b in bests}
    if len(books) < 2:
        return []
    decs = [american_to_decimal(b["american"]) for b in bests]
    if any(d is None or d <= 1 for d in decs):
        return []
    implied = sum(1.0 / d for d in decs)
    if implied >= 1.0:
        return []
    if push:
        return [{
            "ok": False,
            "event_id": event_id,
            "market": market,
            "period": period,
            "line": line,
            "unavailable": True,
            "reason": "Push/void is possible on this integer line and is not separately quoted. Arbitrage is unsupported.",
            "label": ARB_LABEL,
        }]
    return [_arb_row(event_id, market, period, line, bests, implied, "2-way")]


def _arb_row(event_id, market, period, line, bests, implied, kind) -> dict:
    return {
        "ok": True,
        "event_id": event_id,
        "market": market,
        "period": period,
        "line": line,
        "kind": kind,
        "implied_total": round(implied, 4),
        "discrepancy_pct": round((1.0 - implied) * 100, 2),
        "legs": [{"bookmaker": b.get("bookmaker"), "american": b.get("american"), "source_timestamp": b.get("source_timestamp")} for b in bests],
        "source_timestamps": [b.get("source_timestamp") for b in bests],
        "label": ARB_LABEL,
        "executable": False,
        "guaranteed_profit": False,
        "live": False,
    }
