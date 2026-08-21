from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Dict, Any
import logging

from models.database import get_db
from models.schemas import LineupRequest, LineupResponse, ProjectionSchema
from models.domain import Projection, LineupHistory, Player, User, Subscription
from optimizer.core import DFSOptimizer
from api.utils import wrap_data
from api.auth import get_current_user
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/projections/{slate_id}")
async def get_slate_projections(slate_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch all player projections with player metadata."""
    query = select(Projection, Player).join(Player).where(Projection.slate_id == slate_id)
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        return wrap_data([], source="live")
    
    projections = []
    for proj, player in rows:
        d = {c.name: getattr(proj, c.name) for c in proj.__table__.columns}
        d["name"] = player.name
        d["team"] = player.team
        projections.append(d)
        
    return wrap_data(projections, source="live")

@router.post("/optimize")
async def run_optimizer(
    request: LineupRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Run the DFS Optimizer Engine with SaaS feature gating for multi-lineup generation."""
    # Enforce Subscription Limits
    max_lineups = 1  # Default for Free users

    # Admin and QA bootstrap accounts get full access for testing
    is_admin = user.role == "admin"
    
    if is_admin:
        max_lineups = 150
    elif user.is_pro and user.active_subscription_id:
        # Query matching subscription for tier check
        sub_result = await db.execute(select(Subscription).where(Subscription.id == user.active_subscription_id))
        sub = sub_result.scalars().first()
        
        if sub and sub.plan_name == "Elite Stack":
            max_lineups = 150
        elif sub and sub.plan_name == "Pro Arena":
            max_lineups = 20
            
    requested_lineups = request.settings.get("num_lineups", 1) if isinstance(request.settings, dict) else getattr(request.settings, 'num_lineups', 1)
    
    if requested_lineups > max_lineups:
        raise HTTPException(
            status_code=403, 
            detail=f"Subscription limit exceeded. Your current plan allows max {max_lineups} lineups. Upgrade at /billing to generate {requested_lineups}."
        )

    is_native = False
    dfs_source = "native"

    # Try native DFS slate first
    try:
        from dfs.db import DFSSlate as NativeSlate, DFSPlayer as NativePlayer
        native_result = await db.execute(
            select(NativeSlate).where(NativeSlate.id == request.slate_id, NativeSlate.status == "PUBLISHED")
        )
        native_slate = native_result.scalars().first()
        if native_slate:
            # ── Server-side freshness gate ──
            # A stale (past-date) published slate must never generate or
            # save a lineup.  Reject it at the API layer so a client that
            # bypasses the frontend *is_current* filter cannot create
            # lineups from out-of-date salaries.
            from dfs.freshness import is_stale_slate

            if is_stale_slate(native_slate.start_time):
                slate_d = (
                    native_slate.start_time.date().isoformat()
                    if native_slate.start_time
                    else "unknown"
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Slate '{native_slate.slate_name}' is stale "
                        f"(slate date {slate_d}). Please upload or select "
                        f"a current {native_slate.platform} slate."
                    ),
                )

            sport = native_slate.sport.upper()
            platform = request.settings.get("platform", native_slate.platform) if isinstance(request.settings, dict) else getattr(request.settings, 'platform', native_slate.platform)

            players_result = await db.execute(
                select(NativePlayer).where(NativePlayer.slate_id == native_slate.id)
            )
            native_players = players_result.scalars().all()

            projections_list = []
            for np in native_players:
                projections_list.append({
                    "id": np.sbme_player_id or np.provider_player_id,
                    "name": np.player_name,
                    "team": np.team,
                    "position": np.position,
                    "salary": np.salary,
                    "eligible_positions": np.eligible_positions or [np.position],
                    "projected_fp": 0.0,  # filled by projection engine below
                    "opponent": np.opponent or "",
                    "mapping_status": np.mapping_status,
                })

            if len(projections_list) >= 10:
                is_native = True
                dfs_source = "native"

                # Compute native projections from SGO intelligence
                try:
                    from projection.native import compute_projections, projections_to_pool
                    from projection.sgo_intelligence import build_sgo_intelligence

                    # Fetch SGO prop data from cached events for real projections
                    # DATE-SAFE: restrict SGO events to the slate's own game date.
                    slate_date = native_slate.start_time.date().isoformat() if native_slate.start_time else None
                    sgo_intel = await build_sgo_intelligence(sport, projections_list, event_date=slate_date)
                    projs = compute_projections(sport, projections_list, sgo_intelligence=sgo_intel)
                    projected_count = sum(1 for p in projs if p.projection_source != "UNAVAILABLE")
                    projections_list = projections_to_pool(projs)
                    logger.info(f"Native projections: {projected_count}/{len(projections_list)} projected")

                    # UNAVAILABLE players stay at 0.0 projected_fp — the
                    # optimizer can still select them based on salary/value
                    # but they do not contribute to total-fp selection bias.
                    # They are not silently boosted with a fake 0.01 weight.

                    # Require a minimum number of actually-projected players
                    # to build a meaningful optimized lineup. Without enough
                    # legitimate projections the result is random roster fill.
                    MIN_PROJECTED = 10
                    if projected_count < MIN_PROJECTED:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"Only {projected_count}/{len(projections_list)} players "
                                f"have projection data available for {native_slate.slate_name}. "
                                f"At least {MIN_PROJECTED} projected players are required "
                                f"to generate a meaningful optimized lineup."
                            ),
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.warning(f"Native projection engine unavailable: {e}")
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Projection engine could not compute projections for "
                            f"'{native_slate.slate_name}': {e}. "
                            f"Ensure the SGO data cache is populated for {sport}."
                        ),
                    )
    except HTTPException:
        raise
    except Exception:
        pass

    # Legacy SportsDataIO fallback
        if not is_native:
            projections_dicts = await get_slate_projections(request.slate_id, db)

            # Determine sport from slate for roster requirements
            from models.domain import Slate as SlateModel
            slate_result = await db.execute(select(SlateModel).where(SlateModel.id == request.slate_id))
            slate = slate_result.scalars().first()
            if not slate:
                raise HTTPException(status_code=400, detail=f"Slate {request.slate_id} not found.")
            sport = slate.sport.upper()
            min_players = 10 if sport == "MLB" else 8

            if isinstance(projections_dicts, dict) and "data" in projections_dicts:
                projections_list = projections_dicts["data"]
            else:
                projections_list = projections_dicts

            if len(projections_list) < min_players:
                raise HTTPException(status_code=400, detail=f"Not enough players in projection pool ({len(projections_list)}/{min_players} needed for {sport}.)")

    # MLB uses the builder's platform-aware roster generator
    if sport == "MLB":
        from api.builder_routes import _generate_lineups, _normalize_platform, get_strategy as builder_strategy
        settings = request.settings
        platform = _normalize_platform(settings.get("platform", "draftkings") if isinstance(settings, dict) else getattr(settings, 'platform', 'draftkings'))
        strategy = settings.get("strategy", "balanced") if isinstance(settings, dict) else getattr(settings, 'strategy', 'balanced')

        def _sget(key, default=None):
            return settings.get(key, default) if isinstance(settings, dict) else getattr(settings, key, default)

        locks = _sget("locked_player_ids", []) or []
        excludes = _sget("excluded_player_ids", []) or []
        constraints = {
            "max_hitters_per_team": _sget("max_hitters_per_team"),
            "stack_size": _sget("stack_size"),
            "pitcher_conflict": _sget("pitcher_conflict"),
            "min_salary": _sget("min_salary"),
            "max_salary": _sget("max_salary"),
            "max_exposure_pct": _sget("max_exposure_pct"),
        }

        # Apply customer "My Projection" overrides (keyed by player name)
        projection_overrides = _sget("projection_overrides", []) or []
        if projection_overrides:
            override_by_name = {}
            for ov in projection_overrides:
                if isinstance(ov, dict) and ov.get("name"):
                    try:
                        override_by_name[str(ov["name"]).strip().lower()] = float(ov.get("projected_fp", 0))
                    except (ValueError, TypeError):
                        continue
            if override_by_name:
                for pl in projections_list:
                    nm = (pl.get("name") or "").strip().lower()
                    if nm in override_by_name:
                        pl["projected_fp"] = override_by_name[nm]

        pool = projections_list
        lineups = _generate_lineups(
            pool, strategy, requested_lineups,
            locks, excludes, 0.0, platform,
            is_mlb=True, constraints=constraints,
        )
        # Format response using actual builder field names
        formatted = []
        for lu in lineups:
            formatted.append({
                "total_salary": lu.get("total_salary", 0),
                "projected_score": lu.get("projected_score", 0),
                "remaining_salary": lu.get("remaining_salary", 0),
                "players": lu.get("players", []),
            })

        # Save to lineup history (non-critical)
        history_saved = False
        if formatted:
            try:
                history_payload = jsonable_encoder(formatted)
                hist = LineupHistory(
                    user_id=user.id,
                    sport=sport,
                    platform=platform,
                    slate_id=request.slate_id,
                    strategy=strategy,
                    lineup_count=len(formatted),
                    player_count=len(formatted[0].get("players", [])),
                    total_salary=int(formatted[0].get("total_salary", 0)),
                    projected_score=float(formatted[0].get("projected_score", 0)),
                    data_mode="native",
                    lineups_json=history_payload,
                )
                db.add(hist)
                await db.commit()
                history_saved = True
            except Exception as e:
                import logging
                logging.warning(f"Lineup history save failed: {type(e).__name__}: {e}")

        return wrap_data({
                    "lineups": formatted,
                    "source": "native",
                    "sport": sport,
                    "platform": platform,
                    "requested_lineups": requested_lineups,
                    "generated_lineups": len(formatted),
                    "history_saved": history_saved,
                    "dfs_source": dfs_source,
                    "slate_id": request.slate_id,
                    "pool": [
                        {
                            "id": str(p.get("id", "")),
                            "name": p.get("name", ""),
                            "position": p.get("roster_position") or p.get("position", ""),
                            "team": p.get("team", ""),
                            "opponent": p.get("opponent", ""),
                            "salary": p.get("salary", 0),
                            "projected_fp": p.get("projected_fp", 0.0),
                            "projection_source": p.get("projection_source", "UNAVAILABLE"),
                        }
                        for p in projections_list
                    ],
                }, source="builder_engine")

    # NBA path — DFSOptimizer

    df = pd.DataFrame(projections_list)
    if 'id' not in df.columns and 'player_id' in df.columns:
        df['id'] = df['player_id']
        
    optimizer = DFSOptimizer(df, request.settings.model_dump() if hasattr(request.settings, 'model_dump') else request.settings)
    results = optimizer.generate()
    
    if not results:
        raise HTTPException(status_code=400, detail="Infeasible constraints. Could not generate any valid lineups.")

    formatted_responses = []
    for r in results:
        formatted_responses.append(LineupResponse(
            total_salary=r['salary'],
            projected_score=r['projected_score'],
            players=[ProjectionSchema(**p) for p in r['players']]
        ))
    
    return wrap_data(formatted_responses, source="live")

# ── Lineup History ──
@router.get("/lineups/history")
async def list_lineup_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List authenticated user's lineup history."""
    result = await db.execute(
        select(LineupHistory)
        .where(LineupHistory.user_id == user.id)
        .where(LineupHistory.data_mode.notin_(["TRIAL_SCRAMBLED", "demo", "mock", "fake", "archived_legacy"]))
        .order_by(LineupHistory.created_at.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return wrap_data([{
        "id": r.id,
        "sport": r.sport,
        "platform": r.platform,
        "slate_id": r.slate_id,
        "strategy": r.strategy,
        "lineup_count": r.lineup_count,
        "player_count": r.player_count,
        "total_salary": r.total_salary,
        "projected_score": r.projected_score,
        "data_mode": r.data_mode,
        "created_at": str(r.created_at) if r.created_at else None,
        "lineups": r.lineups_json or [],
    } for r in rows])


@router.delete("/lineups/history/{history_id}")
async def delete_lineup_history(
    history_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user's lineup history record."""
    result = await db.execute(
        select(LineupHistory).where(
            LineupHistory.id == history_id,
            LineupHistory.user_id == user.id,
        )
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(404, "History not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
    return wrap_data({"status": "success", "message": "CSV builder ready."})
