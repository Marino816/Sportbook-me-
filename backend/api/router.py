from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any

from models.database import get_db
from models.schemas import LineupRequest, LineupResponse, ProjectionSchema
from models.domain import Projection, LineupHistory, Player, User, Subscription
from optimizer.core import DFSOptimizer
from api.utils import wrap_data
from api.auth import get_current_user
import pandas as pd

router = APIRouter()

@router.get("/projections/{slate_id}")
async def get_slate_projections(slate_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch all player projections with player metadata."""
    query = select(Projection, Player).join(Player).where(Projection.slate_id == slate_id)
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        # High-fidelity demo fallback with names
        return [
            {"id": 1, "name": "Luka Doncic", "team": "DAL", "salary": 11000, "roster_position": "PG", "projected_fp": 55.4, "value": 5.03, "ownership": 25.5, "leverage": 39.5, "ceiling": 65, "floor": 40},
            {"id": 2, "name": "Stephen Curry", "team": "GSW", "salary": 10500, "roster_position": "PG", "projected_fp": 52.1, "value": 4.96, "ownership": 18.0, "leverage": 42.0, "ceiling": 60, "floor": 38},
            {"id": 3, "name": "Nikola Jokic", "team": "DEN", "salary": 11500, "roster_position": "C", "projected_fp": 60.5, "value": 5.26, "ownership": 35.0, "leverage": 35.0, "ceiling": 70, "floor": 45},
            {"id": 4, "name": "Bennedict Mathurin", "team": "IND", "salary": 4500, "roster_position": "SF", "projected_fp": 25.0, "value": 5.55, "ownership": 5.0, "leverage": 30.0, "ceiling": 35, "floor": 10},
        ]
    
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

    projections_dicts = await get_slate_projections(request.slate_id, db)

    # Determine sport from slate for roster requirements
    from models.domain import Slate as SlateModel
    slate_result = await db.execute(select(SlateModel).where(SlateModel.id == request.slate_id))
    slate = slate_result.scalars().first()
    if not slate:
        raise HTTPException(status_code=400, detail=f"Slate {request.slate_id} not found.")
    sport = slate.sport.upper()
    min_players = 10 if sport == "MLB" else 8  # MLB DK Classic = 10, NBA = 8

    if isinstance(projections_dicts, dict) and "data" in projections_dicts:
        projections_list = projections_dicts["data"]
    else:
        projections_list = projections_dicts

    if len(projections_list) < min_players:
        raise HTTPException(status_code=400, detail=f"Not enough players in projection pool ({len(projections_list)}/{min_players} needed for {sport}).")

    # MLB uses the builder's platform-aware roster generator
    if sport == "MLB":
        from api.builder_routes import _generate_lineups, _normalize_platform, get_strategy as builder_strategy
        platform = _normalize_platform(request.settings.get("platform", "draftkings") if isinstance(request.settings, dict) else getattr(request.settings, 'platform', 'draftkings'))
        strategy = request.settings.get("strategy", "balanced") if isinstance(request.settings, dict) else getattr(request.settings, 'strategy', 'balanced')
        pool = projections_list
        lineups = _generate_lineups(pool, strategy, requested_lineups, [], [], 0.0, platform, is_mlb=True)
        # Format response using actual builder field names
        formatted = []
        for lu in lineups:
            formatted.append({
                "total_salary": lu.get("total_salary", 0),
                "projected_score": lu.get("projected_score", 0),
                "remaining_salary": lu.get("remaining_salary", 0),
                "players": lu.get("players", []),
            })

        # Save to lineup history
        try:
            hist = LineupHistory(
                user_id=user.id,
                sport=sport,
                platform=platform,
                slate_id=request.slate_id,
                strategy=strategy,
                lineup_count=len(formatted),
                player_count=formatted[0]["players"].__len__() if formatted else 0,
                total_salary=formatted[0]["total_salary"] if formatted else 0,
                projected_score=formatted[0]["projected_score"] if formatted else 0,
                data_mode="TRIAL_SCRAMBLED",
                lineups_json=formatted,
            )
            db.add(hist)
            await db.commit()
        except Exception:
            pass  # History save is non-critical

        return wrap_data({
                    "lineups": formatted,
                    "source": "sportsdataio",
                    "sport": sport,
                    "platform": platform,
                    "requested_lineups": requested_lineups,
                    "generated_lineups": len(formatted),
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
