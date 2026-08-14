"""
SB ME Projected Ownership + Leverage Model.

Produces a *modeled* projected ownership percentage for each player using
only legitimate, available inputs (salary, SB projection, value, position
scarcity, and game/team environment). This is NOT actual DraftKings/FanDuel
ownership (that is only known after lock); it is an SB ME model estimate,
clearly labeled as such.

The model normalizes ownership against roster-slot demand so that, for each
position, the sum of projected ownership across all eligible players equals
the number of roster slots for that position (e.g. 2 P, 3 OF).

Leverage is the modeled relationship between a player's strength (value /
optimal-adjacent appearance) and their projected field ownership: positive
leverage = strong player who is under-owned relative to their strength.

Model metadata (version + generated-at + inputs) is returned so consumers can
identify how/when the estimate was produced.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

OWNERSHIP_MODEL_VERSION = "sbme-ownership-v1"

# Roster slot counts by platform (MLB). Other sports use a per-position fallback.
DK_MLB_SLOTS = {"P": 2, "C": 1, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "OF": 3}
FD_MLB_SLOTS = {"P": 1, "C1B": 1, "2B": 1, "3B": 1, "SS": 1, "OF": 3, "UTIL": 1}


def _slot_for(position: str, platform: str) -> str:
    """Normalize a roster position to a roster-slot key."""
    p = (position or "").upper()
    if p in ("SP", "RP", "P"):
        return "P"
    if platform == "fanduel" and p in ("C", "1B"):
        return "C1B"
    if p in ("C", "1B", "2B", "3B", "SS"):
        return p
    if p in ("OF", "LF", "RF", "CF", "DH"):
        return "OF"
    return p


def _slots_for_platform(platform: str) -> dict:
    return FD_MLB_SLOTS if platform == "fanduel" else DK_MLB_SLOTS


def compute_ownership_and_leverage(
    pool: list[dict],
    platform: str = "draftkings",
    sport: str = "MLB",
) -> tuple[list[dict], dict]:
    """
    Attach sbme_ownership_pct + leverage to each pool dict (mutates + returns).

    Ownership model (documented): each player's raw ownership strength is a
    weighted blend of normalized projection and normalized value, plus a mild
    inverse-salary term (lower salary = more affordable = higher field share).
    Strengths are then normalized per roster-slot so slot demand is respected.

    Leverage = value_percentile - ownership_percentile (positive = under-owned
    relative to strength).

    Returns (pool, metadata).
    """
    slots = _slots_for_platform(platform)

    # Gather numeric inputs defensively
    projections = []
    salaries = []
    values = []
    for p in pool:
        fp = float(p.get("projected_fp") or 0)
        sal = float(p.get("salary") or 0)
        val = (fp / (sal / 1000.0)) if sal > 0 else 0.0
        projections.append(fp)
        salaries.append(sal)
        values.append(val)

    max_proj = max(projections) if projections else 1.0
    max_val = max(values) if values else 1.0
    max_sal = max(salaries) if salaries else 1.0

    def _norm(x, mx):
        return (x / mx) if mx > 0 else 0.0

    # Raw ownership strength per player
    raw_strength = []
    for p in pool:
        fp = float(p.get("projected_fp") or 0)
        sal = float(p.get("salary") or 0)
        val = (fp / (sal / 1000.0)) if sal > 0 else 0.0
        # weights: projection 0.5, value 0.35, inverse-salary 0.15
        strength = (
            0.5 * _norm(fp, max_proj)
            + 0.35 * _norm(val, max_val)
            + 0.15 * (1.0 - _norm(sal, max_sal))
        )
        raw_strength.append(strength)

    # Group by slot and normalize to slot demand
    slot_players: dict[str, list[int]] = {}
    for i, p in enumerate(pool):
        slot = _slot_for(p.get("roster_position") or p.get("position", ""), platform)
        slot_players.setdefault(slot, []).append(i)

    ownership = [0.0] * len(pool)
    for slot, idxs in slot_players.items():
        demand = slots.get(slot)
        if not demand:
            demand = 1
        total_strength = sum(raw_strength[i] for i in idxs) or 1.0
        for i in idxs:
            # ownership share = strength / total_strength * demand (as a %)
            ownership[i] = (raw_strength[i] / total_strength) * demand * 100.0

    # Value percentile for leverage
    ranked = sorted(range(len(pool)), key=lambda i: values[i])  # ascending
    n = len(pool) or 1
    value_pct = [0.0] * len(pool)
    for rank, i in enumerate(ranked):
        value_pct[i] = (rank / (n - 1)) * 100.0 if n > 1 else 50.0

    own_sorted = sorted(range(len(pool)), key=lambda i: ownership[i])
    own_pct = [0.0] * len(pool)
    for rank, i in enumerate(own_sorted):
        own_pct[i] = (rank / (n - 1)) * 100.0 if n > 1 else 50.0

    for i, p in enumerate(pool):
        p["sbme_ownership_pct"] = round(ownership[i], 2)
        p["leverage"] = round(value_pct[i] - own_pct[i], 2)

    metadata = {
        "model": OWNERSHIP_MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": ["salary", "sb_projection", "value", "position_scarcity"],
        "platform": platform,
        "sport": sport,
        "note": "Modeled field-ownership estimate, not actual lock ownership.",
    }
    return pool, metadata
