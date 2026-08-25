import sys; sys.path.insert(0, "/app")
import os, time, asyncio, json, tracemalloc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

db_url = os.environ.get("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(db_url, echo=False)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

RESULTS = {}

async def main():
    from dfs.canonical import build_canonical_pool
    from dfs.optimal_simulation import simulate_true_optimal, validate_lineup, _generate_outcomes, _pool_slice
    from optimizer.mlb_optimizer import MLBOptimizer

    async with SessionLocal() as db:
        pool, meta = await build_canonical_pool(db, 7, platform="draftkings", with_ownership=True)
        eligible = [p for p in pool if (p.get("projected_fp") or 0) > 0 and (p.get("salary") or 0) > 0]
        print(f"POOL: {len(pool)} total, {len(eligible)} eligible", flush=True)

        for n in [50, 100, 250, 500]:
            for timeout in ([3.0, 5.0] if n <= 100 else [5.0]):
                t0 = time.time()
                r = simulate_true_optimal(pool, sport="MLB", platform="draftkings", n_sims=n, seed=42, sim_timeout=timeout)
                elapsed = time.time() - t0
                opt_pos = [p.optimal_pct for p in r.players if p.optimal_pct > 0]
                key = f"n{n}_t{timeout}"
                RESULTS[key] = {
                    "n_sims": n, "timeout": timeout,
                    "completed": r.n_completed, "infeasible": r.n_infeasible,
                    "total_seconds": round(elapsed, 1),
                    "avg_solve": r.avg_solve_seconds,
                    "players_opt_gt0": len(opt_pos),
                    "max_opt": round(max(opt_pos), 1) if opt_pos else 0,
                }
                print(f"[{key}] completed={r.n_completed}/{n} infeasible={r.n_infeasible} total={elapsed:.1f}s avg={r.avg_solve_seconds:.2f}s opt>0={len(opt_pos)} max={max(opt_pos) if opt_pos else 0:.1f}%", flush=True)

        # Stability check: 500 vs 1000 for ranking
        print("\n--- STABILITY 500 vs 1000 ---", flush=True)
        r500 = simulate_true_optimal(pool, sport="MLB", n_sims=500, seed=42, sim_timeout=5.0)
        top500 = {p.player_id: p.optimal_pct for p in r500.top_n(20)}
        r1000 = simulate_true_optimal(pool, sport="MLB", n_sims=1000, seed=42, sim_timeout=5.0)
        top1000 = {p.player_id: p.optimal_pct for p in r1000.top_n(20)}
        print(f"n500 top20 ids: {list(top500.keys())[:10]}", flush=True)
        print(f"n1000 top20 ids: {list(top1000.keys())[:10]}", flush=True)
        overlap = len(set(top500.keys()) & set(top1000.keys()))
        print(f"Top-20 overlap: {overlap}/20", flush=True)

        print("\n=== FULL RESULTS ===", flush=True)
        print(json.dumps(RESULTS, indent=2), flush=True)

asyncio.run(main())
