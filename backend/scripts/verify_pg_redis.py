"""Verify isolated local Postgres and Redis. SELECT 1 / PING are not sufficient."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_shared_cache import REQUIRED_STEP, COMPOSE, docker_available, main as shared_main


def main() -> int:
    if "--prepare-only" in sys.argv or not docker_available():
        print("status: blocked_until_docker")
        print("required_step:", REQUIRED_STEP)
        print("compose:", COMPOSE)
        print(
            "checks_prepared: postgres TEMP TABLE roundtrip; "
            "Redis labeled-fixture replacement; cross-worker reads; "
            "collector SET NX lock; Redis outage; recovery"
        )
        print("select_1_and_ping_insufficient: true")
        print("connection_attempts: skipped")
        return 3
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/apex_dfs")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    return shared_main()


if __name__ == "__main__":
    raise SystemExit(main())
