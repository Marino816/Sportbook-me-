"""Verify admin password against the production database.

Usage:
  DATABASE_URL='...' python3 scripts/verify_admin_password.py <email> <password>

Outputs ONLY diagnostic key=value pairs. Never prints secrets.
"""

import asyncio, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from models.database import SessionLocal
from models.domain import User
from api.auth import verify_password, hash_password


async def verify(email: str, password: str):
    session = SessionLocal()
    try:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            print("USER_FOUND=false")
            return 1

        print(f"USER_FOUND=true")
        print(f"USER_ID={user.id}")
        print(f"ROLE={user.role}")
        print(f"ACTIVE={user.is_active}")

        h = user.hashed_password
        if not h:
            print("HASH_PRESENT=false")
            return 1

        print(f"HASH_PRESENT=true")
        scheme = h.split("$")[1] if "$" in (h or "") else "unknown"
        print(f"HASH_SCHEME={scheme}")

        ok = verify_password(password, h or "")
        print(f"PASSWORD_VERIFY={str(ok).lower()}")
        return 0 if ok else 1
    finally:
        await session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/verify_admin_password.py <email> <password>")
        sys.exit(1)
    sys.exit(asyncio.run(verify(sys.argv[1], sys.argv[2])))