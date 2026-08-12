"""
SB ME Live Odds Tracker — real-time market movement backend.

Builds :class:`MarketSnapshot` objects from SGO event-level odds and player
props, detects line/price/steam/reversal movements between two snapshots, and
formats a tracker view (moneyline, spread, total, player props) for the UI.

Pure functions (``track_market``, ``detect_movements``, ``format_live_markets``)
operate on already-fetched data so they are deterministic and testable without
network access. ``get_live_markets`` is the async entry point that wires the
shared :class:`MarketCache` into the pipeline.

Field extraction is defensive: it tolerates snake_case, camelCase and the
SGO v2 initialism casing (``eventID``, ``overPrice`` …) and falls back
gracefully when a book/field is missing. Nothing here fabricates odds — every
``BookmakerLine`` maps to a value present in the source payload.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from market_engine import *  # noqa: F401,F403  (foundation namespace per spec)
from market_engine import (
    BookmakerLine,
    LineMovement,
    MarketIdentity,
    MarketSnapshot,
    MarketType,
    MovementType,
    bookmaker_rank,
    detect_movement,
    normalize_bookmaker,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  Field extraction helpers (defensive against schema variance)
# ══════════════════════════════════════════════════════════════

def _pick(obj: dict, *keys: str):
    """Return the first non-None value among candidate keys."""
    if not isinstance(obj, dict):
        return None
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v) -> Optional[int]:
    f = _to_float(v)
    if f is None:
        return None
    return int(round(f))


def _iso(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _book_name(b: dict) -> str:
    raw = _pick(
        b,
        "bookmaker", "book", "sportsbook", "sportsbookName", "bookName",
        "provider", "name",
    )
    return normalize_bookmaker(str(raw)) if raw else ""


def _as_book_list(odds) -> list:
    """Normalize the odds payload's book container into a list of book dicts."""
    if odds is None:
        return []
    if isinstance(odds, list):
        return [o for o in odds if isinstance(o, dict)]
    if isinstance(odds, dict):
        books = _pick(odds, "books", "bookmakers", "data", "lines", "bookmakerLines")
        if isinstance(books, list):
            return [o for o in books if isinstance(o, dict)]
        if isinstance(books, dict):
            return [books]
        # A single book object with no container wrapper.
        if _pick(odds, "bookmaker", "book") or _pick(
            odds, "moneylineHome", "spread", "total"
        ):
            return [odds]
    return []


# ══════════════════════════════════════════════════════════════
#  Game market snapshot builder
# ══════════════════════════════════════════════════════════════

def _game_snapshot(
    event_id: str,
    market_type: MarketType,
    selection: str,
    books: list[BookmakerLine],
    consensus_line: Optional[float] = None,
    fair_line: Optional[float] = None,
) -> MarketSnapshot:
    snap = MarketSnapshot(
        identity=MarketIdentity(
            event_id=event_id,
            market_type=market_type,
            selection=selection,
            line=(consensus_line if consensus_line is not None else
                  (books[0].line if books and books[0].line is not None else None)),
        ),
        books=books,
        consensus_line=consensus_line,
        fair_odds_line=fair_line,
    )
    return snap


def _build_game_snapshots(
    event_id: str, odds, consensus: Optional[dict] = None, fair: Optional[dict] = None
) -> dict[str, MarketSnapshot]:
    """Build moneyline/spread/total snapshots from SGO odds + consensus + fair."""
    snapshots: dict[str, MarketSnapshot] = {}
    books_raw = _as_book_list(odds)

    ml_home: list[BookmakerLine] = []
    ml_away: list[BookmakerLine] = []
    spread_home: list[BookmakerLine] = []
    spread_away: list[BookmakerLine] = []
    total_over: list[BookmakerLine] = []
    total_under: list[BookmakerLine] = []

    for b in books_raw:
        book = _book_name(b) or "unknown"
        updated = _iso(_pick(b, "updatedAt", "updated_at", "timestamp"))

        # ── Moneyline ──
        mh = _to_int(_pick(b, "moneylineHome", "homeMoneyline", "moneyline_home"))
        ma = _to_int(_pick(b, "moneylineAway", "awayMoneyline", "moneyline_away"))
        if mh is not None:
            ml_home.append(BookmakerLine(
                bookmaker=book,
                price=mh,
                opening_price=_to_int(_pick(b, "openingMoneylineHome", "opening_home_moneyline")),
                updated_at=updated,
            ))
        if ma is not None:
            ml_away.append(BookmakerLine(
                bookmaker=book,
                price=ma,
                opening_price=_to_int(_pick(b, "openingMoneylineAway", "opening_away_moneyline")),
                updated_at=updated,
            ))

        # ── Spread ──
        sp_home = _to_float(_pick(
            b, "spread", "pointSpread", "spreadHome", "spread_home", "spreadHomeLine"
        ))
        sp_away = _to_float(_pick(b, "spreadAway", "spread_away"))
        if sp_home is None and sp_away is not None:
            sp_home = -sp_away
        if sp_home is not None and sp_away is None:
            sp_away = -sp_home
        if sp_home is not None:
            spread_home.append(BookmakerLine(
                bookmaker=book,
                line=sp_home,
                price=_to_int(_pick(b, "spreadHomePrice", "spread_home_price",
                                    "spreadHomeOdds", "spreadPriceHome")),
                opening_line=_to_float(_pick(b, "openingSpread", "opening_spread",
                                             "openingPointSpread")),
                updated_at=updated,
            ))
        if sp_away is not None:
            spread_away.append(BookmakerLine(
                bookmaker=book,
                line=sp_away,
                price=_to_int(_pick(b, "spreadAwayPrice", "spread_away_price",
                                    "spreadAwayOdds", "spreadPriceAway")),
                opening_line=_to_float(_pick(b, "openingSpreadAway", "opening_spread_away")),
                updated_at=updated,
            ))

        # ── Total ──
        total = _to_float(_pick(
            b, "total", "totalLine", "overUnder", "overUnderLine", "totalOver"
        ))
        over_line = _to_float(_pick(b, "totalOver", "totalOverLine", "overLine")) or total
        under_line = _to_float(_pick(b, "totalUnder", "totalUnderLine", "underLine")) or total
        if over_line is not None:
            total_over.append(BookmakerLine(
                bookmaker=book,
                line=over_line,
                price=_to_int(_pick(b, "totalOverPrice", "overPrice", "overOdds",
                                    "totalOverOdds", "totalOverJuice")),
                opening_line=_to_float(_pick(b, "openingTotal", "opening_total",
                                             "openingTotalOver", "openingOver")),
                updated_at=updated,
            ))
        if under_line is not None:
            total_under.append(BookmakerLine(
                bookmaker=book,
                line=under_line,
                price=_to_int(_pick(b, "totalUnderPrice", "underPrice", "underOdds",
                                    "totalUnderOdds", "totalUnderJuice")),
                opening_line=_to_float(_pick(b, "openingTotal", "opening_total",
                                             "openingTotalUnder", "openingUnder")),
                updated_at=updated,
            ))

    # Consensus / fair values (book-level only if present in those payloads)
    consensus = consensus or {}
    fair = fair or {}

    def _consensus_total():
        if isinstance(consensus, dict):
            return _to_float(_pick(consensus, "total", "totalOver", "totalLine", "overUnder"))
        return None

    def _consensus_spread():
        if isinstance(consensus, dict):
            return _to_float(_pick(consensus, "spread", "pointSpread", "spreadHome"))
        return None

    def _fair_total():
        if isinstance(fair, dict):
            return _to_float(_pick(fair, "total", "fairTotal", "totalLine"))
        return None

    for key, books, mtype, selection, cons, fair_val in (
        ("moneyline_home", ml_home, MarketType.MONEYLINE, "home", None, None),
        ("moneyline_away", ml_away, MarketType.MONEYLINE, "away", None, None),
        ("spread_home", spread_home, MarketType.SPREAD, "home",
         _consensus_spread(), None),
        ("spread_away", spread_away, MarketType.SPREAD, "away",
         _consensus_spread(), None),
        ("total_over", total_over, MarketType.TOTAL, "over",
         _consensus_total(), _fair_total()),
        ("total_under", total_under, MarketType.TOTAL, "under",
         _consensus_total(), _fair_total()),
    ):
        if books:
            books.sort(key=lambda bl: bookmaker_rank(bl.bookmaker))
            snapshots[key] = _game_snapshot(
                event_id, mtype, selection, books,
                consensus_line=cons, fair_line=fair_val,
            )

    return snapshots


# ══════════════════════════════════════════════════════════════
#  Player prop snapshot builder
# ══════════════════════════════════════════════════════════════

def _iter_prop_rows(props):
    """Yield normalized (player_id, name, market, line, book, over, under, opening).

    Accepts either SGO v2 player-prop entries (player object + markets list) or
    flat market rows, plus an optional ``{"data": [...]}`` wrapper.
    """
    if props is None:
        return
    if isinstance(props, dict):
        props = _pick(props, "data", "props", "markets", "players", "playerProps")
    if not isinstance(props, list):
        return

    for entry in props:
        if not isinstance(entry, dict):
            continue

        # Player resolution (nested player object vs flat fields)
        player = entry.get("player") or entry.get("playerInfo")
        if isinstance(player, dict):
            pid = _pick(player, "playerID", "id", "playerId") or ""
            names = player.get("names", {})
            pname = (
                (names.get("display") or names.get("long") or names.get("full")
                 or names.get("name")) if isinstance(names, dict)
                else _pick(player, "name", "fullName", "playerName") or ""
            )
        else:
            pid = _pick(entry, "playerID", "playerId", "player_id") or ""
            pname = _pick(entry, "playerName", "name", "fullName") or ""

        # Market resolution
        markets = entry.get("markets", entry.get("market"))
        if isinstance(markets, dict):
            markets = [markets]
        elif markets is None and _pick(entry, "line", "value", "market", "name"):
            markets = [entry]
        if not isinstance(markets, list):
            continue

        for mkt in markets:
            if not isinstance(mkt, dict):
                continue
            market = _pick(mkt, "market", "marketName", "name", "stat", "type", "prop")
            line = _to_float(_pick(mkt, "line", "value", "lineValue", "total"))
            if market is None or line is None:
                continue
            book = _book_name(mkt) or _book_name(entry)
            yield (
                str(pid or ""),
                str(pname or ""),
                str(market),
                line,
                book or "unknown",
                _to_int(_pick(mkt, "overPrice", "over", "overOdds", "overJuice")),
                _to_int(_pick(mkt, "underPrice", "under", "underOdds", "underJuice")),
                _to_float(_pick(mkt, "openingLine", "opening_line", "opening")),
            )


def _build_prop_snapshots(event_id: str, props) -> dict[str, MarketSnapshot]:
    """Build per-player, per-market, per-side snapshots from raw prop rows."""
    snapshots: dict[str, MarketSnapshot] = {}
    over_rows: dict[tuple, list[BookmakerLine]] = {}
    under_rows: dict[tuple, list[BookmakerLine]] = {}

    for pid, pname, market, line, book, over, under, opening in _iter_prop_rows(props):
        key = (pid, market)
        over_rows.setdefault(key, []).append(BookmakerLine(
            bookmaker=book, line=line, price=over,
            opening_line=opening, updated_at=None,
        ))
        under_rows.setdefault(key, []).append(BookmakerLine(
            bookmaker=book, line=line, price=under,
            opening_line=opening, updated_at=None,
        ))

    for (pid, market), rows in over_rows.items():
        rows.sort(key=lambda bl: bookmaker_rank(bl.bookmaker))
        snapshots[f"prop:{pid}:{market}:over"] = MarketSnapshot(
            identity=MarketIdentity(
                event_id=event_id, market_type=MarketType.PLAYER_PROP,
                player_id=pid, stat_id=market, selection="over",
                line=(rows[0].line if rows else None),
            ),
            books=rows,
        )
    for (pid, market), rows in under_rows.items():
        rows.sort(key=lambda bl: bookmaker_rank(bl.bookmaker))
        snapshots[f"prop:{pid}:{market}:under"] = MarketSnapshot(
            identity=MarketIdentity(
                event_id=event_id, market_type=MarketType.PLAYER_PROP,
                player_id=pid, stat_id=market, selection="under",
                line=(rows[0].line if rows else None),
            ),
            books=rows,
        )

    return snapshots


# ══════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════

def track_market(
    event_id: str,
    odds=None,
    props=None,
    consensus: Optional[dict] = None,
    fair_odds: Optional[dict] = None,
) -> dict[str, MarketSnapshot]:
    """Build a full set of :class:`MarketSnapshot` objects for an event.

    Returns a dict keyed by market key:
      - ``moneyline_home`` / ``moneyline_away``
      - ``spread_home``   / ``spread_away``
      - ``total_over``    / ``total_under``
      - ``prop:{player_id}:{market}:{over|under}`` for every player prop
    """
    snapshots = _build_game_snapshots(event_id, odds, consensus, fair_odds)
    snapshots.update(_build_prop_snapshots(event_id, props))
    return snapshots


def detect_movements(
    prev: dict[str, MarketSnapshot],
    curr: dict[str, MarketSnapshot],
    history: Optional[dict[str, LineMovement]] = None,
) -> list[LineMovement]:
    """Compare two snapshot dicts and return detected :class:`LineMovement` objects.

    Movement classification:
      * ``LINE_MOVE``  — line changed, price unchanged
      * ``PRICE_MOVE`` — price changed, line unchanged
      * ``STEAM_MOVE`` — line + price changed together, OR >=2 books moved the
        line the same direction on the same market
      * ``REVERSAL``   — line moved opposite to its prior direction (vs opening
        line or a previously recorded movement)
    """
    movements: list[LineMovement] = []
    history = history or {}

    for key in prev:
        if key not in curr:
            continue
        ps, cs = prev[key], curr[key]
        prev_books = {b.bookmaker: b for b in ps.books}
        curr_books = {b.bookmaker: b for b in cs.books}

        # Steam detection: >=2 books moving the line the same direction.
        up = [b for b in prev_books if
              (lambda p, c: c and p.line is not None and c.line is not None
               and c.line - p.line > 0.01)(prev_books[b], curr_books.get(b))]
        down = [b for b in prev_books if
                (lambda p, c: c and p.line is not None and c.line is not None
                 and c.line - p.line < -0.01)(prev_books[b], curr_books.get(b))]
        steam_books = set()
        if len(up) >= 2:
            steam_books.update(up)
        if len(down) >= 2:
            steam_books.update(down)

        for book, pb in prev_books.items():
            cb = curr_books.get(book)
            if cb is None:
                continue
            mtype = detect_movement(pb, cb)
            if mtype == MovementType.NO_CHANGE:
                continue

            # Reversal: current line direction opposes prior direction.
            if mtype in (MovementType.LINE_MOVE, MovementType.STEAM_MOVE):
                prior_dir = None
                if pb.opening_line is not None and pb.line is not None:
                    prior_dir = pb.line - pb.opening_line
                elif key in history:
                    prior_dir = history[key].movement_amount
                if prior_dir and pb.line is not None and cb.line is not None:
                    curr_dir = cb.line - pb.line
                    if prior_dir != 0 and curr_dir != 0 and (prior_dir * curr_dir) < 0:
                        mtype = MovementType.REVERSAL

            # Upgrade to steam when the book joined a multi-book move.
            if book in steam_books and mtype in (MovementType.LINE_MOVE, MovementType.PRICE_MOVE):
                mtype = MovementType.STEAM_MOVE

            amount = 0.0
            if pb.line is not None and cb.line is not None:
                amount = round(cb.line - pb.line, 3)

            movements.append(LineMovement(
                event_id=cs.identity.event_id or key,
                market_identity=cs.identity,
                bookmaker=book,
                movement_type=mtype,
                previous_line=pb.line,
                current_line=cb.line,
                previous_price=pb.price,
                current_price=cb.price,
                movement_amount=amount,
            ))

    return movements


# ══════════════════════════════════════════════════════════════
#  Formatting (UI-ready dicts)
# ══════════════════════════════════════════════════════════════

def _snapshot_view(snap: MarketSnapshot) -> dict:
    """Format a single snapshot into a compact tracker view."""
    books = []
    for b in snap.books:
        books.append({
            "bookmaker": b.bookmaker,
            "line": b.line,
            "price": b.price,
            "opening_line": b.opening_line,
            "opening_price": b.opening_price,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        })
    return {
        "market_type": snap.identity.market_type.value,
        "selection": snap.identity.selection,
        "line": snap.identity.line,
        "consensus_line": snap.consensus_line,
        "fair_odds_line": snap.fair_odds_line,
        "book_count": len(snap.books),
        "books": books,
    }


def _best_price(snap: MarketSnapshot) -> dict:
    """Best (highest American) price among books for this side."""
    best_price: Optional[int] = None
    best_book = ""
    best_line: Optional[float] = None
    for b in snap.books:
        if b.price is not None and (best_price is None or b.price > best_price):
            best_price = b.price
            best_book = b.bookmaker
            best_line = b.line
    if best_price is None:
        return {"price": None, "bookmaker": "", "line": None}
    return {"price": best_price, "bookmaker": best_book, "line": best_line}


def format_live_markets(
    event_id: str,
    snapshots: dict[str, MarketSnapshot],
    movements: Optional[list[LineMovement]] = None,
) -> dict:
    """Format tracker data (moneyline, spread, total, player props) for the UI."""
    movements = movements or []

    def side(key):
        snap = snapshots.get(key)
        if snap is None:
            return None
        return {"best": _best_price(snap), **_snapshot_view(snap)}

    # Group prop snapshots by (player, market)
    prop_map: dict[str, dict] = {}
    for key, snap in snapshots.items():
        if not key.startswith("prop:"):
            continue
        _, pid, market, side_name = key.split(":", 3)
        entry = prop_map.setdefault(
            f"{pid}:{market}",
            {"player_id": pid, "market": market, "over": None, "under": None},
        )
        entry[side_name] = {"best": _best_price(snap), **_snapshot_view(snap)}

    player_props = []
    for entry in prop_map.values():
        over = entry["over"]
        under = entry["under"]
        player_props.append({
            "player_id": entry["player_id"],
            "market": entry["market"],
            "line": (over or under or {}).get("line"),
            "over": over,
            "under": under,
        })

    return {
        "event_id": event_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "markets": {
            "moneyline": {"home": side("moneyline_home"), "away": side("moneyline_away")},
            "spread": {"home": side("spread_home"), "away": side("spread_away")},
            "total": {"over": side("total_over"), "under": side("total_under")},
        },
        "player_props": player_props,
        "movements": [_movement_view(m) for m in movements],
    }


def _movement_view(m: LineMovement) -> dict:
    return {
        "market_type": m.market_identity.market_type.value,
        "player_id": m.market_identity.player_id,
        "stat_id": m.market_identity.stat_id,
        "selection": m.market_identity.selection,
        "bookmaker": m.bookmaker,
        "movement_type": m.movement_type.value,
        "previous_line": m.previous_line,
        "current_line": m.current_line,
        "previous_price": m.previous_price,
        "current_price": m.current_price,
        "movement_amount": m.movement_amount,
        "detected_at": m.detected_at.isoformat(),
    }


# ══════════════════════════════════════════════════════════════
#  Async entry point (shared cache → snapshots → formatted view)
# ══════════════════════════════════════════════════════════════

async def get_live_markets(
    event_id: str,
    cache=None,
    prev_snapshots: Optional[dict[str, MarketSnapshot]] = None,
) -> dict:
    """Fetch event data through the shared cache and return a live tracker view.

    ``cache`` may be a :class:`MarketCache` (optionally already entered) or an
    :class:`SGOIntegration`; if omitted a fresh :class:`MarketCache` is used.
    """
    from market_engine.cache import MarketCache

    own_cache = cache is None
    if cache is None:
        cache = MarketCache()
        await cache.__aenter__()

    try:
        data = await cache.get_event_data(event_id)
        snapshots = track_market(
            event_id,
            odds=data.get("odds"),
            props=data.get("props"),
            consensus=data.get("consensus"),
            fair_odds=data.get("fair_odds"),
        )
        movements = detect_movements(prev_snapshots, snapshots) if prev_snapshots else []
        return format_live_markets(event_id, snapshots, movements=movements)
    finally:
        if own_cache:
            await cache.__aexit__(None, None, None)
