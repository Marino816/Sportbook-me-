"""Check production database identity and user existence."""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from models.domain import User
from sqlalchemy import select

async def main():
    s = SessionLocal()
    try:
        r = await s.execute(select(User).where(User.email == "qa@sportbookme.ai"))
        u = r.scalars().first()
        print(f"USER_FOUND={u is not None}")
        if u:
            print(f"USER_ID={u.id}")
            print(f"ROLE={u.role}")
            print(f"ACTIVE={u.is_active}")
            h = u.hashed_password
            print(f"HASH_PRESENT={bool(h)}")
            if h:
                print(f"HASH_SCHEME={h.split('$')[1] if '$' in h else 'unknown'}")
    finally:
        await s.close()

asyncio.run(main())