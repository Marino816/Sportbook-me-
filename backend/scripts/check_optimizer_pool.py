"""Diagnose optimizer projection pool for production MLB slate."""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from models.domain import Projection, Player, Slate
from sqlalchemy import select, func

async def main():
    s = SessionLocal()
    try:
        # Slate details
        r = await s.execute(select(Slate).where(Slate.id == 1))
        sl = r.scalars().first()
        sport = sl.sport if sl else "?"
        site = sl.site if sl else "?"
        print(f"SPORT={sport}")
        print(f"PLATFORM={site}")
        print(f"SLATE_ID=1")

        # Total projections for slate 1
        r = await s.execute(select(func.count()).select_from(Projection).where(Projection.slate_id == 1))
        total = r.scalar()
        print(f"TOTAL_PROJECTIONS={total}")

        # Valid player relations
        r = await s.execute(
            select(func.count()).select_from(Projection).join(Player, Projection.player_id == Player.id).where(Projection.slate_id == 1)
        )
        valid_players = r.scalar()
        print(f"VALID_PLAYER_RELATIONS={valid_players}")

        # Salary > 0
        r = await s.execute(
            select(func.count()).select_from(Projection).where(Projection.slate_id == 1, Projection.salary > 0)
        )
        valid_sal = r.scalar()
        print(f"VALID_SALARIES={valid_sal}")

        # Projected > 0
        r = await s.execute(
            select(func.count()).select_from(Projection).where(Projection.slate_id == 1, Projection.projected_fp > 0)
        )
        valid_fp = r.scalar()
        print(f"VALID_PROJECTIONS={valid_fp}")

        # Both valid + player relation
        r = await s.execute(
            select(func.count()).select_from(Projection)
            .join(Player, Projection.player_id == Player.id)
            .where(Projection.slate_id == 1, Projection.salary > 0, Projection.projected_fp > 0)
        )
        final = r.scalar()
        print(f"FINAL_POOL={final}")

        # Position breakdown
        r = await s.execute(
            select(Projection.roster_position, func.count())
            .where(Projection.slate_id == 1, Projection.salary > 0, Projection.projected_fp > 0)
            .group_by(Projection.roster_position)
        )
        pos_counts = {}
        for pos, cnt in r.all():
            pos_counts[pos] = cnt
            print(f"POS_{pos}={cnt}")

        # Sample positions
        print(f"\nSAMPLE_POSITIONS:")
        r = await s.execute(
            select(Projection.roster_position).where(Projection.slate_id == 1).limit(10)
        )
        for row in r.all():
            print(f"  {row[0]}")

        # Check if SP/RP are present (pitchers)
        has_pitchers = pos_counts.get("SP", 0) + pos_counts.get("RP", 0) + pos_counts.get("P", 0) > 0
        print(f"\nPITCHERS_PRESENT={has_pitchers}")
        print(f"CAN_BUILD_DK_MLB={'true' if final >= 10 and has_pitchers else 'false'}")

        if final < 10:
            print(f"FAILURE_REASON=Need 10+ players for MLB, only {final} valid")
        elif not has_pitchers:
            print("FAILURE_REASON=No pitcher positions (SP/RP/P) in pool")
        else:
            print("FAILURE_REASON=None — pool is sufficient")

    finally:
        await s.close()

asyncio.run(main())