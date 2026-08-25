"""
Celery background task for Optimal% simulation.

Runs the true Optimal% simulation engine out-of-band (NOT in a FastAPI
request) and stores the result in Redis. The customer API reads only
the cached status/result.

Lifecycle: QUEUED -> RUNNING -> COMPLETE / FAILED (via optimal_cache).
"""

import os
import sys
import asyncio
import logging

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from celery import Celery  # noqa: E402
from models.database import SessionLocal
from dfs.canonical import build_canonical_pool
from dfs.optimal_simulation import simulate_true_optimal
import dfs.optimal_cache as cache

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("worker", broker=REDIS_URL, backend=REDIS_URL)


async def _run_sim_async(platform, sport, slate_id, n_sims, seed, timeout):
    """Load canonical pool, run simulation, cache result."""
    cache.set_status(platform, sport, slate_id, cache.STATUS_RUNNING)
    try:
        async with SessionLocal() as db:
            pool, meta = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
        if not pool:
            cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
            return {"error": "empty pool"}

        result = simulate_true_optimal(pool, sport=sport, platform=platform, n_sims=n_sims, seed=seed, sim_timeout=timeout)

        payload = {
            "slate_id": slate_id,
            "platform": platform,
            "sport": sport,
            "n_completed": result.n_completed,
            "n_infeasible": result.n_infeasible,
            "n_total": result.n_total,
            "runtime_seconds": result.runtime_seconds,
            "inputs_hash": result.inputs_hash,
            "model_version": result.model_version,
            "generated_at": result.generated_at,
            "players": [
                {"player_id": p.player_id, "name": p.name, "position": p.position,
                 "team": p.team, "salary": p.salary, "projected_fp": p.projected_fp,
                 "appearances": p.appearances, "optimal_pct": p.optimal_pct}
                for p in result.players
            ],
        }
        cache.set_result(platform, sport, slate_id, payload)
        cache.set_status(platform, sport, slate_id, cache.STATUS_COMPLETE)
        return {"completed": result.n_completed, "infeasible": result.n_infeasible}
    except Exception as e:
        logger.exception("opt_sim task failed")
        cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=0)
def run_optimal_sim(self, platform="draftkings", sport="MLB",
                    slate_id=0, n_sims=100, seed=42, timeout=5.0):
    """Celery task: run true Optimal% simulation and cache the result."""
    return asyncio.run(_run_sim_async(platform, sport, slate_id, n_sims, seed, timeout))
