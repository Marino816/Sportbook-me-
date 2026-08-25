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

from worker.celery import celery_app  # noqa: E402
from models.database import SessionLocal
from dfs.canonical import build_canonical_pool
from dfs.optimal_simulation import simulate_true_optimal
import dfs.optimal_cache as cache

logger = logging.getLogger(__name__)


LOCK_TTL = 1800  # 30-min auto-release


def _lock_key(platform, sport, slate_id):
    return f"opt_sim:lock:{platform}:{sport}:{slate_id}"


def _try_acquire_lock(platform, sport, slate_id):
    try:
        r = cache._redis()
        if r is None:
            return True
        return bool(r.set(_lock_key(platform, sport, slate_id), "1", nx=True, ex=LOCK_TTL))
    except Exception as e:
        logger.warning(f"Lock acquire error: {e}")
        return True  # fail open on Redis error


def _release_lock(platform, sport, slate_id):
    try:
        r = cache._redis()
        if r is not None:
            r.delete(_lock_key(platform, sport, slate_id))
    except Exception:
        pass


async def _run_sim_async(platform, sport, slate_id, n_sims, seed, timeout):
    """Load canonical pool, run simulation, cache result."""
    # Cache-hit check before expensive sim
    try:
        async with SessionLocal() as db:
            pool, _ = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
        if pool:
            from dfs.optimal_simulation import _compute_inputs_hash
            chash = _compute_inputs_hash(pool, sport, platform, seed, n_sims, "balanced")
            existing = cache.get_result(platform, sport, slate_id, expected_hash=chash)
            if existing:
                logger.info(f"Optimal% cache hit for {sport}/{platform} slate {slate_id}")
                cache.set_status(platform, sport, slate_id, cache.STATUS_COMPLETE)
                return {"cached": True, "n_completed": existing.get("n_completed", 0)}
    except Exception:
        pass


    # Fall through to actual simulation
    cache.set_status(platform, sport, slate_id, cache.STATUS_RUNNING)
    try:
        async with SessionLocal() as db:
            pool, _ = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
        if not pool:
            cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
            return {"error": "empty pool"}

        result = simulate_true_optimal(pool, sport=sport, platform=platform,
                                       n_sims=n_sims, seed=seed, sim_timeout=timeout)

        payload = {
            "slate_id": slate_id, "platform": platform, "sport": sport,
            "n_requested": result.n_requested, "n_completed": result.n_completed,
            "runtime_seconds": result.runtime_seconds,
            "inputs_hash": result.inputs_hash,
            "model_version": result.model_version,
            "generated_at": result.generated_at,
            "completions_optimal": result.completions_optimal,
            "completions_feasible": result.completions_feasible,
            "players": [
                {"player_id": p.player_id, "name": p.name, "position": p.position,
                 "team": p.team, "salary": p.salary, "projected_fp": p.projected_fp,
                 "appearances": p.appearances, "optimal_pct": p.optimal_pct}
                for p in result.players
            ],
        }
        cache.set_result(platform, sport, slate_id, payload)
        cache.set_status(platform, sport, slate_id, cache.STATUS_COMPLETE)
        return {"completed": result.n_completed}
    except Exception as e:
        logger.exception("opt sim task failed")
        cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=0)
def run_optimal_sim(self, platform="draftkings", sport="MLB",
                    slate_id=0, n_sims=500, seed=42, timeout=1.0):
    """Celery task: Optimal% simulation with Redis lock + cache-hit check."""
    if not _try_acquire_lock(platform, sport, slate_id):
        return {"skipped": True, "reason": "already_running"}
    try:
        return asyncio.run(_run_sim_async(platform, sport, slate_id, n_sims, seed, timeout))
    finally:
        _release_lock(platform, sport, slate_id)
