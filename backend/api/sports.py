from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from models.database import get_db
from models.domain import Matchup
from api.utils import wrap_data

router = APIRouter()

@router.get("/lobby")
async def get_sports_lobby(sport: str = "NFL", db: AsyncSession = Depends(get_db)):
    """Fetch live and scheduled matchups for the betting lobby."""
    result = await db.execute(
        select(Matchup)
        .where(Matchup.sport == sport)
        .order_by(Matchup.game_time.asc())
    )
    matches = result.scalars().all()
    
    # Trigger integration sync if empty
    if not matches:
        # demo/test fallback to match the high-fidelity UI
        return wrap_data([
            {
                "time": "SUN 1:00 PM • FOX",
                "home_team": "SF 49ers",
                "away_team": "SEA Seahawks",
                "odds": [{"val": "-4.5", "price": "-110"}, {"val": "O 47.5", "price": "-115"}, {"val": "-210"}]
            },
            {
                "time": "Q4 2:15 • 28 - 24",
                "home_team": "KC Chiefs",
                "away_team": "BUF Bills",
                "is_live": True,
                "odds": [{"val": "-1.5", "price": "-115"}, {"val": "O 54.5", "price": "-110"}, {"val": "-145"}]
            },
            {
                "time": "MON 8:15 PM • ESPN",
                "home_team": "DAL Cowboys",
                "away_team": "PHI Eagles",
                "is_boosted": True,
                "odds": [{"val": "+3.0", "price": "-110"}, {"val": "O 51.5", "price": "-110"}, {"val": "+140"}]
            }
        ], source="demo")
        
    return wrap_data(matches)

@router.post("/slip/calculate")
async def calculate_payout(stake: float, odds: int):
    """Calculate potential payout for a bet slip selection."""
    if odds > 0:
        payout = stake * (1 + odds / 100)
    else:
        payout = stake * (1 + 100 / abs(odds))
    
    return {"payout": round(payout, 2)}
