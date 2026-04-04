import os
from celery import Celery
from backend.integrations.balldontlie import BallDontLieAPI
from backend.integrations.odds import OddsAPI
from backend.models.database import SessionLocal
from backend.models.domain import SystemStatus
from datetime import datetime, timezone
import asyncio

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "apex_dfs_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Example background scheduled task
@celery_app.task
def sync_daily_slate():
    """Background task to sync the day's slate and odds from APIs."""
    print("Initiating daily slate synchronization...")
    
    async def fetch_data():
        nba_api = BallDontLieAPI()
        odds_api = OddsAPI()
        
        # In a real environment, we'd save these to the database here
        players = await nba_api.get_players()
        odds = await odds_api.get_nba_odds()
        
        print(f"Synced {len(players)} players and {len(odds)} localized odds lines.")
        return {"players": len(players), "odds": len(odds)}

    # Celery tasks are synchronous, we run the async functions via asyncio
    result = asyncio.run(fetch_data())
    
    # Log status to DB
    with SessionLocal() as db:
        status = db.query(SystemStatus).filter(SystemStatus.provider_name == "GLOBAL_SYNC").first()
        if not status:
            status = SystemStatus(provider_name="GLOBAL_SYNC")
            db.add(status)
        
        status.last_sync_time = datetime.now(timezone.utc)
        status.last_sync_result = f"Success: {result['players']} players, {result['odds']} odds"
        status.is_healthy = True
        status.data_source_mode = "live"
        db.commit()
        
    return result

# Setup periodic tasks (e.g. every hour)
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Runs every hour
    sender.add_periodic_task(3600.0, sync_daily_slate.s(), name='sync_slate_every_hour')
