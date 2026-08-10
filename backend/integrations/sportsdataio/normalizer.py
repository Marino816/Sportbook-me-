"""Map SportsDataIO fields to SPORTBOOK ME domain models with upsert logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from models.domain import Slate, Player, Projection, Matchup


async def upsert_player(
    db: AsyncSession,
    provider_id: int,
    name: str,
    team: str,
    position: str = None,
) -> Player:
    """Upsert a player by provider ID. Returns the Player instance."""
    result = await db.execute(
        select(Player).where(Player.name == name, Player.sport == "MLB")
    )
    player = result.scalars().first()
    if player:
        player.team = team
        return player

    player = Player(sport="MLB", name=name, team=team)
    db.add(player)
    await db.flush()
    return player


async def upsert_slate(
    db: AsyncSession,
    sport: str,
    site: str,
    date: datetime,
    is_main: bool = True,
) -> Slate:
    """Upsert a slate. Returns the Slate instance."""
    naive_date = date.replace(tzinfo=None) if date.tzinfo else date
    result = await db.execute(
        select(Slate).where(
            Slate.sport == sport,
            Slate.site == site,
            Slate.date >= naive_date.replace(hour=0, minute=0),
            Slate.date <= naive_date.replace(hour=23, minute=59),
        )
    )
    slate = result.scalars().first()
    if slate:
        return slate

    slate = Slate(sport=sport, site=site, date=naive_date, is_main_slate=is_main)
    db.add(slate)
    await db.flush()
    return slate


async def upsert_projection(
    db: AsyncSession,
    slate_id: int,
    player_id: int,
    salary: int,
    roster_position: str,
    projected_fp: float,
    ceiling: float,
    floor: float,
    ownership: float,
    value: float,
) -> None:
    """Upsert a projection record — delete old, insert new for idempotency."""
    # Remove stale projection for this player on this slate
    from sqlalchemy import delete
    await db.execute(
        delete(Projection).where(
            Projection.slate_id == slate_id,
            Projection.player_id == player_id,
        )
    )
    proj = Projection(
        slate_id=slate_id,
        player_id=player_id,
        salary=salary,
        roster_position=roster_position,
        projected_fp=projected_fp,
        ceiling=ceiling,
        floor=floor,
        ownership=ownership,
        value=value,
        updated_at=datetime.now(timezone.utc),
        source="sportsdataio",
    )
    db.add(proj)


async def upsert_matchup(
    db: AsyncSession,
    away_team: str,
    home_team: str,
    game_time: datetime,
    status: str = "scheduled",
) -> None:
    """Upsert a matchup record."""
    naive_gt = game_time.replace(tzinfo=None) if game_time and game_time.tzinfo else game_time
    existing = await db.execute(
        select(Matchup).where(
            Matchup.sport == "MLB",
            Matchup.away_team == away_team,
            Matchup.home_team == home_team,
            Matchup.game_time == naive_gt,
        )
    )
    if existing.scalars().first():
        return
    m = Matchup(
        sport="MLB",
        away_team=away_team,
        home_team=home_team,
        game_time=naive_gt,
        status=status,
    )
    db.add(m)