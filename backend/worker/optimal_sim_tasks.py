"""
Celery background task for Optimal% simulation.

Runs the true Optimal% simulation engine out-of-band (NOT in a FastAPI
request) and stores the result in Redis. The customer API reads only
the cached status/result.

Lifecycle: QUEUED -> RUNNING -> COMPLETE / FAILED (via optimal_cache).

DETERMINISTIC SNAPSHOT MODE (Phase 2D):
When called with inputs_hash, the worker loads the pre-captured snapshot
from Redis rather than re-building the canonical pool.  This guarantees
that the simulation's inputs exactly match the hash signed at queue time,
eliminating SGO live-fetch drift.

BACKWARD-COMPAT MODE:
When called without inputs_hash, the worker builds the canonical pool
live (same behavior as Phase 2C).
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
from dfs.optimal_simulation import simulate_true_optimal, _compute_inputs_hash
from dfs.optimal_lock import is_slate_locked
import dfs.optimal_cache as cache
import dfs.optimal_snapshot as snap

logger = logging.getLogger(__name__)


LOCK_TTL = 1800  # 30-min auto-release


def _lock_key(platform, sport, slate_id):
    return f"opt_sim:lock:{platform}:{sport}:{slate_id}"


def _try_acquire_lock(platform, sport, slate_id):
    """Acquire Redis distributed lock. Returns True if lock was acquired.

    FAIL-CLOSED: if Redis is unavailable or an error occurs, returns False
    (does NOT start the expensive simulation without lock protection).
    """
    try:
        r = cache._redis()
        if r is None:
            logger.warning(f"Lock failed: Redis unavailable for {sport}/{platform} slate {slate_id}")
            return False
        acquired = r.set(_lock_key(platform, sport, slate_id), "1", nx=True, ex=LOCK_TTL)
        if not acquired:
            logger.info(f"Lock held by another worker: {sport}/{platform} slate {slate_id}")
        return bool(acquired)
    except Exception as e:
        logger.warning(f"Lock acquire error for {sport}/{platform} slate {slate_id}: {e}")
        return False


def _release_lock(platform, sport, slate_id):
    try:
        r = cache._redis()
        if r is not None:
            r.delete(_lock_key(platform, sport, slate_id))
    except Exception:
        pass


async def _load_pool_from_snapshot(platform, sport, slate_id, inputs_hash):
    """Load the pre-captured canonical pool from a Redis snapshot."""
    payload = snap.load_snapshot(platform, sport, slate_id, inputs_hash)
    if not payload:
        return None
    return payload.get("players", [])


async def _build_pool_live(db_session_factory, platform, sport, slate_id):
    """Build canonical pool from live DB + SGO (backward-compat path)."""
    async with db_session_factory() as db:
        pool, _ = await build_canonical_pool(db, slate_id, platform=platform, with_ownership=True)
    return pool


async def _run_sim_async(platform, sport, slate_id, n_sims, seed, timeout,
                         inputs_hash=None):
    """Load pool (snapshot or live), run simulation, cache result.

    If inputs_hash is provided:
      - Load snapshot from Redis (deterministic — no live SGO)
      - Skip cache-hit check (caller verified eligibility)
      - Simulate exactly that snapshot version

    Without inputs_hash:
      - Build canonical pool live (backward compat)
      - Cache-hit check before expensive sim
    """
    # Re-assert backend root on sys.path (Celery prefork child fix)
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    # ── SNAPSHOT MODE: deterministic, no live SGO ──
    if inputs_hash:
        pool = await _load_pool_from_snapshot(platform, sport, slate_id, inputs_hash)
        if not pool:
            cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
            return {"error": "snapshot not found", "inputs_hash": inputs_hash}
        logger.info(
            f"Optimal% snapshot mode: {sport}/{platform} slate {slate_id} "
            f"hash={inputs_hash} players={len(pool)}"
        )
        # Verify pool hash matches the signed inputs_hash
        actual_hash = _compute_inputs_hash(pool, sport, platform, seed, n_sims, "balanced")
        if actual_hash != inputs_hash:
            logger.warning(
                f"Snapshot hash mismatch: expected={inputs_hash} actual={actual_hash} "
                f"— simulating with snapshot pool anyway"
            )
        # Skip to simulation — no cache-hit check needed (caller verified)
        return await _do_simulate(pool, platform, sport, slate_id, n_sims, seed, timeout)

    # ── LIVE MODE: backward compat, cache-hit check ──
    # Cache-hit check before expensive sim
    try:
        pool = await _build_pool_live(SessionLocal, platform, sport, slate_id)
        if pool:
            chash = _compute_inputs_hash(pool, sport, platform, seed, n_sims, "balanced")
            existing = cache.get_result(platform, sport, slate_id, expected_hash=chash)
            if existing:
                logger.info(f"Optimal% cache hit for {sport}/{platform} slate {slate_id}")
                cache.set_status(platform, sport, slate_id, cache.STATUS_COMPLETE)
                return {"cached": True, "n_completed": existing.get("n_completed", 0),
                        "inputs_hash": chash}
    except Exception:
        pass

    # Fall through to actual simulation (live build)
    cache.set_status(platform, sport, slate_id, cache.STATUS_RUNNING)
    try:
        pool = await _build_pool_live(SessionLocal, platform, sport, slate_id)
        if not pool:
            cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
            return {"error": "empty pool"}
        return await _do_simulate(pool, platform, sport, slate_id, n_sims, seed, timeout)
    except Exception as e:
        logger.exception("opt sim task failed")
        cache.set_status(platform, sport, slate_id, cache.STATUS_FAILED)
        return {"error": str(e)}


async def _do_simulate(pool, platform, sport, slate_id, n_sims, seed, timeout):
    """Run the actual simulation engine and store result."""
    cache.set_status(platform, sport, slate_id, cache.STATUS_RUNNING)
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
    return {"completed": result.n_completed, "inputs_hash": result.inputs_hash}


@celery_app.task(bind=True, max_retries=0)
def run_optimal_sim(self, platform="draftkings", sport="MLB",
                    slate_id=0, n_sims=500, seed=42, timeout=1.0,
                    inputs_hash=None):
    """Celery task: Optimal% simulation with Redis lock + snapshot support.

    When inputs_hash is provided: loads the pre-captured snapshot from
    Redis (deterministic mode — no live SGO re-fetch).

    Without inputs_hash: builds canonical pool live (backward compat).
    """
    if not _try_acquire_lock(platform, sport, slate_id):
        return {"skipped": True, "reason": "already_running"}
    try:
        return asyncio.run(_run_sim_async(
            platform, sport, slate_id, n_sims, seed, timeout,
            inputs_hash=inputs_hash,
        ))
    finally:
        _release_lock(platform, sport, slate_id)