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
    prop_fp: Optional[float] = None
    game_info: Optional[str] = None


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
            game_info=p.get("game_info"),
        )

        # Check SGO intelligence enrichment
        sgo = sgo_data.get(pid, {})
        fantasy_market = sgo.get("fantasyMarketLine") or sgo.get("fantasyScore")
        props = sgo.get("props") or p.get("props") or {}
        is_pitcher = "P" in pos or "SP" in pos or "RP" in pos

        if fantasy_market is not None and float(fantasy_market) > 0:
            # Record SGO as a raw source. Optimizer mean is decided later by
            # apply_projection_policy (identity-gated consensus).
            proj.base_projection = round(float(fantasy_market), 1)
            proj.projection_source = "SGO_FANTASY_MARKET"
            proj.projection_confidence = 0.8
            proj.fantasy_market_line = float(fantasy_market)
            proj.props_used = ["fantasyScore"]

        if props and is_pitcher:
            # Pitcher props are an independent DK-scored estimate. Stored even
            # when SGO fantasyScore exists. Unmatched identities will not use
            # this as the optimizer mean.
            fp = _compute_mlb_pitcher_projection(props)
            if fp > 0:
                proj.prop_fp = fp
                if proj.projection_source == "UNAVAILABLE":
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
    Raw SGO / BC values are not overwritten.
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


# Disagreement protection: when independent FP sources diverge, the solver
# mean is capped relative to the lower source. Raw provider values are kept.
R_AGREE = 1.20
R_CAP = 1.35
VERIFIED_IDENTITY = "MATCHED"


def identity_verified(p: dict) -> bool:
    """True only when SB ME reconciliation marked a verified identity match."""
    return str(p.get("mapping_status") or "").strip().upper() == VERIFIED_IDENTITY


def _positive_fp(val) -> Optional[float]:
    try:
        n = float(val)
    except (TypeError, ValueError):
        return None
    if n > 0:
        return n
    return None


def stamp_raw_fp_sources(p: dict) -> dict:
    """Copy raw SGO / BC / prop onto dedicated keys. Never clobber existing raws."""
    out = dict(p)
    sgo = _positive_fp(out.get("sgo_fp"))
    if sgo is None:
        sgo = _positive_fp(out.get("fantasy_market_line"))
    if sgo is None and str(out.get("projection_source") or "") == "SGO_FANTASY_MARKET":
        sgo = _positive_fp(out.get("projected_fp"))
    if sgo is not None and out.get("sgo_fp") is None:
        out["sgo_fp"] = sgo
    bc = _positive_fp(out.get("bc_fp"))
    if bc is None:
        bc = _positive_fp(out.get("fppg"))
    if bc is not None:
        if out.get("bc_fp") is None:
            out["bc_fp"] = bc
        if out.get("fppg") is None:
            out["fppg"] = bc
    return out


def collect_fp_sources(p: dict) -> dict[str, float]:
    """Independent fantasy-point estimates already on the player dict.

    Does not invent values. Does not use 1.35× projection, hitter O/U props,
    Optimal%, or Last-5.
    """
    out: dict[str, float] = {}
    sgo = _positive_fp(p.get("sgo_fp"))
    if sgo is None:
        sgo = _positive_fp(p.get("fantasy_market_line"))
    if sgo is not None:
        out["sgo"] = sgo
    bc = _positive_fp(p.get("fppg"))
    if bc is None:
        bc = _positive_fp(p.get("bc_fp"))
    if bc is not None:
        out["bc"] = bc
    prop = _positive_fp(p.get("prop_fp"))
    if prop is not None:
        out["prop"] = prop
    return out


def apply_source_consensus(pool: list[dict]) -> list[dict]:
    """Set optimizer projected_fp / ceiling / floor from real independent sources.

    Raw sgo_fp / bc_fp / fppg / prop_fp are preserved.
    Single source: mean = that source.
    Agreeing sources (hi/lo <= R_AGREE): prefer SGO when present, else mean.
    Disagreement: mean = min(hi, lo * R_CAP); ceiling = max; floor = min.
    """
    out: list[dict] = []
    for raw in pool:
        p = dict(raw)
        sources = collect_fp_sources(p)
        if "sgo" in sources and p.get("sgo_fp") is None:
            p["sgo_fp"] = sources["sgo"]
        if "bc" in sources and p.get("bc_fp") is None:
            p["bc_fp"] = sources["bc"]
        if "prop" in sources and p.get("prop_fp") is None:
            p["prop_fp"] = sources["prop"]

        if (p.get("projection_source") or "") == "MY_PROJ":
            mean = _positive_fp(p.get("projected_fp"))
            if mean is None:
                mean = 0.0
            p["projected_fp"] = round(mean, 1)
            if sources:
                p["floor"] = round(min(sources.values()), 1)
                p["ceiling"] = round(max(sources.values()), 1)
            else:
                p["ceiling"] = round(mean, 1)
                p["floor"] = round(mean, 1)
            out.append(p)
            continue

        vals = list(sources.values())
        if not vals:
            p["ceiling"] = p.get("ceiling")
            p["floor"] = p.get("floor")
            out.append(p)
            continue

        lo, hi = min(vals), max(vals)
        p["floor"] = round(lo, 1)
        p["ceiling"] = round(hi, 1)

        if len(vals) == 1:
            p["projected_fp"] = round(vals[0], 1)
            out.append(p)
            continue

        if hi / lo <= R_AGREE:
            if "sgo" in sources:
                p["projected_fp"] = round(sources["sgo"], 1)
                if p.get("projection_source") in (None, "UNAVAILABLE", "BC_PROJ_FALLBACK", "SLATE_SOURCE"):
                    p["projection_source"] = "SGO_FANTASY_MARKET"
            else:
                p["projected_fp"] = round(sum(vals) / len(vals), 1)
                p["projection_source"] = "CONSENSUS"
            out.append(p)
            continue

        capped = min(hi, lo * R_CAP)
        p["projected_fp"] = round(capped, 1)
        p["projection_source"] = "CONSENSUS_CAPPED"
        out.append(p)
    return out


def apply_unmatched_slate_source(p: dict) -> dict:
    """Unmatched identity: optimizer mean is slate-source (BC FPPG) only.

    Raw SGO / prop values stay on the dict for the integrity report and are
    not used as the solver projection. No team/player match is inferred.
    """
    out = dict(p)
    out["identity_verified"] = False
    bc = _positive_fp(out.get("fppg"))
    if bc is None:
        bc = _positive_fp(out.get("bc_fp"))
    if bc is not None:
        out["projected_fp"] = round(bc, 1)
        out["projection_source"] = "SLATE_SOURCE"
        out["projection_confidence"] = 0.4
        out["ceiling"] = round(bc, 1)
        out["floor"] = round(bc, 1)
        out["fppg_was_fallback"] = True
    else:
        out["projected_fp"] = 0.0
        out["projection_source"] = "UNAVAILABLE"
    return out


def apply_projection_policy(pool: list[dict]) -> list[dict]:
    """Canonical post-SGO policy used by /optimize, Data Hub, Sims, Stacks, AI.

    Matched identity: consensus-cap independent SGO/BC/prop sources.
    Unmatched identity: slate-source FPPG only — never SGO or props.
    Raw provider values are preserved on sgo_fp / bc_fp / fppg / prop_fp.
    """
    out: list[dict] = []
    for raw in pool:
        p = stamp_raw_fp_sources(raw)
        if str(p.get("projection_source") or "") == "MY_PROJ":
            p["identity_verified"] = identity_verified(p)
            out.append(apply_source_consensus([p])[0])
            continue
        if not identity_verified(p):
            out.append(apply_unmatched_slate_source(p))
            continue
        p = apply_bc_proj_fallback([p])[0]
        p = apply_source_consensus([p])[0]
        p["identity_verified"] = True
        out.append(p)
    eligible = resolve_eligible_pitcher_ids(out)
    for p in out:
        if is_pitcher_player(p):
            p["mlb_pitcher_eligible"] = _player_id(p) in eligible
        else:
            p["mlb_pitcher_eligible"] = True
    return out


def lineup_projection_total(players: list[dict]) -> float:
    """Sum of optimizer projected_fp values, rounded to one decimal."""
    return round(sum(float(p.get("projected_fp") or 0) for p in players or []), 1)


def build_projection_integrity_report(
    pool: list[dict],
    *,
    slate_id=None,
    slate_name: Optional[str] = None,
    salary_source: Optional[str] = None,
    freshness: Optional[str] = None,
    uploaded_at: Optional[str] = None,
    published_at: Optional[str] = None,
) -> dict:
    """Per-player optimizer-input lineage. Does not invent matches or projections."""
    salary_label = salary_source or "native"
    if str(salary_label).lower() in ("native", "bcdfs", "blue_collar", "draftkings", "fanduel"):
        salary_label = "stored_contest_salaries"
    players = []
    for p in pool or []:
        verified = bool(p.get("identity_verified")) or identity_verified(p)
        raw_bc = p.get("bc_fp")
        if raw_bc is None:
            raw_bc = p.get("fppg")
        players.append({
            "id": str(p.get("id") or p.get("player_id") or ""),
            "name": p.get("name") or p.get("player_name") or "",
            "team": p.get("team") or "",
            "identity_verified": verified,
            "mapping_status": str(p.get("mapping_status") or "UNMATCHED"),
            "projection_source": p.get("projection_source") or "UNAVAILABLE",
            "raw_sgo_fp": p.get("sgo_fp"),
            "raw_bc_fp": raw_bc,
            "optimizer_projected_fp": p.get("projected_fp"),
            "slate_member": True,
            "game_info": p.get("game_info"),
            "salary": p.get("salary"),
            "salary_source": salary_label,
            "freshness": freshness,
        })
    matched = sum(1 for row in players if row["identity_verified"])
    return {
        "slate_id": slate_id,
        "slate_name": slate_name,
        "salary_source": salary_label,
        "freshness": freshness,
        "uploaded_at": uploaded_at,
        "published_at": published_at,
        "matched_count": matched,
        "unmatched_count": len(players) - matched,
        "player_count": len(players),
        "players": players,
    }


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
        "fantasy_market_line": p.fantasy_market_line,
        "sgo_fp": p.fantasy_market_line if p.fantasy_market_line and p.fantasy_market_line > 0 else None,
        "prop_fp": p.prop_fp,
        "game_info": p.game_info,
    } for p in projections]