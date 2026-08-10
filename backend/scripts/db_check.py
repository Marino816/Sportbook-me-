import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from models.domain import Slate, Player, Projection, SystemStatus
from sqlalchemy import select, func

async def main():
    s = SessionLocal()
    try:
        for label, model in [("PLAYERS", Player), ("SLATES", Slate), ("PROJECTIONS", Projection)]:
            r = await s.execute(select(func.count()).select_from(model))
            print(label + "=" + str(r.scalar()))

        r = await s.execute(select(Projection.source).where(Projection.source == "sportsdataio").limit(1))
        src = r.scalar()
        print("PROJECTION_SOURCE=" + (src if src else "unknown"))

        r = await s.execute(select(Slate).where(Slate.sport == "MLB").order_by(Slate.id.desc()).limit(5))
        for sl in r.scalars().all():
            print("SLATE id=" + str(sl.id) + " site=" + str(sl.site) + " date=" + str(sl.date))

        r = await s.execute(select(SystemStatus).limit(1))
        ss = r.scalars().first()
        if ss:
            print("DATA_MODE=" + str(ss.data_source_mode))
    finally:
        await s.close()

asyncio.run(main())