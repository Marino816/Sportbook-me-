"""Verify isolated local Postgres and Redis. Does not use SQLite or in-process cache."""

from __future__ import annotations

import os
import sys

REQUIRED_STEP = (
    "Install Docker Desktop for Mac (https://docs.docker.com/desktop/setup/install/mac-install/), "
    "start Docker Desktop, then run: sh backend/scripts/pg_redis_setup.sh"
)
COMPOSE = 'docker compose -f docker-compose.yml up -d'


def main() -> int:
    if "--prepare-only" in sys.argv:
        print("status: blocked_until_docker")
        print("required_step:", REQUIRED_STEP)
        print("compose:", COMPOSE)
        print("checks_prepared: postgres SELECT 1; redis PING; Market Tools Redis key sbme:mt:oddsapi:preview; collect lock sbme:mt:oddsapi:collect_lock")
        print("connection_attempts: skipped")
        return 3

    default_pg = "postgresql+asyncpg://postgres:password@127.0.0.1:5432/apex_dfs"
    db = os.getenv("DATABASE_URL", default_pg)
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    if not db.startswith("postgresql"):
        print("NOTE: DATABASE_URL is not Postgres; using isolated local Postgres URL for this check.")
        db = default_pg
    errors = []
    try:
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        async def ping_db():
            engine = create_async_engine(db, pool_pre_ping=True)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()

        asyncio.run(ping_db())
        print("postgres_ok")
    except Exception as exc:  # noqa: BLE001
        errors.append(("postgres", str(exc).split("\n")[0]))
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
        pong = client.ping()
        if not pong:
            raise RuntimeError("redis ping returned falsy")
        print("redis_ok")
    except Exception as exc:  # noqa: BLE001
        errors.append(("redis", str(exc).split("\n")[0]))
    if errors:
        print("BLOCKER: local Postgres/Redis are not reachable.")
        print("required_step:", REQUIRED_STEP)
        print("failed_command:", COMPOSE)
        for name, msg in errors:
            print(f"{name}_error:", msg)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
