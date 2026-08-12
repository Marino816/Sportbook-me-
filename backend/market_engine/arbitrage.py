"""
SB ME Arbitrage Calculator + Auto Scanner.

Provides:
  - arbitrage_check(): Manual calculator for 2 or 3 American odds
  - stake_calculator(): Optimal proportional stakes for given bankroll
  - scan_arbitrage(): Auto scanner across bookmaker odds for an event

All math performed on decimal odds (not American) internally.
Never compares incompatible lines (e.g. Over 7.5 ≠ Under 8.5).
Results are labeled as mathematical market comparisons, not guaranteed profit.

IMPORTANT: Never expose raw API keys. All SGO calls through cache layer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from market_engine import (
    ArbitrageOpportunity,
    BookmakerLine,
    MarketSnapshot,
    MarketType,
    american_to_decimal,
    check_arbitrage as _base_check_arbitrage,
)
from market_engine.live_odds import track_market

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  Manual Arbitrage Calculator
# ══════════════════════════════════════════════════════════════


def arbitrage_check(
    odds_a: int,
    odds_b: int,
    odds_c: Optional[int] = None,
    event_id: str = "",
    market: str = "",
    outcome_a: str = "",
    book_a: str = "",
    outcome_b: str = "",
    book_b: str = "",
    outcome_c: str = "",
    book_c: str = "",
    bankroll: float = 1000.0,
) -> Optional[ArbitrageOpportunity]:
    """
    Check if a set of American odds presents a mathematical arbitrage opportunity.

    All calculations are performed on decimal odds (converted internally).
    Never calculate directly on American odds.

    For 2-way markets (e.g. moneyline, over/under):
        arb exists when 1/odds_A + 1/odds_B < 1
    For 3-way markets (e.g. soccer moneyline with draw):
        arb exists when 1/A + 1/B + 1/C < 1

    Returns an ArbitrageOpportunity with implied probabilities, stakes,
    gross payout, profit, and ROI, or None if no arb exists.
    """
    # Convert to decimal internally — NEVER calculate on American odds
    dec_a = american_to_decimal(odds_a)
    dec_b = american_to_decimal(odds_b)

    imp_a = 1.0 / dec_a
    imp_b = 1.0 / dec_b
    imp_c = None
    dec_c = None

    if odds_c is not None:
        dec_c = american_to_decimal(odds_c)
        imp_c = 1.0 / dec_c

    combined_imp = imp_a + imp_b
    if imp_c is not None:
        combined_imp += imp_c

    # No arb if combined implied probability >= 1.0
    if combined_imp >= 1.0:
        return None

    # Arb exists — build full result
    arb_pct = round((1.0 - combined_imp) * 100, 2)

    opp = ArbitrageOpportunity(
        event_id=event_id,
        market=market,
        outcome_a=outcome_a,
        book_a=book_a,
        odds_a=odds_a,
        outcome_b=outcome_b,
        book_b=book_b,
        odds_b=odds_b,
        outcome_c=outcome_c if odds_c is not None else None,
        book_c=book_c if odds_c is not None else None,
        odds_c=odds_c,
        implied_total=round(combined_imp, 4),
        arb_percent=arb_pct,
    )

    # Compute derived values
    stakes = opp.stakes(bankroll)
    total_staked = sum(stakes.values())
    gross = opp.gross_payout(bankroll)
    profit = round(gross - total_staked, 2)
    roi = round(profit / total_staked * 100, 2) if total_staked > 0 else 0.0

    return opp


def stake_calculator(
    outcomes: list[dict],
    bankroll: float = 1000.0,
) -> dict:
    """
    Calculate optimal proportional stakes for a set of mutually exclusive outcomes.

    Args:
        outcomes: List of dicts, each with {"name": str, "odds": int (American)}
        bankroll: Total bankroll to allocate

    Returns:
        dict with stakes per outcome, total staked, gross payout, profit, ROI

    Proportional staking formula:
        stake_i = bankroll / (sum(1/odds_j) * odds_i)
    """
    if len(outcomes) < 2:
        return {
            "stakes": {},
            "total_staked": 0.0,
            "gross_payout": 0.0,
            "profit": 0.0,
            "roi": 0.0,
            "error": "Need at least 2 outcomes",
        }

    # Convert all to decimal
    decimals = [american_to_decimal(o["odds"]) for o in outcomes]
    inv_sum = sum(1.0 / d for d in decimals)

    stakes = {}
    total = 0.0
    for i, outcome in enumerate(outcomes):
        stake = round(bankroll / (inv_sum * decimals[i]), 2)
        stakes[outcome["name"]] = stake
        total += stake

    total = round(total, 2)

    # Gross payout = min(stake_i * odds_i) across all outcomes
    payouts = [stakes[outcomes[i]["name"]] * decimals[i] for i in range(len(outcomes))]
    gross = round(min(payouts), 2)
    profit = round(gross - total, 2)
    roi = round(profit / total * 100, 2) if total > 0 else 0.0

    return {
        "stakes": stakes,
        "total_staked": total,
        "gross_payout": gross,
        "profit": profit,
        "roi": roi,
    }


# ══════════════════════════════════════════════════════════════
#  Auto Scanner
# ══════════════════════════════════════════════════════════════


def _pick_best_price(books: list[BookmakerLine]) -> tuple[Optional[int], str, Optional[float]]:
    """Find highest American price among books for a given side."""
    best_price: Optional[int] = None
    best_book = ""
    best_line: Optional[float] = None
    for b in books:
        if b.price is not None and (best_price is None or b.price > best_price):
            best_price = b.price
            best_book = b.bookmaker
            best_line = b.line
    return best_price, best_book, best_line


def scan_arbitrage(
    event_id: str,
    odds=None,
    props=None,
    snapshots: Optional[dict[str, MarketSnapshot]] = None,
) -> list[dict]:
    """
    Scan an event's bookmaker odds for mathematical arbitrage opportunities.

    Scans:
      - Moneyline (2-way: home/away)
      - Moneyline (3-way: home/away/draw — if present)
      - Totals (over/under from different books, same line)

    CRITICAL: NEVER compare incompatible lines.
    Over 7.5 ≠ Under 8.5 → these are NOT comparable.
    Only compare over/under pairs that share the EXACT same line value.

    Results are labeled as mathematical market comparisons, not guaranteed profit.

    Returns a list of dicts, each with:
        event_id, market, outcome_a, book_a, odds_a, line_a,
        outcome_b, book_b, odds_b, line_b, (outcome_c, book_c, odds_c, line_c),
        implied_total, arb_percent, stakes, gross_payout, profit, roi,
        disclaimer: "Mathematical comparison only — not guaranteed profit"
    """
    if snapshots is None:
        snapshots = track_market(event_id, odds=odds, props=props)

    opportunities: list[dict] = []

    # ── 2-Way Moneyline Arb (home / away) ──
    ml_home = snapshots.get("moneyline_home")
    ml_away = snapshots.get("moneyline_away")
    if ml_home and ml_away:
        best_home, book_home, home_line = _pick_best_price(ml_home.books)
        best_away, book_away, away_line = _pick_best_price(ml_away.books)
        if best_home and best_away:
            opp = arbitrage_check(
                odds_a=best_home, odds_b=best_away,
                event_id=event_id, market="moneyline",
                outcome_a="Home", book_a=book_home,
                outcome_b="Away", book_b=book_away,
            )
            if opp:
                opportunities.append(_format_opp(opp, home_line, away_line))

    # ── Totals Arb (over/under — must share exact same line) ──
    total_over = snapshots.get("total_over")
    total_under = snapshots.get("total_under")
    if total_over and total_under:
        # Only compare over/under from different books at THE SAME line value
        # Group over books by line, under books by line
        over_by_line: dict[float, list[BookmakerLine]] = {}
        for b in total_over.books:
            if b.line is not None and b.price is not None:
                over_by_line.setdefault(b.line, []).append(b)

        under_by_line: dict[float, list[BookmakerLine]] = {}
        for b in total_under.books:
            if b.line is not None and b.price is not None:
                under_by_line.setdefault(b.line, []).append(b)

        # Find exact line matches
        for line_val, over_books in over_by_line.items():
            under_books = under_by_line.get(line_val, [])
            if not under_books:
                continue

            best_over_price, best_over_book, _ = _pick_best_price(over_books)
            best_under_price, best_under_book, _ = _pick_best_price(under_books)

            if best_over_price and best_under_price:
                opp = arbitrage_check(
                    odds_a=best_over_price, odds_b=best_under_price,
                    event_id=event_id, market="total",
                    outcome_a=f"Over {line_val}", book_a=best_over_book,
                    outcome_b=f"Under {line_val}", book_b=best_under_book,
                )
                if opp:
                    opportunities.append(_format_opp(opp, line_val, line_val))

    return opportunities


def _format_opp(
    opp: ArbitrageOpportunity,
    line_a: Optional[float] = None,
    line_b: Optional[float] = None,
    line_c: Optional[float] = None,
) -> dict:
    """Format an ArbitrageOpportunity into a UI/API-friendly dict."""
    result = {
        "event_id": opp.event_id,
        "market": opp.market,
        "outcome_a": opp.outcome_a,
        "book_a": opp.book_a,
        "odds_a": opp.odds_a,
        "line_a": line_a,
        "outcome_b": opp.outcome_b,
        "book_b": opp.book_b,
        "odds_b": opp.odds_b,
        "line_b": line_b,
        "outcome_c": opp.outcome_c,
        "book_c": opp.book_c,
        "odds_c": opp.odds_c,
        "line_c": line_c,
        "implied_total": opp.implied_total,
        "arb_percent": opp.arb_percent,
        "stakes": opp.stakes(),
        "gross_payout": opp.gross_payout(),
        "profit": round(opp.gross_payout() - sum(opp.stakes().values()), 2),
        "roi": round((opp.gross_payout() - sum(opp.stakes().values())) / sum(opp.stakes().values()) * 100, 2) if sum(opp.stakes().values()) > 0 else 0.0,
        "disclaimer": "Mathematical comparison only — not guaranteed profit. Verify availability and limits with each sportsbook.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Remove None-valued optional fields from the dict for cleaner output
    if opp.outcome_c is None:
        result.pop("outcome_c", None)
        result.pop("book_c", None)
        result.pop("odds_c", None)
        result.pop("line_c", None)
    return result


def format_arbitrage_response(
    event_id: str,
    opportunities: list[dict],
    league: str = "",
) -> dict:
    """Wrap arbitrage scan results into a structured response."""
    return {
        "event_id": event_id,
        "league": league,
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
        "disclaimer": "All results are mathematical market comparisons. Verify availability, limits, and terms with each sportsbook before placing any wager.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }