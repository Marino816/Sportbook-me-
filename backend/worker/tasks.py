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
from models.database import SessionLocal, SyncSessionLocal
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

    Uses SyncSessionLocal to avoid the Celery worker's event-loop mismatch.
    """
    return _auto_generate_sync()


def _auto_generate_sync():
    """Lightweight eligibility check — enqueue if slate is unlocked.

    Does NOT build canonical pools or compute hashes itself. The worker's
    _run_sim_async already has cache-hit + inputs_hash comparison built in
    (Phase 2D). This function only checks the lock gate and enqueues.
    """
    import logging
    logger = logging.getLogger(__name__)
    from dfs.db import DFSSlate
    from dfs.optimal_lock import is_slate_locked
    from worker.optimal_sim_tasks import run_optimal_sim

    with SyncSessionLocal() as db:
        slates = (db.query(DFSSlate)
                  .filter(DFSSlate.status == "PUBLISHED")
                  .order_by(DFSSlate.start_time)
                  .all())

    results = []
    for slate in slates:
        # ONLY gate at trigger level: lock time
        # Cache-hit / inputs_hash dedup handled by the worker
        if is_slate_locked(slate.start_time):
            continue

        try:
            task = run_optimal_sim.delay(
                platform=slate.platform, sport=slate.sport,
                slate_id=slate.id, n_sims=500, seed=42, timeout=1.0,
            )
            results.append({
                "slate_id": slate.id, "slate_name": slate.slate_name,
                "action": "enqueued", "task_id": task.id,
            })
        except Exception as e:
            logger.warning(f"auto-gen: enqueue failed for slate {slate.id}: {e}")
            results.append({"slate_id": slate.id, "action": "error", "error": str(e)})

    return {"enqueued": len(results), "results": results}

# Import optimal-sim tasks so they register under the shared celery_app
import worker.optimal_sim_tasks  # noqa: F401, E402 — registers run_optimal_sim
