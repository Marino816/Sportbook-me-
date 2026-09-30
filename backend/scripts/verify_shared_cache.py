"""Isolated Postgres + Redis verification beyond SELECT 1 / PING.

Labeled fixtures only. Zero provider HTTP. Does not activate production flags
in the caller; subprocesses set MARKET_TOOLS_ODDSAPI_ENABLED for Redis-required
cache behavior only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_STEP = (
    "Install Docker Desktop for Mac (https://docs.docker.com/desktop/setup/install/mac-install/), "
    "start Docker Desktop, then run: sh backend/scripts/pg_redis_setup.sh"
)
COMPOSE = "docker compose -f docker-compose.yml up -d"
DEFAULT_PG = "postgresql+asyncpg://postgres:password@127.0.0.1:5432/apex_dfs"
DEFAULT_REDIS = "redis://127.0.0.1:6379/0"
WORKER = Path(__file__).resolve().parent / "shared_cache_worker.py"


def docker_available() -> bool:
    return shutil.which("docker") is not None


def _home_american(preview: dict):
    for event in preview.get("events") or []:
        for book in event.get("books") or []:
            quote = (book.get("h2h") or {}).get("home")
            if quote:
                return quote.get("american")
    return None


def run_postgres_roundtrip(db_url: str) -> dict:
    import asyncio
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def go():
        engine = create_async_engine(db_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("CREATE TEMP TABLE sbme_mt_verify (k text, v int)"))
            await conn.execute(text("INSERT INTO sbme_mt_verify (k, v) VALUES ('fixture', 148)"))
            row = (await conn.execute(text("SELECT v FROM sbme_mt_verify WHERE k = 'fixture'"))).first()
            await conn.commit()
        await engine.dispose()
        return int(row[0]) if row else None

    value = asyncio.run(go())
    if value != 148:
        raise RuntimeError(f"postgres roundtrip expected 148, got {value}")
    return {"ok": True, "roundtrip": value, "more_than_select_1": True}


def _worker(args: list[str], env: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(WORKER), *args],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-800:] or proc.stdout[-800:] or f"worker exit {proc.returncode}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def run_redis_cache_verification(redis_url: str) -> dict:
    env = os.environ.copy()
    env.update({
        "REDIS_URL": redis_url,
        "MARKET_TOOLS_ODDSAPI_ENABLED": "true",
        "MARKET_TOOLS_ODDSAPI_COLLECT": "false",
        "MARKET_TOOLS_PROVIDER": "sgo",
        "NODE_ENV": "development",
        "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
    })
    report = {"http_requests": 0, "not_customer_data": True}

    _worker(["reset"], env)
    a = _worker(["ingest", "fixture_a_baseline.json"], env)
    report["worker_a_ingest"] = a
    if a.get("american") != -148:
        raise RuntimeError(f"fixture A ingest did not store -148: {a}")
    b_read = _worker(["read"], env)
    report["worker_b_read_a"] = b_read
    if b_read.get("american") != -148:
        raise RuntimeError(f"cross-worker read missed fixture A: {b_read}")
    if b_read.get("cache_backend") != "redis":
        raise RuntimeError(f"cross-worker read did not use redis: {b_read}")

    b = _worker(["ingest", "fixture_b_price_change.json"], env)
    report["worker_a_ingest_b"] = b
    if b.get("american") != -155:
        raise RuntimeError(f"fixture B ingest did not store -155: {b}")
    b_read2 = _worker(["read"], env)
    report["worker_b_read_b"] = b_read2
    if b_read2.get("american") != -155:
        raise RuntimeError(f"cross-worker read missed fixture B replacement: {b_read2}")
    report["cache_replacement"] = True
    report["cross_worker_reads"] = True

    lock1 = _worker(["lock"], env)
    lock2 = _worker(["lock"], env)
    report["lock_first"] = lock1
    report["lock_second"] = lock2
    if not lock1.get("acquired"):
        raise RuntimeError(f"first collector lock failed: {lock1}")
    if lock2.get("acquired") or lock2.get("reason") != "duplicate_worker":
        raise RuntimeError(f"second worker was not denied: {lock2}")
    _worker(["unlock"], env)
    report["collector_lock_contention"] = True

    outage_env = dict(env)
    outage_env["REDIS_URL"] = "redis://127.0.0.1:1/0"
    down = _worker(["read"], outage_env)
    report["outage_read"] = down
    if not down.get("unavailable") or down.get("reason") not in {"redis_unavailable", "redis_error"}:
        raise RuntimeError(f"outage did not return redis unavailable: {down}")
    if down.get("american") is not None or (down.get("events") or []):
        raise RuntimeError("outage fell back to process memory or disk snapshot")
    report["redis_outage"] = True

    recovered = _worker(["ingest", "fixture_a_baseline.json"], env)
    recovered_read = _worker(["read"], env)
    report["recovery_ingest"] = recovered
    report["recovery_read"] = recovered_read
    if recovered_read.get("american") != -148 or recovered_read.get("cache_backend") != "redis":
        raise RuntimeError(f"recovery failed: {recovered_read}")
    report["recovery"] = True
    report["ok"] = True
    return report


def main() -> int:
    if not docker_available() or "--prepare-only" in sys.argv:
        print("status: blocked_until_docker")
        print("required_step:", REQUIRED_STEP)
        print("compose:", COMPOSE)
        print(
            "checks_prepared: postgres TEMP TABLE roundtrip; "
            "Redis fixture A/B replacement; cross-worker reads; "
            "collector SET NX lock; Redis outage unavailable; recovery re-ingest"
        )
        print("connection_attempts: skipped")
        print("select_1_and_ping_insufficient: true")
        return 3

    db = os.getenv("DATABASE_URL", DEFAULT_PG)
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS)
    if not str(db).startswith("postgresql"):
        print("NOTE: DATABASE_URL is not Postgres; using isolated local Postgres URL for this check.")
        db = DEFAULT_PG
    errors = []
    report = {"provider_http": 0}
    try:
        report["postgres"] = run_postgres_roundtrip(db)
        print("postgres_roundtrip_ok")
    except Exception as exc:  # noqa: BLE001
        errors.append(("postgres", str(exc).split("\n")[0]))
    try:
        report["redis_cache"] = run_redis_cache_verification(redis_url)
        print("redis_cache_ok")
    except Exception as exc:  # noqa: BLE001
        errors.append(("redis_cache", str(exc).split("\n")[0]))
    if errors:
        print("BLOCKER: isolated Postgres/Redis cache verification failed.")
        print("required_step:", REQUIRED_STEP)
        print("failed_command:", COMPOSE)
        for name, msg in errors:
            print(f"{name}_error:", msg)
        return 2
    print(json.dumps(report, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
