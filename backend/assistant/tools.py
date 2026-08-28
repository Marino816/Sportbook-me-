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

import inspect
import logging
import re
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
    player_name: Optional[str] = None,
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

    pinned = None
    if player_name:
        from dfs.name_normalize import names_equal
        compact = re.sub(r"[^a-z0-9]", "", (player_name or "").lower())
        for p in pool:
            nm = p.get("name") or ""
            if names_equal(nm, player_name) or re.sub(r"[^a-z0-9]", "", nm.lower()) == compact:
                pinned = {
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
                }
                break
        if pinned:
            players = [pinned] + [p for p in players if p.get("name") != pinned.get("name")]

    return {
        "slate_id": slate_id,
        "platform": platform,
        "sport": metadata.get("sport"),
        "slate_name": metadata.get("slate_name"),
        "sort_by": sort_by,
        "count": len(players),
        "ownership_model": metadata.get("ownership", {}).get("model"),
        "requested_player": _clean(pinned) if pinned else None,
        "requested_player_found": bool(pinned) if player_name else None,
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
    from providers.sgo_rookie import normalize_league_id
    return normalize_league_id(sport)


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
        "note": None if rows else "No cached SportsGameOdds events for this league. Say the data is unavailable. Do not invent games, scores, or lines.",
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
            "results": evt.get("results"),
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
    from providers.nested_events import (
        extract_nested_consensus,
        extract_nested_fair_odds,
        find_event_by_id,
        sbevent_team_props,
        sbevent_to_compare_books,
        sbevent_to_game_row,
    )
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
        row["fair_odds"] = extract_nested_fair_odds(evt)
        row["book_consensus"] = extract_nested_consensus(evt)
        row["team_props"] = sbevent_team_props(evt)
        games.append(row)
    return {
        "available": bool(games),
        "source": "sgo_nested_cache",
        "note": (
            "Bookmaker prices, fairOdds, bookOdds consensus, and team props from nested event.markets."
            if games
            else "Current market data is not in the SportsGameOdds cache. Say it is unavailable. Do not substitute general knowledge for current odds, Fair Odds, consensus, or bookmaker availability."
        ),
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


# ── Tool: get_sgo_team_props ───────────────────────────────────

async def get_sgo_team_props(
    db: AsyncSession,
    event_id: Optional[str] = None,
    sport: str = "MLB",
) -> dict:
    from providers.nested_events import find_event_by_id, sbevent_team_props
    events = await _cached_events(sport)
    if event_id:
        evt = find_event_by_id(events, event_id)
        events = [evt] if evt else []
    props = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        props.extend(sbevent_team_props(evt))
    return {
        "available": bool(props),
        "source": "sgo_nested_cache",
        "note": "Team totals (home/away O/U), distinct from game totals and player props.",
        "team_props": props[:80],
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
    """Last-N via finalized /v2/events?expandResults=true after ID reconcile."""
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


# ── Tool: resolve_player_on_slate ──────────────────────────────

async def resolve_player_on_slate(
    db: AsyncSession,
    slate_id: int,
    player_name: str,
    platform: str = "draftkings",
) -> dict:
    """Resolve a player name against a published slate. Never invent eligibility."""
    from dfs.canonical import build_canonical_pool
    from dfs.name_normalize import names_equal, fold_player_name
    from dfs.db import DFSPlayer

    slate = await _get_published_slate(db, slate_id)
    if not slate:
        return {"found": False, "error": f"Slate {slate_id} not found or not published"}

    target = fold_player_name(player_name)
    compact = re.sub(r"[^a-z0-9]", "", target)
    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    rows = pool or []
    if not rows:
        q = await db.execute(select(DFSPlayer).where(DFSPlayer.slate_id == slate_id))
        rows = [{
            "id": p.sbme_player_id or p.provider_player_id,
            "name": p.player_name,
            "position": p.position,
            "team": p.team,
            "opponent": p.opponent,
            "salary": p.salary,
            "projected_fp": None,
            "value": None,
            "sbme_ownership_pct": None,
            "leverage": None,
            "ceiling": None,
            "floor": None,
        } for p in q.scalars().all()]

    found = None
    for p in rows:
        nm = p.get("name") or ""
        if names_equal(nm, player_name) or re.sub(r"[^a-z0-9]", "", fold_player_name(nm)) == compact:
            found = p
            break

    display_name = (found.get("name") if found else None) or player_name
    if not found:
        return {
            "found": False,
            "player_name": display_name,
            "slate_id": slate_id,
            "slate_name": slate.slate_name,
            "sport": slate.sport,
            "platform": slate.platform,
            "message": f"{display_name} is not in this selected slate.",
        }

    return _clean({
        "found": True,
        "player_id": found.get("id"),
        "name": display_name,
        "position": found.get("roster_position") or found.get("position"),
        "team": found.get("team"),
        "opponent": found.get("opponent"),
        "salary": found.get("salary"),
        "projected_fp": found.get("projected_fp"),
        "value": found.get("value"),
        "sbme_ownership_pct": found.get("sbme_ownership_pct"),
        "leverage": found.get("leverage"),
        "ceiling": found.get("ceiling"),
        "floor": found.get("floor"),
        "projection_source": found.get("projection_source"),
        "slate_id": slate_id,
        "slate_name": slate.slate_name,
        "sport": slate.sport,
        "platform": slate.platform,
    })


# ── Tool: build_optimizer_lineup ───────────────────────────────

async def build_optimizer_lineup(
    db: AsyncSession,
    slate_id: int,
    platform: str = "draftkings",
    sport: str = "MLB",
    locked_player_ids: Optional[list] = None,
    excluded_player_ids: Optional[list] = None,
    strategy: str = "balanced",
) -> dict:
    """Build one lineup from the canonical pool via MLBOptimizer. No invented players."""
    from dfs.canonical import build_canonical_pool
    from dfs.optimal_lock import is_slate_locked, slate_lock_status
    from assistant.session_state import build_optimizer_handoff_href, ConversationContext, PlayerRef

    slate = await _get_published_slate(db, slate_id)
    if not slate:
        return {"ok": False, "error": f"Slate {slate_id} not found or not published"}

    platform = (platform or slate.platform or "draftkings").lower()
    sport = (sport or slate.sport or "MLB").upper()
    lock_status = slate_lock_status(slate.start_time).value
    locked = is_slate_locked(slate.start_time)
    handoff_ctx = ConversationContext(
        sport=sport,
        platform=platform,
        slate_id=slate_id,
        slate_name=slate.slate_name,
        slate_status="LOCKED" if locked else "UNLOCKED",
        locked_players=[PlayerRef(name=str(x)) for x in (locked_player_ids or []) if x],
    )
    href = build_optimizer_handoff_href(handoff_ctx)

    if locked:
        return {
            "ok": False,
            "can_optimize": False,
            "slate_id": slate_id,
            "slate_name": slate.slate_name,
            "slate_status": "LOCKED",
            "lock_status": lock_status,
            "optimizer_url": href,
            "note": (
                f"{slate.slate_name} is LOCKED. You can still analyze the pool, "
                "but new contest lineup submission/optimization may no longer be useful for entry."
            ),
        }

    if sport != "MLB":
        return {
            "ok": False,
            "can_optimize": False,
            "slate_id": slate_id,
            "sport": sport,
            "platform": platform,
            "optimizer_url": href,
            "note": (
                f"Direct AI lineup generation currently supports MLB. "
                f"Open the Optimizer for {sport}."
            ),
        }

    locks = [str(x) for x in (locked_player_ids or []) if x is not None and str(x).strip()]
    excludes = [str(x) for x in (excluded_player_ids or []) if x is not None and str(x).strip()]

    unresolved = []
    if locks:
        for lock in locks:
            resolved = await resolve_player_on_slate(db, slate_id, lock, platform=platform)
            if not resolved.get("found"):
                unresolved.append(lock)
        if unresolved:
            name = unresolved[0]
            return {
                "ok": False,
                "can_optimize": False,
                "slate_id": slate_id,
                "slate_name": slate.slate_name,
                "missing_locks": unresolved,
                "message": f"{name} is not in this selected slate.",
                "optimizer_url": href,
            }

    pool, metadata = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=False)
    if not pool or len(pool) < 10:
        return {
            "ok": False,
            "can_optimize": False,
            "slate_id": slate_id,
            "error": metadata.get("error") or "Player pool is too small to optimize.",
            "optimizer_url": href,
        }

    try:
        from optimizer.mlb_optimizer import MLBOptimizer
        opt = MLBOptimizer(
            pool,
            platform=platform,
            strategy=strategy or "balanced",
            locks=locks,
            excludes=excludes,
        )
        lineups = opt.generate(count=1)
    except Exception as e:
        logger.warning(f"AI optimizer failed: {e}")
        return {
            "ok": False,
            "can_optimize": True,
            "slate_id": slate_id,
            "error": f"Optimizer could not complete: {e}",
            "optimizer_url": href,
        }

    if not lineups:
        return {
            "ok": False,
            "can_optimize": True,
            "slate_id": slate_id,
            "error": "Optimizer returned no legal lineup for these locks/constraints.",
            "optimizer_url": href,
        }

    lu = lineups[0]
    players_out = []
    for pl in lu.get("players") or []:
        players_out.append({
            "name": pl.get("name"),
            "team": pl.get("team"),
            "salary": pl.get("salary"),
            "projected_fp": pl.get("projected_fp"),
            "roster_slot": pl.get("roster_slot") or pl.get("position"),
            "id": pl.get("id"),
        })
    return _clean({
        "ok": True,
        "can_optimize": True,
        "source": "native",
        "sport": sport,
        "platform": platform,
        "slate_id": slate_id,
        "slate_name": slate.slate_name,
        "slate_status": "UNLOCKED",
        "lock_status": lock_status,
        "strategy": strategy or "balanced",
        "locked_players": locks,
        "total_salary": lu.get("total_salary"),
        "projected_score": lu.get("projected_score"),
        "remaining_salary": lu.get("remaining_salary"),
        "solver_status": lu.get("solver_status"),
        "players": players_out,
        "optimizer_url": href,
        "note": (
            f"Built a {platform} {sport} lineup for {slate.slate_name}"
            + (f" with {', '.join(locks)} locked." if locks else ".")
        ),
    })


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
        "Return SB ME modeled metrics for a slate's players: SB Projection, Value, SB OWN% (modeled ownership), Leverage, Ceiling, Floor. Use for 'best value', 'highest projection', 'leverage', 'ownership', or 'SB ME metrics' questions. If session state has a locked player, pass player_name so that player is pinned first.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
            "sort_by": {"type": "string", "enum": ["projected_fp", "value", "sbme_ownership_pct", "leverage", "salary"], "description": "Metric to sort by (descending)."},
            "top_n": {"type": "integer", "description": "Number of top players to return (default 25, max 60)."},
            "player_name": {"type": "string", "description": "Optional player to pin at the top of the results."},
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
        {"sport": {"type": "string", "description": "League ID, e.g. MLB, EPL, UEFA_CHAMPIONS_LEAGUE, UCL."}},
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
        "Return current moneyline/spread/total, per-bookmaker prices, fairOdds, bookOdds consensus, and team props from the nested event cache.",
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
        "get_sgo_team_props",
        "Return nested SportsGameOdds team-prop markets (home/away totals). Distinct from game totals and player props.",
        {
            "event_id": {"type": "string", "description": "Optional SGO event ID."},
            "sport": {"type": "string", "description": "League/sport, e.g. MLB or EPL."},
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
    _fn_schema(
        "resolve_player_on_slate",
        "Resolve a player name against a selected DFS slate. Returns canonical id and SB ME metrics if the player is on the slate. If not found, returns found=false — never invent eligibility.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "player_name": {"type": "string", "description": "Player name to resolve."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
        },
        ["slate_id", "player_name"],
    ),
    _fn_schema(
        "build_optimizer_lineup",
        "Build one DFS lineup with the SB ME optimizer for a known sport/platform/slate. Lock players if provided. Use when the customer asks to build/optimize a lineup and session state already has sport, platform, and slate_id. Do not call if those are missing.",
        {
            "slate_id": {"type": "integer", "description": "The slate ID."},
            "platform": {"type": "string", "enum": ["draftkings", "fanduel"], "description": "DFS platform."},
            "sport": {"type": "string", "description": "Sport, e.g. MLB."},
            "locked_player_ids": {"type": "array", "items": {"type": "string"}, "description": "Player names or IDs to lock."},
            "excluded_player_ids": {"type": "array", "items": {"type": "string"}, "description": "Player names or IDs to exclude."},
            "strategy": {"type": "string", "enum": ["balanced", "cash", "gpp", "aggressive", "nuclear"], "description": "Optimizer strategy."},
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
    "get_sgo_current_events": get_sgo_current_events,
    "get_sgo_game_status": get_sgo_game_status,
    "get_sgo_current_odds": get_sgo_current_odds,
    "get_sgo_player_props": get_sgo_player_props,
    "get_sgo_team_props": get_sgo_team_props,
    "get_player_last_n": get_player_last_n,
    "get_sbme_game_environment": get_sbme_game_environment,
    "resolve_player_on_slate": resolve_player_on_slate,
    "build_optimizer_lineup": build_optimizer_lineup,
}

ALLOWED_TOOLS = frozenset(TOOL_HANDLERS.keys())


async def execute_tool(name: str, arguments: dict, db: AsyncSession) -> dict:
    """Execute an allow-listed tool by name. Returns a JSON-safe dict."""
    if name not in TOOL_HANDLERS:
        return {"error": f"Unknown tool: {name}"}
    try:
        handler = TOOL_HANDLERS[name]
        args = dict(arguments or {})
        sig = inspect.signature(handler)
        allowed = {k for k in sig.parameters if k != "db"}
        filtered = {k: v for k, v in args.items() if k in allowed}
        result = await handler(db, **filtered)
        return _clean(result) if isinstance(result, dict) else {"result": _clean(result)}
    except TypeError as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:  # never let a tool crash the request
        logger.warning(f"Tool {name} failed: {e}")
        return {"error": f"Tool {name} failed: {e}"}
