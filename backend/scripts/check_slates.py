"""Diagnose all slates and their projection counts."""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from models.domain import Slate, Projection
from sqlalchemy import select, func

async def main():
    s = SessionLocal()
    try:
        # List all slates
        r = await s.execute(select(Slate).order_by(Slate.id))
        slates = r.scalars().all()
        print(f"Total slates: {len(slates)}\n")
        for sl in slates:
            # Count projections
            r = await s.execute(select(func.count()).select_from(Projection).where(Projection.slate_id == sl.id))
            proj_count = r.scalar()
            r = await s.execute(
                select(func.count()).select_from(Projection)
                .where(Projection.slate_id == sl.id, Projection.salary > 0, Projection.projected_fp > 0)
            )
            valid_count = r.scalar()
            print(f"SLATE_ID={sl.id}")
            print(f"  SPORT={sl.sport}")
            print(f"  SITE={sl.site}")
            print(f"  DATE={sl.date}")
            print(f"  IS_MAIN={sl.is_main_slate}")
            print(f"  PROJECTION_COUNT={proj_count} (valid={valid_count})")
            print()

        # Check for any non-MLB slates
        r = await s.execute(select(Slate).where(Slate.sport != "MLB"))
        bad = r.scalars().all()
        if bad:
            print("NON-MLB SLATES FOUND:")
            for sl in bad:
                print(f"  ID={sl.id} SPORT={sl.sport} SITE={sl.site}")
    finally:
        await s.close()

asyncio.run(main())