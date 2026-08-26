"""
SB ME Native Projection Engine — computes DFS projections from SGO intelligence.

Uses SportsGameOdds fantasyScore markets and player props as primary inputs.
No SportsDataIO dependency. No synthetic/scrambled data.
"""

from __future__ import annotations
import logging
from typing import Optional
from datetime import datetime, timezone

from intelligence.sports import SPORT_MARKETS, resolve_market

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  MLB Projection Model
# ══════════════════════════════════════════════════════════════

# Hitter: standard DFS scoring weights
# DK: Single=3, Double=5, Triple=8, HR=10, RBI=2, R=2, BB=2, SB=5, HBP=2
# Approximate from props: hits includes all types, we estimate distribution
MLB_HITTER_WEIGHTS = {
    "hits": 3.0,          # average hit value (singles 3, doubles 5, triples 8)
    "homeRuns": 10.0,     # DK: HR = 10 pts
    "rbi": 2.0,           # DK: RBI = 2 pts
    "totalBases": 1.2,    # DK: TB = 1 pt per base, approximate factor
    "stolenBases": 5.0,   # DK: SB = 5 pts
    "walks": 2.0,         # DK: BB = 2 pts
    "battingStrikeouts": -0.5,  # DK: K = -0.5
}

# Pitcher: DK scoring
# IP=2.25, K=2, ER=-2, H=-0.6, BB=-0.6, W=4, QS=1.5
MLB_PITCHER_WEIGHTS = {
    "pitchingStrikeouts": 2.0,       # DK: K = 2 pts
    "pitchingOuts": 0.75,            # DK: IP = 2.25, 1 out = 0.75
    "pitchingEarnedRuns": -2.0,      # DK: ER = -2
    "pitchingHits": -0.6,            # DK: H allowed = -0.6
    "pitchingWalks": -0.6,           # DK: BB = -0.6
}


def _compute_mlb_hitter_projection(props: dict[str, float]) -> float:
    """Compute hitter fantasy projection from available props."""
    proj = 0.0
    count = 0
    for mk, weight in MLB_HITTER_WEIGHTS.items():
        val = props.get(mk)
        if val is not None:
            proj += val * weight
            count += 1
    return round(proj, 1) if count >= 2 else 0.0


def _compute_mlb_pitcher_projection(props: dict[str, float]) -> float:
    """Compute pitcher fantasy projection from available props."""
    proj = 0.0
    count = 0
    for mk, weight in MLB_PITCHER_WEIGHTS.items():
        val = props.get(mk)
        if val is not None:
            proj += val * weight
            count += 1
    return round(proj, 1) if count >= 2 else 0.0


# ══════════════════════════════════════════════════════════════
#  Projection Engine
# ══════════════════════════════════════════════════════════════

from dataclasses import dataclass, field


@dataclass
class NativeProjection:
    player_id: str
    player_name: str
    sport: str
    position: str
    salary: int
    team: str = ""
    opponent: Optional[str] = None
    fppg: Optional[float] = None  # DK FPPG from Blue Collar DFS
    base_projection: float = 0.0
    projection_source: str = "UNAVAILABLE"  # SGO_FANTASY_MARKET | PROP_BASED | HYBRID | UNAVAILABLE
    projection_confidence: float = 0.0
    projection_updated_at: Optional[datetime] = None
    props_used: list[str] = field(default_factory=list)
    fantasy_market_line: Optional[float] = None


def compute_projections(
    sport: str,
    players: list[dict],           # [{id, name, position, salary, props: {}}]
    sgo_intelligence: dict = None, # {player_id: {fantasyScore, props, ...}}
) -> list[NativeProjection]:
    """
    Compute native projections for a slate of DFS players.

    Priority:
      1. SGO fantasyScore market → direct projection
      2. Prop-based model → weighted computation
      3. UNAVAILABLE → player not projectable
    """
    results = []
    sgo_data = sgo_intelligence or {}

    for p in players:
        pid = str(p.get("id") or p.get("player_id") or "")
        name = p.get("name") or p.get("player_name") or ""
        pos = (p.get("position") or "").upper()
        salary = p.get("salary") or 0

        proj = NativeProjection(
            player_id=pid, player_name=name, sport=sport,
            position=pos, salary=int(salary),
            team=p.get("team") or "",
            opponent=p.get("opponent"),
            fppg=p.get("fppg"),
        )

        # Check SGO intelligence enrichment
        sgo = sgo_data.get(pid, {})
        fantasy_market = sgo.get("fantasyMarketLine") or sgo.get("fantasyScore")
        props = sgo.get("props") or p.get("props") or {}

        if fantasy_market is not None and float(fantasy_market) > 0:
            # Method 1: Direct fantasyScore market
            proj.base_projection = round(float(fantasy_market), 1)
            proj.projection_source = "SGO_FANTASY_MARKET"
            proj.projection_confidence = 0.8
            proj.fantasy_market_line = float(fantasy_market)
            proj.props_used = ["fantasyScore"]

        elif props and sport == "MLB":
            # Method 2: Prop-based model
            if "P" in pos or "SP" in pos or "RP" in pos:
                fp = _compute_mlb_pitcher_projection(props)
            else:
                fp = _compute_mlb_hitter_projection(props)

            if fp > 0:
                proj.base_projection = fp
                proj.projection_source = "PROP_BASED"
                proj.projection_confidence = 0.5
                proj.props_used = [k for k, v in props.items() if v is not None]

        # Unprojectable players get explicit UNAVAILABLE status
        # (not 1.0 placeholder)

        proj.projection_updated_at = datetime.now(timezone.utc)
        results.append(proj)

    return results


def projections_to_pool(projections: list[NativeProjection]) -> list[dict]:
    """Convert NativeProjection list to optimizer-compatible pool dicts.

    Emits both `position` and `roster_position` (the CP-SAT optimizer reads
    `roster_position`) plus `team`/`opponent` so stacking and pitcher-conflict
    constraints survive the projection pass.
    """
    return [{
        "id": p.player_id,
        "name": p.player_name,
        "position": p.position,
        "roster_position": p.position,
        "salary": p.salary,
        "fppg": p.fppg,
        "team": p.team,
        "opponent": p.opponent,
        "projected_fp": p.base_projection,
        "projection_source": p.projection_source,
        "projection_confidence": p.projection_confidence,
    } for p in projections]