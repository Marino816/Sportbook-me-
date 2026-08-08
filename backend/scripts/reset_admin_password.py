"""One-time admin password reset — for Founder Acceptance Testing.

Usage:
  python3 scripts/reset_admin_password.py <email> <new_password>

Requires ASYNC_DATABASE_URL (or DATABASE_URL) in environment.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from models.database import SessionLocal
from models.domain import User
from api.auth import hash_password


async def reset_password(email: str, new_password: str) -> int:
    session = SessionLocal()
    try:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            print(f"ERROR: No user found with email {email}")
            return 1
        user.hashed_password = hash_password(new_password)
        await session.commit()
        print(f"Password reset for {email} (user_id={user.id}, role={user.role})")
        return 0
    finally:
        await session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/reset_admin_password.py <email> <new_password>")
        sys.exit(1)
    sys.exit(asyncio.run(reset_password(sys.argv[1], sys.argv[2])))