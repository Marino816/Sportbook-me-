"""
SB ME Parlay Builder.

Provides:
  - build_parlay(): Calculate parlay odds and payout from ParlayLeg list
  - is_same_game_parlay(): Detect if legs share the same event_id
  - sgp_price_available(): Check if SGO provides SGP pricing

Supports:
  - Cross-game parlays: FULLY SUPPORTED — combined odds computed from decimal product
  - Same-game parlays: Labeled "Same-game parlay pricing unavailable" unless
    SGO provides SGP data (returns False for V1)

All calculations on decimal odds, converted to American for display.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from market_engine import (
    ParlayLeg,
    ParlayResult,
    american_to_decimal,
    calculate_parlay as _base_calculate_parlay,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  Parlay Builder
# ══════════════════════════════════════════════════════════════


def is_same_game_parlay(legs: list[ParlayLeg]) -> bool:
    """
    Detect if any legs share the same event_id.

    A same-game parlay (SGP) has 2+ legs from the same event.
    """
    if len(legs) < 2:
        return False
    event_ids = {leg.event_id for leg in legs}
    return len(event_ids) < len(legs)


def sgp_price_available(event_id: str = "") -> bool:
    """
    Check if SGO provides SGP (same-game parlay) pricing.

    V1: Returns False — SGP pricing not yet available from SGO.
    When SGO adds SGP support, this will check the provider capability.
    """
    # V1: SGO does not provide SGP pricing
    return False


def build_parlay(
    legs: list[ParlayLeg],
    stake: float = 100.0,
) -> ParlayResult:
    """
    Build a parlay from a list of ParlayLeg and calculate combined odds + payout.

    Args:
        legs: List of ParlayLeg (event_id, market, selection, bookmaker, odds)
        stake: Wager amount in dollars (default: 100.0)

    Returns:
        ParlayResult with combined odds, payout, profit, and SGP detection

    Calculation:
        1. Convert each leg's American odds → decimal
        2. Multiply all decimal odds → combined_decimal
        3. Convert combined_decimal → American
        4. Payout = stake × combined_decimal
        5. Profit = payout - stake

    Supports 2, 3, 4, 5+ legs.

    Cross-game parlays: FULLY SUPPORTED
    Same-game parlays: Labeled with sgp_available check
    """
    if not legs:
        # Return empty result
        return ParlayResult(
            legs=[],
            leg_count=0,
            combined_decimal=1.0,
            combined_american=0,
            implied_probability=0.0,
            stake=stake,
            potential_payout=0.0,
            potential_profit=0.0,
            is_same_game=False,
            sgp_available=False,
        )

    # Use the foundation calculation
    result = _base_calculate_parlay(legs, stake)

    # Augment with SGP detection
    result.is_same_game = is_same_game_parlay(legs)
    result.sgp_available = sgp_price_available()

    return result


def build_parlay_dict(
    legs: list[dict],
    stake: float = 100.0,
) -> dict:
    """
    Build a parlay from a list of leg dicts and return a dict response.

    Each leg dict should have:
        event_id, market, selection, bookmaker, odds (American)

    Convenience wrapper for API consumption.
    """
    parlay_legs = [
        ParlayLeg(
            event_id=leg.get("event_id", ""),
            market=leg.get("market", ""),
            selection=leg.get("selection", ""),
            bookmaker=leg.get("book", leg.get("bookmaker", "")),
            odds=leg.get("odds", 0),
        )
        for leg in legs
    ]

    result = build_parlay(parlay_legs, stake)

    return _format_parlay_result(result)


def _format_parlay_result(result: ParlayResult) -> dict:
    """Format a ParlayResult into a UI/API-friendly dict."""
    legs_formatted = []
    for leg in result.legs:
        legs_formatted.append({
            "event_id": leg.event_id,
            "market": leg.market,
            "selection": leg.selection,
            "bookmaker": leg.bookmaker,
            "odds": leg.odds,
            "decimal_odds": round(american_to_decimal(leg.odds), 4),
            "implied_probability": round(1.0 / american_to_decimal(leg.odds) * 100, 1),
        })

    response = {
        "legs": legs_formatted,
        "leg_count": result.leg_count,
        "combined_decimal": result.combined_decimal,
        "combined_american": result.combined_american,
        "implied_probability": result.implied_probability,
        "stake": result.stake,
        "potential_payout": result.potential_payout,
        "potential_profit": result.potential_profit,
        "is_same_game_parlay": result.is_same_game,
        "sgp_available": result.sgp_available,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Add SGP disclaimer if applicable
    if result.is_same_game and not result.sgp_available:
        response["sgp_disclaimer"] = (
            "Same-game parlay pricing unavailable from current odds provider. "
            "Parlay odds shown use standard multiplicative calculation and may "
            "differ from bookmaker-specific SGP pricing."
        )

    # Cross-game parlay confirmation
    if not result.is_same_game:
        response["parlay_type"] = "cross_game"
        response["parlay_note"] = "Cross-game parlay — each leg is from a different event."

    return response


def validate_parlay_legs(legs: list[dict]) -> dict:
    """
    Validate a list of parlay leg dicts before building.

    Returns {"valid": True/False, "errors": [...], "warnings": [...]}
    """
    errors = []
    warnings = []

    if not legs:
        errors.append("At least 2 legs are required for a parlay")
    elif len(legs) < 2:
        errors.append(f"Minimum 2 legs required, got {len(legs)}")

    for i, leg in enumerate(legs):
        idx = i + 1
        if not leg.get("event_id"):
            errors.append(f"Leg {idx}: missing event_id")
        if not leg.get("odds"):
            errors.append(f"Leg {idx}: missing odds")
        elif not isinstance(leg.get("odds"), int):
            try:
                leg["odds"] = int(leg["odds"])
            except (ValueError, TypeError):
                errors.append(f"Leg {idx}: odds must be an integer (American odds)")

    # SGP warning
    if is_same_game_parlay([
        ParlayLeg(
            event_id=leg.get("event_id", ""),
            market=leg.get("market", ""),
            selection=leg.get("selection", ""),
            bookmaker=leg.get("book", leg.get("bookmaker", "")),
            odds=leg.get("odds", 0),
        )
        for leg in legs
    ]):
        if not sgp_price_available():
            warnings.append(
                "Same-game parlay detected but SGP pricing is not available. "
                "Displayed odds use standard multiplicative calculation."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "leg_count": len(legs),
    }