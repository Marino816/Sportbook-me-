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

# Hitter: DraftKings standard MLB scoring
# DK: Single=3, Double=5, Triple=8, HR=10, RBI=2, R=2, BB=2, SB=5, HBP=2
# DK does NOT penalise hitter strikeouts in standard contests.
#
# PROP_BASED hitter projections have been RETIRED (commit 67e681d+).
# SGO props are betting-market O/U thresholds (e.g. 0.5 HR line),
# NOT expected-value predictions.  Multiplying a threshold by a DK
# weight produces a mathematically invalid fantasy-point estimate.
#
# Valid hitter projection sources:
#   1. SGO_FANTASY_MARKET → direct fantasyScore market line
#   2. BC_PROJ_FALLBACK   → Blue Collar DFS projection (validated independent)
#   3. UNAVAILABLE        → no valid source — excluded from optimisation

# Pitcher: DK scoring
# IP=2.25, K=2, ER=-2, H=-0.6, BB=-0.6, W=4, QS=1.5
# Pitcher props (IP, K, ER) from SGO are legitimate expected values
# and PROP_BASED remains valid for pitchers without a fantasyScore market.
MLB_PITCHER_WEIGHTS = {
    "pitchingStrikeouts": 2.0,       # DK: K = 2 pts
    "pitchingOuts": 0.75,            # DK: IP = 2.25, 1 out = 0.75
    "pitchingEarnedRuns": -2.0,      # DK: ER = -2
    "pitchingHits": -0.6,            # DK: H allowed = -0.6
    "pitchingWalks": -0.6,           # DK: BB = -0.6
}


def _compute_mlb_pitcher_projection(props: dict[str, float]) -> float:
    """Compute pitcher fantasy projection from available props.
    
    Pitcher props (IP, K, ER) are legitimate expected-value signals —
    unlike hitter props which are O/U betting thresholds.
    """
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
    eligible_positions: list[str] = field(default_factory=list)
    mapping_status: Optional[str] = None
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
      2. Pitcher prop-based model → weighted computation (pitchers only)
      3. UNAVAILABLE → player not projectable

    Hitter PROP_BASED is RETIRED.  SGO hitter props are O/U betting
    thresholds (e.g. 0.5 HR), not expected-value predictions, and
    cannot be multiplied by DK weights to produce valid fantasy points.
    Hitters without an SGO fantasyScore market receive UNAVAILABLE
    status here; the optimizer may later apply a BC_PROJ_FALLBACK if
    Blue Collar has a valid independent projection.
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
            eligible_positions=list(p.get("eligible_positions") or []),
            mapping_status=p.get("mapping_status"),
        )

        # Check SGO intelligence enrichment
        sgo = sgo_data.get(pid, {})
        fantasy_market = sgo.get("fantasyMarketLine") or sgo.get("fantasyScore")
        props = sgo.get("props") or p.get("props") or {}
        is_pitcher = "P" in pos or "SP" in pos or "RP" in pos

        if fantasy_market is not None and float(fantasy_market) > 0:
            # Method 1: Direct fantasyScore market (hitters & pitchers)
            proj.base_projection = round(float(fantasy_market), 1)
            proj.projection_source = "SGO_FANTASY_MARKET"
            proj.projection_confidence = 0.8
            proj.fantasy_market_line = float(fantasy_market)
            proj.props_used = ["fantasyScore"]

        elif props and is_pitcher:
            # Method 2: Prop-based model — pitchers only.
            # Pitcher props (IP, K, ER) are legitimate expected values.
            fp = _compute_mlb_pitcher_projection(props)
            if fp > 0:
                proj.base_projection = fp
                proj.projection_source = "PROP_BASED"
                proj.projection_confidence = 0.5
                proj.props_used = [k for k, v in props.items() if v is not None]

        # Hitters without fantasyScore: UNAVAILABLE (was PROP_BASED).
        # apply_bc_proj_fallback() may later attach BC_PROJ_FALLBACK.

        proj.projection_updated_at = datetime.now(timezone.utc)
        results.append(proj)

    return results


def _is_pitcher_pos(pos: str) -> bool:
    p = (pos or "").upper()
    return "P" in p or "SP" in p or "RP" in p


def _player_id(p: dict) -> str:
    return str(p.get("id") or p.get("player_id") or "")


def pitcher_position_tokens(p: dict) -> set[str]:
    """Roster tokens used for SP/RP vs P starter classification."""
    pos = str(p.get("roster_position") or p.get("position") or "").upper()
    tokens = {pos} if pos else set()
    for x in p.get("eligible_positions") or []:
        t = str(x).upper().strip()
        if t:
            tokens.add(t)
    return tokens


def is_pitcher_player(p: dict) -> bool:
    return any(_is_pitcher_pos(t) for t in pitcher_position_tokens(p)) or _is_pitcher_pos(
        str(p.get("roster_position") or p.get("position") or "")
    )


def _is_rp_only(p: dict) -> bool:
    tokens = pitcher_position_tokens(p)
    return "RP" in tokens and "SP" not in tokens


def _is_sp_labeled(p: dict) -> bool:
    return "SP" in pitcher_position_tokens(p)


def has_bc_pitcher_coverage(pool: list[dict]) -> bool:
    """True when Blue Collar supplied at least one pitcher projection (fppg>0)."""
    for p in pool:
        if not is_pitcher_player(p):
            continue
        fppg = p.get("fppg")
        if fppg is not None and float(fppg) > 0:
            return True
    return False


def resolve_eligible_pitcher_ids(pool: list[dict]) -> set[str]:
    """MLB pitcher starter eligibility — shared by optimizer, hub, sims, AI.

    Precedence:
      1. If the slate has BC pitcher coverage (any fppg>0): BC fppg>0 is the
         exclusive starter signal. Relievers without BC proj are excluded.
         SGO fantasyScore alone is never a starter proof.
      2. Else (BC unavailable / CSV-only):
         a. If SP vs RP labels exist on the slate, SP is eligible and RP-only
            is excluded (DK/FD roster-position signal already in the CSV).
         b. Else pitchers with PROP_BASED outing props (IP/K/ER) and fp>0.
         c. Else the highest-salary pitcher per team (operational stand-in
            for BC's one-starter-per-team rule using salary already on the
            slate). SGO fantasyScore is still not used as a starter gate.
    """
    from dfs.team_normalize import normalize_team_abbr

    pitchers = [p for p in pool if is_pitcher_player(p)]
    if not pitchers:
        return set()

    if has_bc_pitcher_coverage(pool):
        return {
            _player_id(p)
            for p in pitchers
            if p.get("fppg") is not None and float(p.get("fppg") or 0) > 0
        }

    has_split = any(_is_sp_labeled(p) or _is_rp_only(p) for p in pitchers)
    if has_split:
        return {_player_id(p) for p in pitchers if not _is_rp_only(p)}

    prop_ids = {
        _player_id(p)
        for p in pitchers
        if (p.get("projection_source") == "PROP_BASED" and float(p.get("projected_fp") or 0) > 0)
    }
    if prop_ids:
        return prop_ids

    best_by_team: dict[str, tuple[str, int]] = {}
    for p in pitchers:
        team = normalize_team_abbr(p.get("team") or "") or "_none"
        sal = int(p.get("salary") or 0)
        pid = _player_id(p)
        prev = best_by_team.get(team)
        if prev is None or sal > prev[1]:
            best_by_team[team] = (pid, sal)
    return {pid for pid, sal in best_by_team.values() if pid and sal > 0}


def apply_bc_proj_fallback(pool: list[dict]) -> list[dict]:
    """Apply Blue Collar fppg when SGO produced no usable fantasy-point value.

    Value policy (not eligibility):
      - Hitters: fppg>0 becomes BC_PROJ_FALLBACK when projected_fp<=0
      - Pitchers: same, when BC fppg>0 (does not promote relievers by itself)
    """
    out: list[dict] = []
    for raw in pool:
        p = dict(raw)
        fp = float(p.get("projected_fp") or 0)
        fppg = p.get("fppg")
        if fp <= 0 and fppg is not None and float(fppg) > 0:
            p["projected_fp"] = round(float(fppg), 1)
            p["projection_source"] = "BC_PROJ_FALLBACK"
            p["projection_confidence"] = 0.4
            p["fppg_was_fallback"] = True
        out.append(p)
    return out


def apply_projection_policy(pool: list[dict]) -> list[dict]:
    """Canonical post-SGO policy used by /optimize, Data Hub, Sims, Stacks, AI."""
    out = apply_bc_proj_fallback(pool)
    eligible = resolve_eligible_pitcher_ids(out)
    for p in out:
        if is_pitcher_player(p):
            p["mlb_pitcher_eligible"] = _player_id(p) in eligible
        else:
            p["mlb_pitcher_eligible"] = True
    return out


def count_projected_players(pool: list[dict]) -> int:
    """Count players with a usable projection under solver eligibility rules."""
    eligible = resolve_eligible_pitcher_ids(pool)
    n = 0
    for p in pool:
        fp = float(p.get("projected_fp") or 0)
        if fp <= 0:
            continue
        if is_pitcher_player(p) and _player_id(p) not in eligible:
            continue
        n += 1
    return n


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
        "eligible_positions": list(p.eligible_positions or []),
        "salary": p.salary,
        "fppg": p.fppg,
        "team": p.team,
        "opponent": p.opponent,
        "mapping_status": p.mapping_status,
        "projected_fp": p.base_projection,
        "projection_source": p.projection_source,
        "projection_confidence": p.projection_confidence,
    } for p in projections]