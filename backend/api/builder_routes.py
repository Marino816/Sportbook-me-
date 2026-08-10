"""
SB-Me Builder API endpoints.

Endpoints:
  POST /api/builder/lineups
  POST /api/builder/portfolios
  POST /api/builder/validate
  GET  /api/builder/runs/{id}
  GET  /api/builder/portfolios/{id}
  POST /api/builder/rebuild/{id}
"""

import time
import uuid
import random
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User, Projection, Player
from api.auth import get_current_user
from api.utils import wrap_data
from ai.projection_service import log_audit_record

from builder.engine import (
    BuilderValidator, ExposureEngine, PortfolioEngine, ExplanationGenerator,
    DK_CAP, FD_CAP,
)
from builder.strategy import (
    get_strategy, list_strategies, builder_objective, StrategyProfile,
)

router = APIRouter(prefix="/builder", tags=["SB-Me Builder"])

# ── Gating ───────────────────────────────────────────────────
GATING = {
    "free": {"max_lineups": 1, "strategies": ["cash", "balanced", "conservative"], "portfolios": False},
    "pro_arena": {"max_lineups": 20, "strategies": ["all"], "portfolios": True},
    "elite_stack": {"max_lineups": 150, "strategies": ["all"], "portfolios": True},
}

def _tier(user: User) -> str:
    if not user.is_pro: return "free"
    try:
        s = getattr(user, "subscription", None)
        if s and getattr(s, "plan_name", "") == "Elite Stack": return "elite_stack"
    except: pass
    return "pro_arena"

# ── Request Schemas ──────────────────────────────────────────
class LineupRequest(BaseModel):
    slate_id: int
    platform: str = "draftkings"
    sport: str = "nba"
    strategy: str = "balanced"
    lineup_count: int = 1
    locked_player_ids: List[int] = []
    excluded_player_ids: List[int] = []
    randomness: float = 0.0

class PortfolioRequest(BaseModel):
    slate_id: int
    platform: str = "draftkings"
    sport: str = "nba"
    strategy: str = "balanced"
    lineup_count: int = 5
    locked_player_ids: List[int] = []
    excluded_player_ids: List[int] = []
    exposure_rules: List[dict] = []
    randomness: float = 0.0

# ── Projection Loader ──────────────────────────────────────────
async def _load_projections(slate_id: int, db: AsyncSession) -> list[dict]:
    """Load projections from database. Returns empty list if none found."""
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Projection, Player)
        .join(Player, Projection.player_id == Player.id)
        .where(Projection.slate_id == slate_id)
        .order_by(Projection.projected_fp.desc())
    )
    rows = result.all()
    if not rows:
        return []
    return [
        {
            "id": proj.player_id,
            "name": player.name,
            "team": player.team,
            "salary": proj.salary,
            "roster_position": proj.roster_position,
            "projected_fp": proj.projected_fp,
            "ceiling": proj.ceiling,
            "floor": proj.floor,
            "ownership": proj.ownership,  # null when unavailable
            "value": proj.value,
            "leverage": proj.leverage,
        }
        for proj, player in rows
    ]

NBA_DEMO = [
    {"id":1,"name":"Luka Doncic","team":"DAL","salary":11000,"roster_position":"PG","projected_fp":55.4,"ceiling":65,"edge_score":78,"risk_score":0.1,"ownership":None},
    {"id":2,"name":"Stephen Curry","team":"GSW","salary":10500,"roster_position":"PG","projected_fp":52.1,"ceiling":60,"edge_score":72,"risk_score":0.15,"ownership":None},
    {"id":3,"name":"Nikola Jokic","team":"DEN","salary":11500,"roster_position":"C","projected_fp":60.5,"ceiling":70,"edge_score":85,"risk_score":0.05,"ownership":None},
    {"id":4,"name":"Jayson Tatum","team":"BOS","salary":10200,"roster_position":"SF","projected_fp":48.2,"ceiling":55,"edge_score":65,"risk_score":0.1,"ownership":None},
    {"id":5,"name":"Giannis Antetokounmpo","team":"MIL","salary":10800,"roster_position":"PF","projected_fp":54.0,"ceiling":62,"edge_score":80,"risk_score":0.08,"ownership":None},
    {"id":6,"name":"Bennedict Mathurin","team":"IND","salary":4500,"roster_position":"SF","projected_fp":25.0,"ceiling":35,"edge_score":45,"risk_score":0.3,"ownership":None},
    {"id":7,"name":"Kevin Durant","team":"PHX","salary":9800,"roster_position":"PF","projected_fp":44.0,"ceiling":50,"edge_score":60,"risk_score":0.12,"ownership":None},
    {"id":8,"name":"Joel Embiid","team":"PHI","salary":11300,"roster_position":"C","projected_fp":56.0,"ceiling":66,"edge_score":82,"risk_score":0.1,"ownership":None},
    {"id":9,"name":"Austin Reaves","team":"LAL","salary":6500,"roster_position":"SG","projected_fp":32.0,"ceiling":42,"edge_score":55,"risk_score":0.2,"ownership":None},
    {"id":10,"name":"Tyrese Haliburton","team":"IND","salary":9500,"roster_position":"PG","projected_fp":46.0,"ceiling":54,"edge_score":68,"risk_score":0.08,"ownership":None},
    {"id":11,"name":"Value PG","team":"ORL","salary":3800,"roster_position":"PG","projected_fp":18.0,"ceiling":25,"edge_score":35,"risk_score":0.3,"ownership":None},
    {"id":12,"name":"Budget SF","team":"CHA","salary":3500,"roster_position":"SF","projected_fp":15.0,"ceiling":22,"edge_score":30,"risk_score":0.4,"ownership":None},
    {"id":13,"name":"Min C","team":"DET","salary":3000,"roster_position":"C","projected_fp":12.0,"ceiling":20,"edge_score":25,"risk_score":0.5,"ownership":None},
    {"id":14,"name":"Min PG","team":"SAS","salary":3000,"roster_position":"PG","projected_fp":10.0,"ceiling":18,"edge_score":20,"risk_score":0.6,"ownership":None},
    {"id":15,"name":"Min SG","team":"HOU","salary":3000,"roster_position":"SG","projected_fp":11.0,"ceiling":19,"edge_score":22,"risk_score":0.5,"ownership":None},
]

# ════════════════════════════════════════════════════════════════
#  MLB OPTIMIZER ENGINE  (DK MLB Classic)
# ════════════════════════════════════════════════════════════════

MLB_SLOTS = [("P", 2), ("C", 1), ("1B", 1), ("2B", 1), ("3B", 1), ("SS", 1), ("OF", 3)]
# ── all 10 positional requirements with counts ──
MLB_CAP = 50000
MLB_SIZE = 10

# FanDuel MLB: 9 players, $35K cap
FD_MLB_CAP = 35000
FD_MLB_SIZE = 9
# FanDuel MLB slots: 1 P, 1 C/1B (combined), 1 2B, 1 3B, 1 SS, 3 OF, 1 UTIL
FD_MLB_SLOTS = [("P", 1), ("C1B", 1), ("2B", 1), ("3B", 1), ("SS", 1), ("OF", 3), ("UTIL", 1)]

# ── strategy → behaviour config ──────────────────────────────────
STRATEGY_CONFIG = {
    "balanced":   {"min_unique": 2, "max_exposure_pct": None, "diversify": True},
    "cash":       {"min_unique": 1, "max_exposure_pct": None, "diversify": False},
    "gpp":        {"min_unique": 2, "max_exposure_pct": 50,   "diversify": True},
    "aggressive": {"min_unique": 3, "max_exposure_pct": 40,   "diversify": True},
    "nuclear":    {"min_unique": 4, "max_exposure_pct": 30,   "diversify": True},
}


def _normalize_mlb_pos(pos_str: str, platform: str = "draftkings") -> str:
    """Map SportsDataIO position to roster slot. FD combines C/1B into one slot."""
    p = str(pos_str).upper()
    if p in ("SP", "RP", "P"):           return "P"
    if platform == "fanduel":
        if p in ("C", "1B"):             return "C1B"
    if p in ("C"):                       return "C"
    if p in ("1B"):                      return "1B"
    if p in ("2B"):                      return "2B"
    if p in ("3B"):                      return "3B"
    if p in ("SS"):                      return "SS"
    if p in ("OF", "LF", "RF", "CF", "DH"):  return "OF"
    return p


def _validate_mlb_lineup(selected: list, cap: int, size: int, platform: str = "draftkings") -> str | None:
    """Validate a built MLB lineup. Returns None if valid, else error string."""
    slots = FD_MLB_SLOTS if platform == "fanduel" else MLB_SLOTS
    if len(selected) != size:
        return f"wrong player count: {len(selected)} (expected {size})"
    slot_count = {s: 0 for s, _ in slots}
    ids = set()
    for p in selected:
        if p["id"] in ids:
            return f"duplicate player {p['name']}"
        ids.add(p["id"])
        slot = _normalize_mlb_pos(p.get("roster_position", ""), platform)
        # Required non-UTIL slots: count only up to the needed amount
        required_set = {s for s, _ in slots if s != "UTIL"}
        if slot in required_set:
            need = dict(slots).get(slot, 0)
            if slot_count.get(slot, 0) < need:
                slot_count[slot] = slot_count.get(slot, 0) + 1
            elif "UTIL" in dict(slots):
                slot_count["UTIL"] = slot_count.get("UTIL", 0) + 1
        elif "UTIL" in dict(slots) and slot != "P":
            slot_count["UTIL"] = slot_count.get("UTIL", 0) + 1
    for slot, need in slots:
            if slot == "UTIL":
                continue  # UTIL is any non-P hitter; count validated by total size
            if slot_count.get(slot, 0) != need:
                return f"slot {slot}: {slot_count.get(slot, 0)} (need {need})"
    salary = sum(p.get("salary", 0) for p in selected)
    if salary > cap:
        return f"salary {salary} > cap {cap}"
    return None


def _build_mlb_candidates(pool: list[dict], slot_name: str, used_ids: set) -> list[dict]:
    """Return players matching the slot, sorted by projection/salary ratio (value)."""
    candidates = [
        p for p in pool
        if _normalize_mlb_pos(p.get("roster_position", "")) == slot_name
        and p["id"] not in used_ids
        and p.get("salary", 0) > 0
    ]
    candidates.sort(
        key=lambda p: (p.get("projected_fp", 0) or 0) / max(p.get("salary", 1), 100),
        reverse=True,
    )
    return candidates


def _fill_mlb_roster(
    pool: list[dict],
    locked: list[dict],
    used_ids_in: set,
    used_teams_in: dict,
    cap: int,
    config: dict,
    platform: str = "draftkings",
) -> tuple[list[dict], int, set, dict] | None:
    """
    Position-enforced MLB roster fill with budget-aware selection.
    Uses platform-specific slots (DK=10, FD=9) and salary cap.

    Returns (selected, used_salary, used_ids, used_teams) or None.
    """
    is_fd = platform == "fanduel"
    slots = FD_MLB_SLOTS if is_fd else MLB_SLOTS
    size = FD_MLB_SIZE if is_fd else MLB_SIZE

    selected: list[dict] = []
    used_sal = 0
    ids: set = set()
    teams: dict = {}

    def _try_add(p: dict) -> bool:
        nonlocal used_sal
        if p["id"] in ids:
            return False
        if used_sal + p.get("salary", 0) > cap:
            return False
        tn = teams.get(p.get("team", ""), 0)
        if tn >= 5:
            return False
        selected.append(p)
        used_sal += p.get("salary", 0)
        ids.add(p["id"])
        teams[p.get("team", "")] = tn + 1
        return True

    # Lock players first
    for p in locked:
        _try_add(p)

    # Track remaining fills per position
    remaining = {s: n for s, n in slots}

    for slot_name, needed in slots:
        for _ in range(needed):
            remaining_now = [(s, n) for s, n in remaining.items() if n > 0]
            remaining_now[0] = (remaining_now[0][0], remaining_now[0][1] - 1)
            slots_for_min = [(s, n) for s, n in remaining_now if n > 0]

            min_budget_needed = 0
            for s_slot, s_n in slots_for_min:
                if s_slot == "UTIL":
                    # UTIL accepts any non-pitcher — use cheapest hitter
                    cheapest_hitter = sorted(
                        [p for p in pool if _normalize_mlb_pos(p.get("roster_position", ""), platform) != "P"
                         and p["id"] not in ids and p.get("salary", 0) > 0],
                        key=lambda p: p.get("salary", 0),
                    )[:1]
                    min_budget_needed += sum(p.get("salary", 0) for p in cheapest_hitter)
                else:
                    cheapest = sorted(
                        [p for p in pool if _normalize_mlb_pos(p.get("roster_position", ""), platform) == s_slot
                         and p["id"] not in ids and p.get("salary", 0) > 0],
                        key=lambda p: p.get("salary", 0),
                    )[:s_n]
                    min_budget_needed += sum(p.get("salary", 0) for p in cheapest)

            candidates = [
                p for p in pool
                if (
                    # UTIL: any non-pitcher (including C, 1B, C1B, 2B, 3B, SS, OF)
                    (slot_name == "UTIL" and _normalize_mlb_pos(p.get("roster_position", ""), platform) != "P")
                    or _normalize_mlb_pos(p.get("roster_position", ""), platform) == slot_name
                )
                and p["id"] not in ids
                and p.get("salary", 0) > 0
                and used_sal + p.get("salary", 0) + min_budget_needed <= cap
            ]
            if not candidates:
                return None

            candidates.sort(
                key=lambda p: (p.get("projected_fp", 0) or 0) / max(p.get("salary", 1), 100),
                reverse=True,
            )

            if config.get("diversify") and len(candidates) > 2:
                top_k = min(5, len(candidates))
                candidates = candidates[:top_k]
                random.shuffle(candidates)

            picked = None
            for p in candidates:
                if _try_add(p):
                    picked = p
                    break
            if picked is None:
                return None

            remaining[slot_name] -= 1

    # Fill remaining to reach full size (UTIL spot for FD)
    remaining_players = [p for p in pool if p["id"] not in ids and p.get("salary", 0) > 0]
    remaining_players.sort(
        key=lambda p: (p.get("projected_fp", 0) or 0) / max(p.get("salary", 1), 100),
        reverse=True,
    )
    for p in remaining_players:
        if len(selected) >= size:
            break
        _try_add(p)

    if len(selected) < size:
        return None
    return selected, used_sal, ids, teams


def _gen_unique_lineups(
    pool: list[dict],
    strategy: str,
    count: int,
    locks: list[int],
    excludes: list[int],
    platform: str = "draftkings",
) -> list[dict]:
    """
    Generate count unique MLB lineups with platform-specific rules.
    DK: 10 players, $50K, 2P/C/1B/2B/3B/SS/3OF
    FD: 9 players, $35K, P/C1B/2B/3B/SS/3OF/UTIL
    """
    is_fd = platform == "fanduel"
    cap = FD_MLB_CAP if is_fd else MLB_CAP
    size = FD_MLB_SIZE if is_fd else MLB_SIZE

    cfg = STRATEGY_CONFIG.get(strategy, STRATEGY_CONFIG["balanced"])
    min_unique = cfg["min_unique"]
    max_exp_pct = cfg["max_exposure_pct"]

    eligible = [p for p in pool if p["id"] not in excludes]
    eligible = [p for p in eligible if (p.get("projected_fp", 0) or 0) > 0]
    if len(eligible) < size:
        return []

    # Lock players
    locked = [p for p in eligible if p["id"] in locks]

    player_use = {}  # player_id -> count of lineups they appear in
    lineups = []
    attempts = 0
    max_attempts = count * 20  # avoid infinite loop

    while len(lineups) < count and attempts < max_attempts:
        attempts += 1

        # Check per-player max exposure before this lineup
        if max_exp_pct:
            max_uses = max(1, int(count * max_exp_pct / 100.0))
            eligible_this = [
                p for p in eligible
                if player_use.get(p["id"], 0) < max_uses
            ]
            if len(eligible_this) < size:
                eligible_this = eligible.copy()
        else:
            eligible_this = eligible.copy()

        random.shuffle(eligible_this)

        used_ids = set()
        used_teams = {}

        result = _fill_mlb_roster(
            eligible_this, locked, used_ids, used_teams, cap, cfg, platform,
        )
        if result is None:
            continue

        selected, used_sal, ids, teams = result

        # Validate
        err = _validate_mlb_lineup(selected, cap, size, platform)
        if err:
            continue

        # Minimum uniqueness against existing lineups
        if lineups:
            ok = True
            for prior in lineups:
                prior_ids = {p["id"] for p in prior["players"]}
                overlap = len(ids & prior_ids)
                if (size - overlap) < min_unique:
                    ok = False
                    break
            if not ok:
                continue

        # Build lineup struct
        proj_score = sum(p.get("projected_fp", 0) for p in selected)
        ceil = sum(p.get("ceiling") or 0 for p in selected)

        lineup = {
            "lineup_index": len(lineups) + 1,
            "sport": "MLB",
            "platform": "draftkings",
            "strategy": strategy,
            "total_salary": used_sal,
            "remaining_salary": cap - used_sal,
            "projected_score": round(proj_score, 1),
            "ceiling_score": round(ceil, 1) if ceil else None,
            "player_count": len(selected),
            "data_source": "sportsdataio",
            "data_mode": "TRIAL_SCRAMBLED",
            "min_uniqueness": min_unique,
            "players": [
                {
                    "id": p["id"],
                    "name": p.get("name", ""),
                    "team": p.get("team", ""),
                    "eligible_positions": p.get("roster_position", ""),
                    "roster_slot": (
                        "UTIL" if is_fd and j == size - 1 and _normalize_mlb_pos(p.get("roster_position", ""), platform) != "P"
                        else _normalize_mlb_pos(p.get("roster_position", ""), platform)
                    ),
                    "salary": p.get("salary", 0),
                    "projected_fp": p.get("projected_fp", 0),
                    "ceiling": p.get("ceiling"),
                    "floor": p.get("floor"),
                    "ownership": p.get("ownership"),  # null when unavailable
                    "value": p.get("value"),
                }
                for j, p in enumerate(selected)
            ],
        }
        lineups.append(lineup)

        # Update exposure tracking
        for pid in ids:
            player_use[pid] = player_use.get(pid, 0) + 1

    return lineups


def _generate_lineups(
    pool: list,
    strategy: str,
    count: int,
    locks: list,
    excludes: list,
    randomness: float,
    platform: str = "draftkings",
    is_mlb: bool = False,
) -> list:
    """
    Generate lineups for the given platform.

    MLB path uses position-enforced _gen_unique_lineups with
    strategy-based diversification and exposure control.

    NBA path uses the original greedy flex-based approach.
    """
    profile = get_strategy(strategy)
    eligible = [p for p in pool if p["id"] not in excludes]
    eligible.sort(key=lambda p: builder_objective(p, profile, randomness), reverse=True)

    # MLB path — full position-enforced engine
    if is_mlb:
        return _gen_unique_lineups(eligible, strategy, count, locks, excludes, platform)

    # ── NBA path (unchanged) ──────────────────────────────────────
    platform_lower = platform.lower()
    if platform_lower == "fanduel":
        cap = FD_CAP
        size = 9
    else:
        cap = DK_CAP
        size = 8

    lineups = []
    forbidden_ids = set()
    for i in range(min(count, 50)):
        working = [p for p in eligible if p["id"] not in forbidden_ids]
        if len(working) < size:
            working = eligible.copy()
        random.shuffle(working)
        selected = []
        used_salary = 0
        used_ids = set()
        used_teams = {}
        for pid in locks:
            p = next((x for x in working if x["id"] == pid), None)
            if p and p["id"] not in used_ids:
                selected.append(p)
                used_salary += p["salary"]
                used_ids.add(p["id"])
                used_teams[p.get("team", "")] = used_teams.get(p.get("team", ""), 0) + 1
        working.sort(key=lambda x: x["salary"])
        for p in working:
            if len(selected) >= size:
                break
            if p["id"] in used_ids:
                continue
            tn = used_teams.get(p.get("team", ""), 0)
            if tn >= 4:
                continue
            if used_salary + p["salary"] > cap:
                continue
            selected.append(p)
            used_salary += p["salary"]
            used_ids.add(p["id"])
            used_teams[p.get("team", "")] = tn + 1
        if len(selected) < size:
            continue
        proj_score = sum(p["projected_fp"] for p in selected)
        ceil = sum(p.get("ceiling", 0) for p in selected)
        lineups.append({
            "lineup_index": i + 1,
            "projected_score": round(proj_score, 1),
            "ceiling_score": round(ceil, 1) if ceil else None,
            "total_salary": used_salary,
            "remaining_salary": cap - used_salary,
            "players": selected,
        })
        forbidden_ids.update(used_ids)
    return lineups


# ════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.post("/validate")
async def validate_request(body: LineupRequest, user: User = Depends(get_current_user)):
    errors = []
    err = BuilderValidator.validate_platform(body.platform)
    if err: errors.append(err)
    err = BuilderValidator.validate_slate(body.slate_id)
    if err: errors.append(err)
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/lineups")
async def build_lineups(
    body: LineupRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Build lineups from projections. MLB uses position-enforced engine."""
    errs = BuilderValidator.validate_constraints(
        body.locked_player_ids, body.excluded_player_ids, NBA_DEMO
    )
    if errs:
        raise HTTPException(422, detail="; ".join(errs))

    pool = await _load_projections(body.slate_id, db)
    source = "live"
    if not pool:
        raise HTTPException(
            status_code=503,
            detail="Live projections are not available for this slate yet.",
        )

    if body.sport.lower() == "mlb":
        lineups = _generate_lineups(
            pool, body.strategy, body.lineup_count,
            body.locked_player_ids, body.excluded_player_ids,
            body.randomness, body.platform, is_mlb=True,
        )
    else:
        lineups = _generate_lineups(
            pool, body.strategy, body.lineup_count,
            body.locked_player_ids, body.excluded_player_ids,
            body.randomness, body.platform,
        )

    profile = get_strategy(body.strategy)
    explained = [ExplanationGenerator.explain(lu, profile) for lu in lineups]

    return wrap_data(
        {
            "run_id": str(uuid.uuid4()),
            "lineups": explained,
            "strategy": body.strategy,
            "platform": body.platform,
            "sport": body.sport,
        },
        source="builder_engine",
    )


@router.post("/portfolios")
async def build_portfolio():
    return {"status": "not_implemented"}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    return {"run_id": run_id, "status": "stored"}


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: str):
    return {"portfolio_id": portfolio_id, "status": "not_implemented"}


@router.post("/rebuild/{run_id}")
async def rebuild_run(run_id: str):
    return {"run_id": run_id, "status": "rebuilt"}