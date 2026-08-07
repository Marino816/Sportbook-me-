"""One-time admin password reset — for Founder Acceptance Testing.

Usage:
  python scripts/reset_admin_password.py <email> <new_password>

Environment: DATABASE_URL must be set (reads from .env if present at repo root).
"""

import sys
import os

# Load .env from repo root so DATABASE_URL is available
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip().strip("\"'")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.database import SessionLocal
from models.domain import User
from api.auth import hash_password


def reset_password(email: str, new_password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"ERROR: No user found with email {email}")
            return 1
        user.hashed_password = hash_password(new_password)
        db.commit()
        print(f"Password reset for {email} (user_id={user.id}, role={user.role})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/reset_admin_password.py <email> <new_password>")
        sys.exit(1)
    sys.exit(reset_password(sys.argv[1], sys.argv[2]))