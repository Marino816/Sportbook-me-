"""
SB ME AI — read-only tool registry.

The only tools the assistant may call.  Each is:
  - allow-listed (this module is the sole source of executable tools)
  - read-only (never writes to DB/Redis/provider)
  - server-side (runs in the FastAPI process, not the client)
  - schema-validated (arguments parsed defensively)

Tools reuse the canonical SB ME services (dfs.db, dfs.canonical,
dfs.optimal_cache, dfs.optimal_lock) — never raw Blue Collar feeds.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dfs.db import DFSSlate, DFSPlayer

logger = logging.getLogger(__name__)

MAX_PLAYERS = 100
MAX_METRICS = 60


# ── Helpers ────────────────────────────────────────────────────

def _clean(value: Any) -> Any:
    """Make a value JSON-safe (handle None and non-serializable types)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return str(value)


async def _get_published_slate(db: AsyncSession, slate_id: int) -> Optional[DFSSlate]:
    r = await db.execute(
        select(DFSSlate).where(DFSSlate.id == slate_id, DFSSlate.status == "PUBLISHED")
    )
    return r.scalars().first()


# ── Tool: get_current_slates ───────────────────────────────────

async def get_current_slates(
    db: AsyncSession,
    sport: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    """List currently published DFS slates, optionally filtered."""
    q = select(DFSSlate).where(DFSSlate.status == "PUBLISHED")
    if platform:
        q = q.where(DFSSlate.platform == platform.lower())
    if sport:
        q = q.where(DFSSlate.sport == sport.upper())
    q = q.order_by(DFSSlate.start_time.asc())
    r = await db.execute(q)
    slates = r.scalars().all()

    from dfs.optimal_lock import is_slate_locked

    result = []
    for s in slates:
        start = s.start_time
        result.append({
            "slate_id": s.id,
            "sport": s.sport,
            "platform": s.platform,
            "slate_name": s.slate_name,
            "start_time": start.isoformat() if start else None,
            "locked": is_slate_locked(start),
            "player_count": s.player_count or 0,
        })
    return {"slates": result, "count": len(result)}


# ── Tool: get_slate_players ────────────────────────────────────

async def get_slate_players(
    db: AsyncSession,
    slate_id: int,
    platform: str = "draftkings",
    position: Optional[str] = None,
    team: Optional[str] = None,
    max_salary: Optional[int] = None,
    min_salary: Optional[int] = None,
) -> dict:
    """Return a slate's player pool with the same effective SB projection
    policy used by the optimizer (canonical pool)."""
    from dfs.canonical import build_canonical_pool
    from dfs.team_normalize import normalize_team_abbr, teams_equivalent

    slate = await _get_published_slate(db, slate_id)
    if not slate:
        return {"error": f"Slate {slate_id} not found or not published"}

    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=False)
    if not pool:
        # Tiny/unpublished-shape slates still return identity + fppg via the same policy.
        q = select(DFSPlayer).where(DFSPlayer.slate_id == slate_id)
        r = await db.execute(q)
        rows = r.scalars().all()
        if not rows:
            return {"error": metadata.get("error", f"Slate {slate_id} not found or not published")}
        from projection.native import apply_projection_policy
        pool = apply_projection_policy([{
            "id": p.sbme_player_id or p.provider_player_id,
            "name": p.player_name,
            "position": p.position,
            "roster_position": p.position,
            "eligible_positions": p.eligible_positions or [p.position],
            "team": p.team,
            "opponent": p.opponent,
            "salary": p.salary,
            "fppg": p.fppg,
            "projected_fp": 0.0,
            "projection_source": "UNAVAILABLE",
        } for p in rows])

    want_pos = position.upper() if position else None
    want_team = normalize_team_abbr(team) if team else None
    filtered = []
    for p in pool:
        pos = (p.get("roster_position") or p.get("position") or "").upper()
        elig = [str(x).upper() for x in (p.get("eligible_positions") or [])]
        pteam = normalize_team_abbr(p.get("team"))
        salary = int(p.get("salary") or 0)
        if want_pos and pos != want_pos and want_pos not in elig:
            continue
        if want_team and not teams_equivalent(pteam, want_team):
            continue
        if max_salary is not None and salary > max_salary:
            continue
        if min_salary is not None and salary < min_salary:
            continue
        filtered.append(p)
        if len(filtered) >= MAX_PLAYERS:
            break

    return {
        "slate_id": slate_id,
        "platform": slate.platform,
        "sport": slate.sport,
        "slate_name": slate.slate_name,
        "count": len(filtered),
        "players": _clean([{
            "player_id": p.get("id"),
            "name": p.get("name"),
            "position": p.get("roster_position") or p.get("position"),
            "team": p.get("team"),
            "opponent": p.get("opponent"),
            "salary": p.get("salary"),
            "projected_fp": p.get("projected_fp"),
            "projection_source": p.get("projection_source"),
            "mlb_pitcher_eligible": p.get("mlb_pitcher_eligible"),
            "fppg": p.get("fppg"),
        } for p in filtered]),
    }


# ── Tool: get_player_sb_metrics ────────────────────────────────

async def get_player_sb_metrics(
    db: AsyncSession,
    slate_id: int,
    platform: str = "draftkings",
    sort_by: str = "projected_fp",
    top_n: int = 25,
) -> dict:
    """Return SB ME modeled metrics (projection, value, ownership, leverage,
    ceiling/floor) for a slate's players. Uses the canonical pool."""
    from dfs.canonical import build_canonical_pool

    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    if not pool:
        return {"error": metadata.get("error", "Slate not found or not published")}

    valid_sorts = {"projected_fp", "value", "sbme_ownership_pct", "leverage", "salary"}
    sort_by = sort_by if sort_by in valid_sorts else "projected_fp"
    top_n = max(1, min(top_n, MAX_METRICS))

    ordered = sorted(
        pool,
        key=lambda p: float(p.get(sort_by) or 0),
        reverse=True,
    )[:top_n]

    players = [{
        "player_id": p.get("id"),
        "name": p.get("name"),
        "position": p.get("roster_position") or p.get("position"),
        "team": p.get("team"),
        "opponent": p.get("opponent"),
        "salary": p.get("salary"),
        "projected_fp": p.get("projected_fp"),
        "value": p.get("value"),
        "bc_value": p.get("bc_value"),
        "bc_beta_proj": p.get("bc_beta_proj"),
        "sbme_ownership_pct": p.get("sbme_ownership_pct"),
        "leverage": p.get("leverage"),
        "ceiling": p.get("ceiling"),
        "floor": p.get("floor"),
        "projection_source": p.get("projection_source"),
    } for p in ordered]

    return {
        "slate_id": slate_id,
        "platform": platform,
        "sport": metadata.get("sport"),
        "slate_name": metadata.get("slate_name"),
        "sort_by": sort_by,
        "count": len(players),
        "ownership_model": metadata.get("ownership", {}).get("model"),
        "players": _clean(players),
    }


# ── Tool: get_optimal_pct ──────────────────────────────────────

async def get_optimal_pct(
    db: AsyncSession,
    slate_id: int,
    platform: str = "draftkings",
    sport: str = "MLB",
    top_n: int = 25,
) -> dict:
    """Return Optimal% for a slate (only while unlocked). Respects lock gate."""
    import dfs.optimal_cache as ocache
    from dfs.optimal_lock import is_slate_locked, slate_lock_status

    slate = await _get_published_slate(db, slate_id)
    if slate is None:
        return {"slate_id": slate_id, "status": "UNKNOWN", "error": "Slate not found or not published"}

    lock_status = slate_lock_status(slate.start_time)
    if is_slate_locked(slate.start_time):
        return {
            "slate_id": slate_id,
            "status": "LOCKED",
            "lock_status": lock_status.value,
            "note": "Optimal% is not available for locked/in-progress slates.",
        }

    status = ocache.get_status(platform, sport.upper(), slate_id)
    result = ocache.get_result(platform, sport.upper(), slate_id)

    if status != ocache.STATUS_COMPLETE or not result:
        return {
            "slate_id": slate_id,
            "status": status,
            "note": "Optimal% has not been computed yet for this slate.",
        }

    players = result.get("players") or []
    ordered = sorted(
        players,
        key=lambda p: float(p.get("optimal_pct") or 0),
        reverse=True,
    )[: max(1, min(top_n, MAX_METRICS))]

    n_completed = result.get("n_completed")
    n_requested = result.get("n_requested")

    return {
        "slate_id": slate_id,
        "platform": platform,
        "sport": sport.upper(),
        "status": "COMPLETE",
        "n_requested": n_requested,
        "n_completed": n_completed,
        # Explicit denominator alias so the model always reports exact counts.
        "simulation_count": n_completed,
        "inputs_hash": result.get("inputs_hash"),
        "generated_at": result.get("generated_at"),
        "note": (
            "appearances = number of completed simulations in which the player "
            "appeared in the optimal (highest-scoring) lineup. "
            "optimal_pct = appearances / n_completed * 100. Report exact counts "
            "(e.g. '440 of 500') — do not round to an approximate fraction."
        ),
        "top_players": [{
            "name": p.get("name"),
            "position": p.get("position") or p.get("roster_position"),
            "team": p.get("team"),
            "optimal_pct": p.get("optimal_pct"),
            "appearances": p.get("appearances"),
            "appearances_numerator": p.get("appearances"),
            "simulation_denominator": n_completed,
        } for p in ordered],
    }


# ── Registry (name → schema + handler) ─────────────────────────

def _fn_schema(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOLS = [
    _fn_schema(
        "get_current_slates",
        "List currently published DFS slates with sport, platform, start/lock time, and player count.",
        {
            "sport": {"type": "string", "description": "Optional sport filter, e.g. MLB, NBA, NFL."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "Optional platform filter."},
        },
        [],
    ),
    _fn_schema(
        "get_slate_players",
        "Return a slate's player pool: name, position, team, opponent, and salary. Use for 'who is on this slate' or salary-filtered questions.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
            "position": {"type": "string", "description": "Optional position filter (e.g. P, OF, 1B)."},
            "team": {"type": "string", "description": "Optional team filter."},
            "min_salary": {"type": "integer", "description": "Optional minimum salary."},
            "max_salary": {"type": "integer", "description": "Optional maximum salary."},
        },
        ["slate_id"],
    ),
    _fn_schema(
        "get_player_sb_metrics",
        "Return SB ME modeled metrics for a slate's players: SB Projection, Value, SB OWN% (modeled ownership), Leverage, Ceiling, Floor. Use for 'best value', 'highest projection', 'leverage', or 'ownership' questions.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
            "sort_by": {"type": "string", "enum": ["projected_fp", "value", "sbme_ownership_pct", "leverage", "salary"], "description": "Metric to sort by (descending)."},
            "top_n": {"type": "integer", "description": "Number of top players to return (default 25, max 60)."},
        },
        ["slate_id"],
    ),
    _fn_schema(
        "get_optimal_pct",
        "Return Optimal% (share of SB ME's 500 simulations where the player appeared in the top lineup) for a slate. Only available while the slate is unlocked.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
            "sport": {"type": "string", "description": "Sport (e.g. MLB)."},
            "top_n": {"type": "integer", "description": "Number of top players to return (default 25, max 60)."},
        },
        ["slate_id"],
    ),
]

# name → async handler(db, **args) -> dict
TOOL_HANDLERS = {
    "get_current_slates": get_current_slates,
    "get_slate_players": get_slate_players,
    "get_player_sb_metrics": get_player_sb_metrics,
    "get_optimal_pct": get_optimal_pct,
}

ALLOWED_TOOLS = frozenset(TOOL_HANDLERS.keys())


async def execute_tool(name: str, arguments: dict, db: AsyncSession) -> dict:
    """Execute an allow-listed tool by name. Returns a JSON-safe dict."""
    if name not in TOOL_HANDLERS:
        return {"error": f"Unknown tool: {name}"}
    try:
        handler = TOOL_HANDLERS[name]
        result = await handler(db, **arguments)
        return _clean(result) if isinstance(result, dict) else {"result": _clean(result)}
    except TypeError as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:  # never let a tool crash the request
        logger.warning(f"Tool {name} failed: {e}")
        return {"error": f"Tool {name} failed: {e}"}
