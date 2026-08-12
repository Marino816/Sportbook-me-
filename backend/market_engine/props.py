"""
SB ME Player Props Analyzer — cross-book prop aggregation and DFS-matching.

For every player prop market (hits, homeRuns, strikeouts, fantasyScore, etc.)
this module aggregates all available books to compute:

  • BOOK_COUNT          — how many sportsbooks offer the prop
  • CONSENSUS_LINE      — median line across books
  • BEST_OVER_PRICE      — highest +American over price
  • BEST_UNDER_PRICE     — highest +American under price
  • LINE_RANGE           — [min, max] line across books
  • MARKET_DIRECTION     — line movement direction (UP / DOWN / STEADY)

It also compares the ``fantasyScore`` market line to the DFS projection
(SportsDataIO), producing an edge signal, and returns a structured
``props_intelligence_card`` suitable for UI display.

Market names are normalised sport‑aware via ``intelligence.sports`` with a
graceful local fallback. Nothing here fabricates odds — every line, price, and
count comes directly from the SGO v2 payload.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

from market_engine import *  # noqa: F401,F403  (foundation namespace per spec)
from market_engine import bookmaker_rank, implied_probability
from market_engine.live_odds import _iter_prop_rows  # shared SGO→row iterator

logger = logging.getLogger(__name__)

# ── Sport-aware market resolution (try intelligence.sports, fall back) ──
try:
    from intelligence.sports import resolve_market as _resolve_market
    from intelligence.sports import get_sport_markets as _get_sport_markets
except ImportError:
    # Inline minimal fallback.
    _FALLBACK_ALIASES = {
        "fantasyScore": "fantasyScore", "fantasy_points": "fantasyScore",
        "hits": "hits", "totalHits": "hits", "homeRuns": "homeRuns",
        "home_runs": "homeRuns", "hr": "homeRuns", "rbi": "rbi",
        "runsBattedIn": "rbi", "totalBases": "totalBases",
        "stolenBases": "stolenBases", "sb": "stolenBases",
        "battingStrikeouts": "battingStrikeouts", "walks": "walks",
        "pitchingStrikeouts": "pitchingStrikeouts",
        "strikeouts": "pitchingStrikeouts", "pitchingOuts": "pitchingOuts",
        "pitchingEarnedRuns": "pitchingEarnedRuns",
        "passingYards": "passingYards", "rushingYards": "rushingYards",
        "receivingYards": "receivingYards", "receptions": "receptions",
        "passingTouchdowns": "passingTouchdowns",
        "rushingTouchdowns": "rushingTouchdowns",
        "receivingTouchdowns": "receivingTouchdowns",
        "points": "points", "rebounds": "rebounds", "assists": "assists",
        "threePointersMade": "threePointersMade",
        "pointsReboundsAssists": "pointsReboundsAssists",
        "pra": "pointsReboundsAssists", "blocks": "blocks", "steals": "steals",
        "goals": "goals", "shotsOnGoal": "shotsOnGoal",
        "goalieSaves": "goalieSaves",
    }

    def _resolve_market(raw_name: str) -> Optional[str]:
        key = str(raw_name).strip()
        if key in _FALLBACK_ALIASES:
            return _FALLBACK_ALIASES[key]
        lk = key.lower().replace(" ", "").replace("_", "")
        for alias, norm in _FALLBACK_ALIASES.items():
            if alias.lower().replace(" ", "").replace("_", "") == lk:
                return norm
        return None

    def _get_sport_markets(sport: str) -> dict:
        return {}


# ══════════════════════════════════════════════════════════════
#  Per-player prop aggregation
# ══════════════════════════════════════════════════════════════

def analyze_player_props(
    props,
    player_id: Optional[str] = None,
    sport: str = "MLB",
) -> dict[str, dict]:
    """Aggregate every prop market for a player (or all players) across books.

    Parameters
    ----------
    props : list | dict
        Raw SGO player-props payload (or a list of ``NormalizedPlayerProp`` /
        flat market rows).  The shared ``_iter_prop_rows`` iterator handles the
        SGO v2 structure (nested ``player`` → ``markets`` and flat variants).
    player_id : str, optional
        Filter to a specific player.  If ``None``, all players are aggregated
        into a ``{player_id: {market: ...}}`` top-level dict.
    sport : str
        Sport code passed to ``resolve_market`` for market-name normalisation.

    Returns
    -------
    dict
        When ``player_id`` is supplied::

            {market: {
                "book_count": int,
                "consensus_line": float | None,
                "best_over_price": {"price": int, "bookmaker": str},
                "best_under_price": {"price": int, "bookmaker": str},
                "line_range": [min, max] | None,
                "market_direction": "UP" | "DOWN" | "STEADY" | None,
                "books": [...],
            }}

        When ``player_id`` is ``None`` the top key is ``player_id`` and each
        value is the per-market dict above.
    """
    if player_id:
        players: dict[str, dict] = {player_id: {}}
    else:
        players: dict[str, dict] = {}

    # Collect raw rows keyed by (player_id, normalized_market)
    rows: dict[tuple[str, str], list[dict]] = {}
    for pid, pname, market_raw, line, book, over, under, opening in _iter_prop_rows(props):
        mkt = _resolve_market(market_raw) or market_raw.lower()
        if player_id and pid != player_id:
            continue
        key = (pid, mkt)
        rows.setdefault(key, []).append({
            "book": book, "line": line, "over": over, "under": under,
            "opening": opening,
        })

    # Aggregate per (player, market)
    for (pid, mkt), entries in rows.items():
        if pid not in players:
            players[pid] = {}

        lines = [e["line"] for e in entries]
        over_prices = [(e["over"], e["book"]) for e in entries if e["over"] is not None]
        under_prices = [(e["under"], e["book"]) for e in entries if e["under"] is not None]
        openings = [e["opening"] for e in entries if e["opening"] is not None]

        # Consensus line (median)
        consensus = round(statistics.median(lines), 3) if lines else None

        # Best prices (highest American)
        best_over = max(over_prices, key=lambda x: x[0]) if over_prices else None
        best_under = max(under_prices, key=lambda x: x[0]) if under_prices else None

        # Line range
        line_range = [min(lines), max(lines)] if len(lines) >= 2 else None

        # Market direction (current consensus vs opening consensus)
        op_consensus = round(statistics.median(openings), 3) if openings else None
        direction = _direction(consensus, op_consensus)

        # Sort books by rank
        sorted_entries = sorted(entries, key=lambda e: bookmaker_rank(e["book"]))

        players[pid][mkt] = {
            "book_count": len(entries),
            "consensus_line": consensus,
            "best_over_price": (
                {"price": best_over[0], "bookmaker": best_over[1]}
                if best_over else {"price": None, "bookmaker": ""}
            ),
            "best_under_price": (
                {"price": best_under[0], "bookmaker": best_under[1]}
                if best_under else {"price": None, "bookmaker": ""}
            ),
            "line_range": line_range,
            "market_direction": direction,
            "opening_consensus_line": op_consensus,
            "books": [
                {
                    "bookmaker": e["book"],
                    "line": e["line"],
                    "over_price": e["over"],
                    "under_price": e["under"],
                    "opening_line": e["opening"],
                }
                for e in sorted_entries
            ],
        }

    if player_id:
        return players[player_id]
    return players


def _direction(current: Optional[float], opening: Optional[float],
               threshold: float = 0.5) -> Optional[str]:
    """Classify line movement direction."""
    if current is None or opening is None:
        return None
    delta = current - opening
    if abs(delta) < threshold:
        return "STEADY"
    return "UP" if delta > 0 else "DOWN"


# ══════════════════════════════════════════════════════════════
#  DFS projection comparison
# ══════════════════════════════════════════════════════════════

def build_dfs_projection(
    player_id: str,
    projection: float,
    market_line: Optional[float] = None,
    market_over_price: Optional[int] = None,
    market_under_price: Optional[int] = None,
    market_book: str = "",
) -> dict:
    """Compare a DFS projection (SportsDataIO / native) to the SGO market line.

    Returns a dict with ``edge`` (projection – line), ``edge_score`` (edge /
    |line| * 100), and the implied probabilities / directional signal.
    """
    result = {
        "player_id": player_id,
        "projection": round(projection, 1),
        "market_line": market_line,
        "market_over_price": market_over_price,
        "market_under_price": market_under_price,
        "market_book": market_book,
        "edge": None,
        "edge_score": None,
        "projection_vs_consensus": None,
        "signal": "NEUTRAL",
    }

    if market_line is not None and market_line > 0:
        edge = round(projection - market_line, 2)
        edge_score = round(edge / abs(market_line) * 100, 1)
        result["edge"] = edge
        result["edge_score"] = edge_score

        if abs(edge) < 0.5:
            result["signal"] = "NEUTRAL"
            result["projection_vs_consensus"] = "IN_LINE"
        elif edge > 3.0:
            result["signal"] = "STRONG_OVER"
            result["projection_vs_consensus"] = "ABOVE"
        elif edge > 0.5:
            result["signal"] = "OVER"
            result["projection_vs_consensus"] = "ABOVE"
        elif edge < -3.0:
            result["signal"] = "STRONG_UNDER"
            result["projection_vs_consensus"] = "BELOW"
        else:
            result["signal"] = "UNDER"
            result["projection_vs_consensus"] = "BELOW"

    if market_over_price is not None:
        result["over_implied_probability"] = round(
            implied_probability(market_over_price), 4
        )
    if market_under_price is not None:
        result["under_implied_probability"] = round(
            implied_probability(market_under_price), 4
        )

    return result


# ══════════════════════════════════════════════════════════════
#  Intelligence card (UI-ready)
# ══════════════════════════════════════════════════════════════

def props_intelligence_card(
    player_id: str = "",
    player_name: str = "",
    team: str = "",
    position: str = "",
    opponent: str = "",
    props_analysis: Optional[dict[str, dict]] = None,
    projection: Optional[dict] = None,
    game_total: Optional[float] = None,
    sport: str = "MLB",
) -> dict:
    """Return a structured player-intelligence card for UI consumption.

    Combines the per-market prop aggregation from :func:`analyze_player_props`
    with the DFS projection comparison from :func:`build_dfs_projection` and
    the game-total environment signal.

    Parameters
    ----------
    player_id, player_name, team, position, opponent : str
        Player identity fields.
    props_analysis : dict | None
        Dict keyed by normalized market name, as produced by
        :func:`analyze_player_props`.
    projection : dict | None
        Dict as produced by :func:`build_dfs_projection`.  If *None* but a
        ``fantasyScore`` key exists in *props_analysis*, a minimal projection
        comparison is built using the consensus line as the market line.
    game_total : float | None
        Game total line (for environment context).
    sport : str
        Sport code, used to list *expected* prop markets that are not found.

    Returns
    -------
    dict   A JSON-friendly card ready to drive a front-end component.
    """
    props_analysis = props_analysis or {}

    # Build projection edge from props_analysis if not provided explicitly
    proj = projection
    if proj is None:
        fs = props_analysis.get("fantasyScore")
        if fs:
            proj_line = fs.get("consensus_line")
            best_over = fs.get("best_over_price") or {}
            best_under = fs.get("best_under_price") or {}
            proj = build_dfs_projection(
                player_id, 0,
                market_line=proj_line,
                market_over_price=best_over.get("price"),
                market_under_price=best_under.get("price"),
                market_book=best_over.get("bookmaker") or best_under.get("bookmaker") or "",
            )
            # Clear NaN projection — keep market values only
            proj["projection"] = None
            proj["edge"] = None
            proj["edge_score"] = None
            proj["signal"] = "NEUTRAL"

    # Environment from game total
    env = _environment_flag(game_total)

    # Expected props for this sport (not found → list as missing)
    sport_cfg = _get_sport_markets(sport)
    all_expected = set()
    for category in ("hitting", "pitching", "offense", "goalie", "defense", "special_teams"):
        for mkt in sport_cfg.get(category, []):
            all_expected.add(mkt)
    missing = sorted(all_expected - set(props_analysis.keys()))

    # Book diversity
    all_books = set()
    for mkt in props_analysis.values():
        if isinstance(mkt, dict):
            for b in mkt.get("books", []):
                all_books.add(b.get("bookmaker", ""))
    all_books.discard("")

    # Primary props card fields
    card: dict = {
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "position": position,
        "opponent": opponent,
        "sport": sport,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game_total": game_total,
        "game_environment": env,
        "total_bookmakers": len(all_books),
        "bookmaker_list": sorted(all_books, key=bookmaker_rank),
        "prop_count": len(props_analysis),
        "props": props_analysis,
        "missing_props": missing,
        "projection": proj,
    }

    return card


def _environment_flag(total: Optional[float]) -> str:
    if total is None:
        return "NEUTRAL"
    if total > 9.0:
        return "HIGH"
    if total > 8.0:
        return "ABOVE_AVERAGE"
    if total < 6.5:
        return "LOW"
    if total < 7.5:
        return "BELOW_AVERAGE"
    return "NEUTRAL"
