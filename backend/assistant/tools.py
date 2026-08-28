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
        "sgo_player_id": p.get("sgo_player_id"),
        "sbme_game_total": p.get("sbme_game_total"),
        "sbme_implied_team_total": p.get("sbme_implied_team_total"),
        "sbme_environment_source": p.get("sbme_environment_source"),
        "sgo_prop_lines": p.get("sgo_prop_lines"),
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


def _league(sport: Optional[str]) -> str:
    return (sport or "MLB").upper()


async def _cached_events(sport: Optional[str] = "MLB") -> list:
    from providers.nested_events import load_cached_events
    return load_cached_events(_league(sport))


# ── Tool: get_sgo_current_events ───────────────────────────────

async def get_sgo_current_events(
    db: AsyncSession,
    sport: str = "MLB",
) -> dict:
    """Cached nested /v2/events only — no direct SportsGameOdds HTTP."""
    events = await _cached_events(sport)
    rows = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
        away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
        rows.append({
            "event_id": evt.get("id"),
            "league": evt.get("league") or _league(sport),
            "start_time": evt.get("start_time"),
            "status": evt.get("status"),
            "status_display": evt.get("status_display"),
            "home_team": home.get("abbreviation") or home.get("name"),
            "away_team": away.get("abbreviation") or away.get("name"),
            "home_score": evt.get("home_score"),
            "away_score": evt.get("away_score"),
        })
    return {
        "available": bool(rows),
        "source": "sgo_nested_cache",
        "sport": _league(sport),
        "count": len(rows),
        "events": rows,
        "note": None if rows else "No cached SportsGameOdds events. Market Tools refresh fills this cache.",
    }


# ── Tool: get_sgo_game_status ──────────────────────────────────

async def get_sgo_game_status(
    db: AsyncSession,
    event_id: Optional[str] = None,
    sport: str = "MLB",
) -> dict:
    from providers.nested_events import find_event_by_id
    events = await _cached_events(sport)
    if event_id:
        evt = find_event_by_id(events, event_id)
        events = [evt] if evt else []
    games = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
        away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
        games.append({
            "event_id": evt.get("id"),
            "status": evt.get("status"),
            "status_display": evt.get("status_display"),
            "home_team": home.get("abbreviation") or home.get("name"),
            "away_team": away.get("abbreviation") or away.get("name"),
            "home_score": evt.get("home_score"),
            "away_score": evt.get("away_score"),
            "period": evt.get("period"),
        })
    return {
        "available": bool(games),
        "source": "sgo_nested_cache",
        "games": games,
    }


# ── Tool: get_sgo_current_odds ─────────────────────────────────

async def get_sgo_current_odds(
    db: AsyncSession,
    event_id: Optional[str] = None,
    sport: str = "MLB",
) -> dict:
    from providers.nested_events import find_event_by_id, sbevent_to_game_row, sbevent_to_compare_books
    events = await _cached_events(sport)
    if event_id:
        evt = find_event_by_id(events, event_id)
        events = [evt] if evt else []
    games = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        row = sbevent_to_game_row(evt)
        row["books"] = sbevent_to_compare_books(evt)
        games.append(row)
    return {
        "available": bool(games),
        "source": "sgo_nested_cache",
        "note": "Bookmaker prices from nested event.markets. Fair odds included when present on the market.",
        "games": games,
    }


# ── Tool: get_sgo_player_props ─────────────────────────────────

async def get_sgo_player_props(
    db: AsyncSession,
    player_name: Optional[str] = None,
    player_id: Optional[str] = None,
    event_id: Optional[str] = None,
    sport: str = "MLB",
) -> dict:
    from providers.nested_events import find_event_by_id, sbevent_player_props
    events = await _cached_events(sport)
    if event_id:
        evt = find_event_by_id(events, event_id)
        events = [evt] if evt else []
    ident = player_id or player_name or ""
    props = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        props.extend(sbevent_player_props(evt, player_id=ident))
    return {
        "available": bool(props),
        "source": "sgo_nested_cache",
        "note": "SGO betting O/U thresholds. Not fantasy-point projections.",
        "props": props[:80],
    }


# ── Tool: get_player_last_n ────────────────────────────────────

async def get_player_last_n(
    db: AsyncSession,
    player_id: str,
    name: Optional[str] = None,
    team: Optional[str] = None,
    sport: str = "MLB",
    n: int = 5,
    slate_id: Optional[int] = None,
) -> dict:
    """Last-N via the existing historical /events?include=results path after ID reconcile."""
    from api.player_stats import compute_last_n
    from scoring import ScoringPlatform

    n = max(1, min(int(n or 5), 10))
    payload = await compute_last_n(
        db,
        player_id,
        n=n,
        platform="draftkings",
        sport=_league(sport),
        name=name or "",
        team=team or "",
        slate_id=slate_id,
        scoring_platform=ScoringPlatform.DRAFTKINGS,
    )
    payload["source"] = "sgo_historical"
    payload["note"] = (
        "DraftKings MLB historical scoring from finalized SportsGameOdds results. "
        "FanDuel historical scoring is not enabled."
    )
    return payload


# ── Tool: get_sbme_game_environment ────────────────────────────

async def get_sbme_game_environment(
    db: AsyncSession,
    event_id: Optional[str] = None,
    team: Optional[str] = None,
    sport: str = "MLB",
) -> dict:
    from providers.nested_events import derive_game_environment, environments_by_team, find_event_by_id
    from dfs.team_normalize import normalize_team_abbr

    events = await _cached_events(sport)
    if event_id:
        evt = find_event_by_id(events, event_id)
        if not evt:
            return {"available": False, "source": "sbme_derived", "reason": "Event not in nested cache."}
        env = derive_game_environment(evt)
        return {"available": True, "source": "sbme_derived", "environment": env}
    if team:
        by_team = environments_by_team(events)
        env = by_team.get(normalize_team_abbr(team))
        if not env:
            return {"available": False, "source": "sbme_derived", "reason": "Team not found in cached events."}
        return {"available": True, "source": "sbme_derived", "environment": env}
    envs = [derive_game_environment(e) for e in events if isinstance(e, dict)]
    return {
        "available": bool(envs),
        "source": "sbme_derived",
        "note": "SB ME derived from nested moneyline/total/spread. Not a provider-supplied fact.",
        "environments": envs,
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
    _fn_schema(
        "get_sgo_current_events",
        "List current SportsGameOdds events from SB ME's nested event cache (start time, teams, status). Cache-only; does not call SportsGameOdds directly.",
        {"sport": {"type": "string", "description": "League/sport, e.g. MLB."}},
        [],
    ),
    _fn_schema(
        "get_sgo_game_status",
        "Return game status and scores from the nested SportsGameOdds event cache.",
        {
            "event_id": {"type": "string", "description": "Optional SGO event ID."},
            "sport": {"type": "string", "description": "League/sport, e.g. MLB."},
        },
        [],
    ),
    _fn_schema(
        "get_sgo_current_odds",
        "Return current moneyline/spread/total and per-bookmaker prices from the nested event cache, including fair odds when present.",
        {
            "event_id": {"type": "string", "description": "Optional SGO event ID."},
            "sport": {"type": "string", "description": "League/sport, e.g. MLB."},
        },
        [],
    ),
    _fn_schema(
        "get_sgo_player_props",
        "Return nested SportsGameOdds player prop O/U lines (hits, HR, strikeouts, etc.). These are betting thresholds, not fantasy-point projections.",
        {
            "player_name": {"type": "string", "description": "Player name."},
            "player_id": {"type": "string", "description": "SGO player ID if known."},
            "event_id": {"type": "string", "description": "Optional SGO event ID."},
            "sport": {"type": "string", "description": "League/sport, e.g. MLB."},
        },
        [],
    ),
    _fn_schema(
        "get_player_last_n",
        "Return last-N completed games with DraftKings MLB fantasy scoring from finalized SportsGameOdds results. Resolves DFS IDs to SGO player IDs. FanDuel historical scoring is not available.",
        {
            "player_id": {"type": "string", "description": "SGO player ID, DFS sbme_player_id, or provider player ID."},
            "name": {"type": "string", "description": "Player name used for exact reconciliation."},
            "team": {"type": "string", "description": "Team abbreviation."},
            "sport": {"type": "string", "description": "Sport, default MLB."},
            "n": {"type": "integer", "description": "Number of games (1-10, default 5)."},
            "slate_id": {"type": "integer", "description": "Optional DFS slate ID to scope ID lookup."},
        },
        ["player_id"],
    ),
    _fn_schema(
        "get_sbme_game_environment",
        "Return SB ME derived game environment: game total, moneyline implied win probability, and implied team totals. These are SB ME calculations from nested markets, not SportsGameOdds-supplied facts.",
        {
            "event_id": {"type": "string", "description": "Optional SGO event ID."},
            "team": {"type": "string", "description": "Optional team abbreviation."},
            "sport": {"type": "string", "description": "League/sport, e.g. MLB."},
        },
        [],
    ),
]

# name → async handler(db, **args) -> dict
TOOL_HANDLERS = {
    "get_current_slates": get_current_slates,
    "get_slate_players": get_slate_players,
    "get_player_sb_metrics": get_player_sb_metrics,
    "get_optimal_pct": get_optimal_pct,
    "get_sgo_current_events": get_sgo_current_events,
    "get_sgo_game_status": get_sgo_game_status,
    "get_sgo_current_odds": get_sgo_current_odds,
    "get_sgo_player_props": get_sgo_player_props,
    "get_player_last_n": get_player_last_n,
    "get_sbme_game_environment": get_sbme_game_environment,
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
