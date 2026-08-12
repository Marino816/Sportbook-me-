"""
SB ME Odds Comparison Dashboard — cross-book line shopping backend.

Shows every bookmaker side by side for each market (moneyline, spread, total,
alternate lines, and player props), surfaces the best price per side, and
computes a consensus line across books.

Builds on :func:`market_engine.live_odds.track_market` for snapshot creation and
uses :func:`market_engine.bookmaker_rank` so books are always ordered by
priority. Pure functions operate on already-fetched data; no odds are invented.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Optional

from market_engine import *  # noqa: F401,F403  (foundation namespace per spec)
from market_engine import (
    BookmakerLine,
    MarketSnapshot,
    MarketType,
    bookmaker_rank,
    implied_probability,
)
from market_engine.live_odds import track_market

# Game markets presented side-by-side (canonical snapshot keys → UI metadata).
GAME_MARKET_KEYS = {
    "moneyline_home": {"market": "moneyline", "selection": "home"},
    "moneyline_away": {"market": "moneyline", "selection": "away"},
    "spread_home": {"market": "spread", "selection": "home"},
    "spread_away": {"market": "spread", "selection": "away"},
    "total_over": {"market": "total", "selection": "over"},
    "total_under": {"market": "total", "selection": "under"},
}


# ══════════════════════════════════════════════════════════════
#  Core functions
# ══════════════════════════════════════════════════════════════

def compute_consensus(snapshots, method: str = "median") -> Optional[float]:
    """Consensus line across books for a market.

    ``snapshots`` may be a single :class:`MarketSnapshot`, a list of them, or a
    list of raw line floats. ``method`` is ``"median"`` (default) or ``"mean"``.
    """
    if isinstance(snapshots, MarketSnapshot):
        lines = [b.line for b in snapshots.books if b.line is not None]
    elif isinstance(snapshots, (list, tuple)):
        lines = []
        for s in snapshots:
            if isinstance(s, MarketSnapshot):
                lines.extend(b.line for b in s.books if b.line is not None)
            elif isinstance(s, (int, float)):
                lines.append(float(s))
            else:
                continue
    else:
        return None

    lines = [float(x) for x in lines]
    if not lines:
        return None
    if method == "mean":
        return round(statistics.fmean(lines), 3)
    return round(statistics.median(lines), 3)


def find_best_price(
    over_snap: Optional[MarketSnapshot],
    under_snap: Optional[MarketSnapshot] = None,
) -> dict:
    """Best (highest American) price per side, plus which book offers it.

    With two snapshots returns ``{"over": {...}, "under": {...}}``; with a
    single snapshot returns the one-side dict ``{"price", "bookmaker", "line"}``.
    """

    def _best(snap: Optional[MarketSnapshot]) -> dict:
        if snap is None:
            return {"price": None, "bookmaker": "", "line": None}
        best_price: Optional[int] = None
        best_book = ""
        best_line: Optional[float] = None
        for b in snap.books:
            if b.price is not None and (best_price is None or b.price > best_price):
                best_price = b.price
                best_book = b.bookmaker
                best_line = b.line
        return {"price": best_price, "bookmaker": best_book, "line": best_line}

    if under_snap is not None:
        return {"over": _best(over_snap), "under": _best(under_snap)}
    return _best(over_snap)


# ══════════════════════════════════════════════════════════════
#  Formatting (UI-ready dicts)
# ══════════════════════════════════════════════════════════════

def _book_view(b: BookmakerLine) -> dict:
    return {
        "bookmaker": b.bookmaker,
        "line": b.line,
        "price": b.price,
        "implied_probability": (
            round(implied_probability(b.price), 4) if b.price is not None else None
        ),
        "opening_line": b.opening_line,
        "opening_price": b.opening_price,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def _market_view(key: str, snap: MarketSnapshot) -> dict:
    books = sorted(snap.books, key=lambda b: bookmaker_rank(b.bookmaker))
    return {
        "key": key,
        "market": GAME_MARKET_KEYS.get(key, {}).get("market", snap.identity.market_type.value),
        "selection": GAME_MARKET_KEYS.get(key, {}).get("selection", snap.identity.selection),
        "line": snap.identity.line,
        "consensus_line": snap.consensus_line if snap.consensus_line is not None
                          else compute_consensus(snap),
        "fair_odds_line": snap.fair_odds_line,
        "best": find_best_price(snap),
        "book_count": len(books),
        "books": [_book_view(b) for b in books],
    }


def _prop_market_view(over_snap: Optional[MarketSnapshot],
                      under_snap: Optional[MarketSnapshot],
                      player_id: str, market: str) -> dict:
    over_books = sorted(over_snap.books, key=lambda b: bookmaker_rank(b.bookmaker)) if over_snap else []
    under_books = sorted(under_snap.books, key=lambda b: bookmaker_rank(b.bookmaker)) if under_snap else []
    line = None
    if over_snap and over_snap.identity.line is not None:
        line = over_snap.identity.line
    elif under_snap and under_snap.identity.line is not None:
        line = under_snap.identity.line
    return {
        "player_id": player_id,
        "market": market,
        "line": line,
        "over": {
            "best": find_best_price(over_snap),
            "consensus_line": compute_consensus(over_snap) if over_snap else None,
            "book_count": len(over_books),
            "books": [_book_view(b) for b in over_books],
        },
        "under": {
            "best": find_best_price(under_snap),
            "consensus_line": compute_consensus(under_snap) if under_snap else None,
            "book_count": len(under_books),
            "books": [_book_view(b) for b in under_books],
        },
    }


def compare_odds(
    event_id: str,
    odds=None,
    props=None,
    snapshots: Optional[dict[str, MarketSnapshot]] = None,
) -> dict:
    """Side-by-side bookmaker comparison for every market in an event.

    Accepts either pre-built snapshots (from :func:`track_market`) or raw SGO
    ``odds``/``props`` payloads which are converted internally.
    """
    if snapshots is None:
        snapshots = track_market(event_id, odds=odds, props=props)

    markets = []
    for key, snap in snapshots.items():
        if key in GAME_MARKET_KEYS:
            markets.append(_market_view(key, snap))

    # Group prop snapshots into over/under pairs
    prop_groups: dict[tuple[str, str], dict] = {}
    for key, snap in snapshots.items():
        if not key.startswith("prop:"):
            continue
        _, pid, market, side = key.split(":", 3)
        group = prop_groups.setdefault((pid, market), {"over": None, "under": None})
        group[side] = snap

    player_props = [
        _prop_market_view(g["over"], g["under"], pid, market)
        for (pid, market), g in sorted(prop_groups.items())
    ]

    return {
        "event_id": event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bookmakers": _bookmakers_present(snapshots),
        "markets": markets,
        "player_props": player_props,
    }


def _bookmakers_present(snapshots: dict[str, MarketSnapshot]) -> list[str]:
    seen = set()
    for snap in snapshots.values():
        for b in snap.books:
            if b.bookmaker:
                seen.add(b.bookmaker)
    return sorted(seen, key=bookmaker_rank)


def format_comparison(
    event_id: str,
    odds=None,
    props=None,
    snapshots: Optional[dict[str, MarketSnapshot]] = None,
) -> dict:
    """Structured comparison dict for UI display (convenience alias)."""
    return compare_odds(event_id, odds=odds, props=props, snapshots=snapshots)
