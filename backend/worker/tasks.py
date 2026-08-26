"""
Celery worker for background data synchronization.

Runs daily slate sync: fetches NBA players and odds from external APIs
and writes system health status to the database.

Usage:
    celery -A worker.tasks worker --loglevel=info   # from backend/
    celery -A backend.worker.tasks worker --loglevel=info  # from repo root
"""

import os
import sys
import asyncio
from datetime import datetime, timezone

# Ensure the backend package is importable regardless of working directory.
# When running from backend/ via "celery -A worker.tasks", the parent dir is
# already on sys.path. When running from repo root via
# "celery -A backend.worker.tasks", the repo root is on sys.path and
# the backend package is importable as "backend.*".
# We add the parent of this file to sys.path to cover both cases.
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from integrations.balldontlie import BallDontLieAPI
from integrations.odds import OddsAPI
from models.database import SessionLocal
from models.domain import SystemStatus

from worker.celery import celery_app


@celery_app.task
def sync_daily_slate():
    """Background task to sync the day's slate and odds from APIs."""
    print("Initiating daily slate synchronization...")

    async def fetch_data():
        nba_api = BallDontLieAPI()
        odds_api = OddsAPI()

        players = await nba_api.get_players()
        odds = await odds_api.get_nba_odds()

        print(
            f"Synced {len(players)} players and {len(odds)} localized odds lines."
        )
        return {"players": len(players), "odds": len(odds)}

    result = asyncio.run(fetch_data())

    # Log status to DB
    with SessionLocal() as db:
        status = (
            db.query(SystemStatus)
            .filter(SystemStatus.provider_name == "GLOBAL_SYNC")
            .first()
        )
        if not status:
            status = SystemStatus(provider_name="GLOBAL_SYNC")
            db.add(status)

        status.last_sync_time = datetime.now(timezone.utc)
        status.last_sync_result = (
            f"Success: {result['players']} players, {result['odds']} odds"
        )
        status.is_healthy = True
        status.data_source_mode = "live"
        db.commit()

    return result


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        3600.0, sync_daily_slate.s(), name="sync_slate_every_hour"
    )
    sender.add_periodic_task(
        900.0,  # every 15 minutes
        auto_generate_optimal_pct.s(),
        name="optimal_pct_auto_generate"
    )


@celery_app.task
def auto_generate_optimal_pct():
    """Periodic beat task: check all eligible unlocked slates and enqueue
    Optimal% simulation if the current inputs_hash has no COMPLETE result.

    Phase 2D lock gates + snapshot rules applied.
    Concurrency=1 on the worker ensures only one sim at a time.
    Duplicate-lock in run_optimal_sim prevents double-enqueue.
    """
    return asyncio.run(_auto_generate_async())


async def _auto_generate_async():
    import logging
    logger = logging.getLogger(__name__)

    from dfs.db import DFSSlate
    from dfs.canonical import build_canonical_pool
    from dfs.optimal_simulation import _compute_inputs_hash
    from dfs.optimal_lock import is_slate_locked, slate_lock_status
    from dfs.optimal_snapshot import capture_snapshot, store_snapshot
    import dfs.optimal_cache as ocache
    from worker.optimal_sim_tasks import run_optimal_sim

    results = []
    async with SessionLocal() as db:
        from sqlalchemy import select
        r = await db.execute(
            select(DFSSlate)
            .where(DFSSlate.status == "PUBLISHED")
            .order_by(DFSSlate.start_time)
        )
        slates = r.scalars().all()

    for slate in slates:
        if is_slate_locked(slate.start_time):
            continue  # locked/expired — never generate

        platform = slate.platform
        sport = slate.sport
        sid = slate.id

        # Check if already completed with current inputs
        try:
            async with SessionLocal() as db2:
                pool, _ = await build_canonical_pool(
                    db2, sid, platform=platform, with_ownership=True
                )
            if not pool:
                continue

            chash = _compute_inputs_hash(pool, sport, platform, 42, 500, "balanced")
            existing = ocache.get_result(platform, sport, sid, expected_hash=chash)
            if existing:
                results.append({
                    "slate_id": sid, "slate_name": slate.slate_name,
                    "action": "skip_cache_hit", "inputs_hash": chash,
                })
                continue
        except Exception as e:
            logger.warning(f"auto-gen: pool/hash check failed for slate {sid}: {e}")
            continue

        # Freeze snapshot + enqueue with deterministic hash
        try:
            snap = capture_snapshot(pool)
            store_snapshot(platform, sport, sid, chash, snap)

            task = run_optimal_sim.delay(
                platform=platform, sport=sport, slate_id=sid,
                n_sims=500, seed=42, timeout=1.0, inputs_hash=chash,
            )
            results.append({
                "slate_id": sid, "slate_name": slate.slate_name,
                "action": "enqueued", "inputs_hash": chash,
                "task_id": task.id, "pool_size": len(pool),
            })
            logger.info(
                f"auto-gen: enqueued {sport}/{platform} slate {sid} "
                f"({slate.slate_name}) hash={chash}"
            )
        except Exception as e:
            logger.warning(f"auto-gen: enqueue failed for slate {sid}: {e}")
            results.append({
                "slate_id": sid, "action": "error", "error": str(e),
            })

    return {"checked": len(results), "results": results}

# Import optimal-sim tasks so they register under the shared celery_app
import worker.optimal_sim_tasks  # noqa: F401, E402 — registers run_optimal_sim
