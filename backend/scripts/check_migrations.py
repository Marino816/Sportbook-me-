"""Check production alembic revision via Railway TCP proxy."""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from sqlalchemy import text

async def main():
    s = SessionLocal()
    try:
        r = await s.execute(text("SELECT version_num FROM alembic_version"))
        v = r.scalar()
        print(f"PRODUCTION REVISION: {v}")
    finally:
        await s.close()

asyncio.run(main())