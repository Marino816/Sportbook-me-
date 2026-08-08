"""One-time admin password reset — for Founder Acceptance Testing.

Usage:
  DATABASE_URL='...' python3 scripts/reset_admin_password.py <email> <new_password>
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from models.database import SessionLocal
from models.domain import User
from api.auth import hash_password, verify_password


async def reset_password(email: str, new_password: str) -> int:
    session = SessionLocal()
    try:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if not user:
            print(f"ERROR: No user found with email {email}")
            return 1

        # Hash with the EXACT password (never print)
        new_hash = hash_password(new_password)
        user.hashed_password = new_hash
        await session.commit()

        # ── POST-COMMIT VERIFICATION ── reload from DB
        result2 = await session.execute(select(User).where(User.email == email))
        reloaded = result2.scalars().first()
        hash_committed = bool(reloaded and reloaded.hashed_password)
        hash_verifies = verify_password(new_password, reloaded.hashed_password or "")

        print(f"Password reset for {email} (user_id={user.id}, role={user.role})")
        print(f"PASSWORD_RESET_COMMITTED={str(hash_committed).lower()}")
        print(f"POST_COMMIT_PASSWORD_VERIFY={str(hash_verifies).lower()}")

        return 0 if hash_verifies else 1
    finally:
        await session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/reset_admin_password.py <email> <new_password>")
        sys.exit(1)
    sys.exit(asyncio.run(reset_password(sys.argv[1], sys.argv[2])))