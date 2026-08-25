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

# Import optimal-sim tasks so they register under the shared celery_app
import worker.optimal_sim_tasks  # noqa: F401, E402 — registers run_optimal_sim
