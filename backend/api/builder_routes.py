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
            "ownership": proj.ownership,
            "value": proj.value,
            "leverage": proj.leverage,
        }
        for proj, player in rows
    ]
NBA_DEMO = [
    {"id":1,"name":"Luka Doncic","team":"DAL","salary":11000,"roster_position":"PG","projected_fp":55.4,"ceiling":65,"edge_score":78,"risk_score":0.1,"ownership":25},
    {"id":2,"name":"Stephen Curry","team":"GSW","salary":10500,"roster_position":"PG","projected_fp":52.1,"ceiling":60,"edge_score":72,"risk_score":0.15,"ownership":18},
    {"id":3,"name":"Nikola Jokic","team":"DEN","salary":11500,"roster_position":"C","projected_fp":60.5,"ceiling":70,"edge_score":85,"risk_score":0.05,"ownership":35},
    {"id":4,"name":"Jayson Tatum","team":"BOS","salary":10200,"roster_position":"SF","projected_fp":48.2,"ceiling":55,"edge_score":65,"risk_score":0.1,"ownership":20},
    {"id":5,"name":"Giannis Antetokounmpo","team":"MIL","salary":10800,"roster_position":"PF","projected_fp":54.0,"ceiling":62,"edge_score":80,"risk_score":0.08,"ownership":30},
    {"id":6,"name":"Bennedict Mathurin","team":"IND","salary":4500,"roster_position":"SF","projected_fp":25.0,"ceiling":35,"edge_score":45,"risk_score":0.3,"ownership":5},
    {"id":7,"name":"Kevin Durant","team":"PHX","salary":9800,"roster_position":"PF","projected_fp":44.0,"ceiling":50,"edge_score":60,"risk_score":0.12,"ownership":15},
    {"id":8,"name":"Joel Embiid","team":"PHI","salary":11300,"roster_position":"C","projected_fp":56.0,"ceiling":66,"edge_score":82,"risk_score":0.1,"ownership":28},
    {"id":9,"name":"Austin Reaves","team":"LAL","salary":6500,"roster_position":"SG","projected_fp":32.0,"ceiling":42,"edge_score":55,"risk_score":0.2,"ownership":12},
    {"id":10,"name":"Tyrese Haliburton","team":"IND","salary":9500,"roster_position":"PG","projected_fp":46.0,"ceiling":54,"edge_score":68,"risk_score":0.08,"ownership":22},
    {"id":11,"name":"Value PG","team":"ORL","salary":3800,"roster_position":"PG","projected_fp":18.0,"ceiling":25,"edge_score":35,"risk_score":0.3,"ownership":2},
    {"id":12,"name":"Budget SF","team":"CHA","salary":3500,"roster_position":"SF","projected_fp":15.0,"ceiling":22,"edge_score":30,"risk_score":0.4,"ownership":1},
    {"id":13,"name":"Min C","team":"DET","salary":3000,"roster_position":"C","projected_fp":12.0,"ceiling":20,"edge_score":25,"risk_score":0.5,"ownership":1},
    {"id":14,"name":"Min PG","team":"SAS","salary":3000,"roster_position":"PG","projected_fp":10.0,"ceiling":18,"edge_score":20,"risk_score":0.6,"ownership":1},
    {"id":15,"name":"Min SG","team":"HOU","salary":3000,"roster_position":"SG","projected_fp":11.0,"ceiling":19,"edge_score":22,"risk_score":0.5,"ownership":1},
]

def _fill_mlb_roster(pool, selected, used_salary, used_ids, used_teams, cap):
    """Fill MLB DraftKings roster with positional enforcement.
    
    DK MLB Classic: 2 P, 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 3 OF = 10 players, $50K cap.
    """
    size = 10
    # Normalize positions: SP/RP → P, map to MLB slots
    def normalize_pos(pos_str):
        p = str(pos_str).upper()
        if p in ("SP", "RP", "P"): return "P"
        if p in ("C"): return "C"
        if p in ("1B"): return "1B"
        if p in ("2B"): return "2B"
        if p in ("3B"): return "3B"
        if p in ("SS"): return "SS"
        if p in ("OF", "LF", "RF", "CF"): return "OF"
        return p  # return as-is for unknown
    
    # Slot requirements: (slot_name, count_needed)
    slots = [("P", 2), ("C", 1), ("1B", 1), ("2B", 1), ("3B", 1), ("SS", 1), ("OF", 3)]
    slot_filled = {s: 0 for s, _ in slots}
    
    for slot_name, needed in slots:
        while slot_filled[slot_name] < needed:
            # Find best available player at this position
            candidates = [
                p for p in pool
                if normalize_pos(p.get("roster_position", "")) == slot_name
                and p["id"] not in used_ids
                and p["salary"] > 0
            ]
            # Sort by value (projected_fp / salary)
            candidates.sort(
                key=lambda p: (p.get("projected_fp", 0) or 0) / max(p["salary"], 100),
                reverse=True
            )
            
            picked = None
            for p in candidates:
                if used_salary + p["salary"] > cap:
                    continue
                tn = used_teams.get(p.get("team", ""), 0)
                if tn >= 5:
                    continue
                picked = p
                break
            
            if picked is None:
                # Can't fill this slot — try picking best available any position
                # as long as we don't exceed the total size
                break
            
            selected.append(picked)
            used_salary += picked["salary"]
            used_ids.add(picked["id"])
            used_teams[picked.get("team", "")] = used_teams.get(picked.get("team", ""), 0) + 1
            slot_filled[slot_name] += 1
    
    # Fill remaining slots to reach 10 players (utility/flex spots)
    remaining = [p for p in pool if p["id"] not in used_ids and p["salary"] > 0]
    remaining.sort(key=lambda p: (p.get("projected_fp", 0) or 0) / max(p["salary"], 100), reverse=True)
    for p in remaining:
        if len(selected) >= size:
            break
        if used_salary + p["salary"] > cap:
            continue
        tn = used_teams.get(p.get("team", ""), 0)
        if tn >= 5:
            continue
        selected.append(p)
        used_salary += p["salary"]
        used_ids.add(p["id"])
        used_teams[p.get("team", "")] = tn + 1
    
    return selected, used_salary, used_ids, used_teams


def _generate_lineups(pool: list, strategy: str, count: int, locks: list, excludes: list, randomness: float, platform: str = "draftkings", is_mlb: bool = False) -> list:
    profile = get_strategy(strategy)
    eligible = [p for p in pool if p["id"] not in excludes]
    eligible.sort(key=lambda p: builder_objective(p, profile, randomness), reverse=True)

    # Platform-specific rules
    platform_lower = platform.lower()
    if is_mlb:
        cap = DK_CAP  # $50,000
        size = 10
        required_slots = ["P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "P"]
    elif platform_lower == "fanduel":
        cap = FD_CAP
        size = 9
        required_slots = ["PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C"]
    else:
        cap = DK_CAP
        size = 8
        required_slots = None  # DK NBA is flex-based

    lineups = []
    import random
    forbidden_ids = set()  # Cross-lineup uniqueness pool
    for i in range(min(count, 50)):
        working = [p for p in eligible if p["id"] not in forbidden_ids]
        if len(working) < size:
            working = eligible.copy()  # fallback if too many excluded
        random.shuffle(working)
        selected = []
        used_salary = 0
        used_ids = set()
        used_teams = {}

        # Lock players first
        for pid in locks:
            p = next((x for x in working if x["id"] == pid), None)
            if p and p["id"] not in used_ids:
                selected.append(p); used_salary += p["salary"]; used_ids.add(p["id"])
                used_teams[p.get("team","")] = used_teams.get(p.get("team",""), 0) + 1

        if is_mlb:
            # Position-enforced MLB fill
            selected, used_salary, used_ids, used_teams = _fill_mlb_roster(
                working, selected, used_salary, used_ids, used_teams, cap
            )
        else:
            # NBA: flex-based greedy fill
            working.sort(key=lambda x: x["salary"])
            for p in working:
                if len(selected) >= size: break
                if p["id"] in used_ids: continue
                tn = used_teams.get(p.get("team",""), 0)
                if tn >= 4: continue
                if used_salary + p["salary"] > cap: continue
                selected.append(p)
                used_salary += p["salary"]
                used_ids.add(p["id"])
                used_teams[p.get("team","")] = tn + 1

        if len(selected) < size:
            continue

        proj_score = sum(p["projected_fp"] for p in selected)
        ceil = sum(p.get("ceiling", 0) for p in selected)
        lineups.append({
            "lineup_index": i + 1, "projected_score": round(proj_score, 1),
            "ceiling_score": round(ceil, 1) if ceil else None,
            "total_salary": used_salary, "remaining_salary": cap - used_salary,
            "players": selected,
        })
        # Cross-lineup uniqueness: exclude all selected players from future lineups
        forbidden_ids.update(used_ids)
        if randomness > 0:
            import random; random.shuffle(eligible)
    return lineups


# ── Endpoints ────────────────────────────────────────────────

@router.post("/validate")
async def validate_request(body: LineupRequest, user: User = Depends(get_current_user)):
    errors = []
    err = BuilderValidator.validate_platform(body.platform)
    if err: errors.append(err)
    err = BuilderValidator.validate_sport(body.sport)
    if err: errors.append(err)
    errs = BuilderValidator.validate_constraints(body.locked_player_ids, body.excluded_player_ids, NBA_DEMO)
    errors.extend(errs)
    return wrap_data({"valid": len(errors) == 0, "errors": errors}, source="builder_engine")


@router.post("/lineups")
async def build_lineups(body: LineupRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    start = time.time()
    tier = _tier(user)
    limits = GATING[tier]
    if body.lineup_count > limits["max_lineups"]:
        raise HTTPException(403, f"Lineup limit: {limits['max_lineups']}. Your plan allows {limits['max_lineups']}.")
    strategies = limits["strategies"]
    if strategies != ["all"] and body.strategy not in strategies:
        raise HTTPException(403, f"Strategy '{body.strategy}' requires Pro Arena or higher.")

    errs = BuilderValidator.validate_constraints(body.locked_player_ids, body.excluded_player_ids, NBA_DEMO)
    if errs:
        raise HTTPException(422, detail="; ".join(errs))

    pool = await _load_projections(body.slate_id, db)
    source = "live"
    if not pool:
        raise HTTPException(
            status_code=503,
            detail="Live projections are not available for this slate yet. Data is being refreshed — please check back shortly.",
        )

    lineups = _generate_lineups(pool, body.strategy, body.lineup_count,
                                body.locked_player_ids, body.excluded_player_ids, body.randomness, body.platform)
    profile = get_strategy(body.strategy)
    run_id = f"run:{uuid.uuid4().hex[:12]}"
    explained = []
    for lu in lineups:
        exp = ExplanationGenerator.explain(lu, body.strategy, "7d.0.1",
                                            body.locked_player_ids, body.excluded_player_ids)
        explained.append({**lu, "explanation": exp})

    await log_audit_record(db=db, user_id=user.id, endpoint="/builder/lineups", action="build_lineups",
        request_body={"slate_id": body.slate_id, "count": body.lineup_count},
        response_body={"run_id": run_id, "lineups": len(explained)},
        model_version="7d.0.1", latency_ms=(time.time()-start)*1000, success=True)

    return wrap_data({"run_id": run_id, "lineups": explained, "strategy": body.strategy, "platform": body.platform}, source="builder_engine")


@router.post("/portfolios")
async def build_portfolio(body: PortfolioRequest, user: User = Depends(get_current_user)):
    tier = _tier(user)
    if not GATING[tier]["portfolios"]:
        raise HTTPException(403, "Portfolios require Pro Arena or higher.")
    limits = GATING[tier]
    if body.lineup_count > limits["max_lineups"]:
        raise HTTPException(403, f"Lineup limit: {limits['max_lineups']}")

    lineups = _generate_lineups(NBA_DEMO, body.strategy, body.lineup_count,
                                body.locked_player_ids, body.excluded_player_ids, body.randomness, body.platform)
    portfolio = PortfolioEngine.build_portfolio(lineups, body.strategy)
    pid = f"portfolio:{uuid.uuid4().hex[:12]}"
    return wrap_data({"portfolio_id": pid, **portfolio}, source="builder_engine")


@router.get("/strategies")
async def get_strategies():
    return wrap_data({"strategies": [{
        "name": s.name, "description": s.description,
    } for s in [get_strategy(k) for k in list_strategies()]]}, source="builder_engine")


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: User = Depends(get_current_user)):
    return wrap_data({"run_id": run_id, "status": "completed"}, source="builder_engine")


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: str, user: User = Depends(get_current_user)):
    return wrap_data({"portfolio_id": portfolio_id}, source="builder_engine")


@router.post("/rebuild/{run_id}")
async def rebuild(run_id: str, body: LineupRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await build_lineups(body, user, db)