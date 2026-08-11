"""Production CP-SAT diagnostic — traces every solve iteration."""
import asyncio, sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.database import SessionLocal
from models.domain import Projection, Player as DBPlayer, Slate as DBSlate
from sqlalchemy import select, func
from optimizer.mlb_optimizer import MLBOptimizer, PLATFORM_CONFIG, STRATEGY_CONFIG

random.seed(42)

async def main():
    s = SessionLocal()
    try:
        for sl_id, platform in [(1, "draftkings"), (2, "fanduel")]:
            print(f"\n{'='*60}")
            print(f"SLATE {sl_id} — {platform.upper()} MLB")

            # Load slate info
            r = await s.execute(select(DBSlate).where(DBSlate.id == sl_id))
            sl = r.scalars().first()
            print(f"Slate: {sl.sport} / {sl.site} / {sl.date}")

            # Load projections with players
            r = await s.execute(
                select(Projection, DBPlayer)
                .join(DBPlayer, Projection.player_id == DBPlayer.id)
                .where(Projection.slate_id == sl_id)
                .where(Projection.salary > 0)
            )
            rows = r.all()
            pool = []
            for proj, player in rows:
                fp = proj.projected_fp or 0
                if fp <= 0:
                    continue
                pool.append({
                    "id": proj.player_id,
                    "name": player.name,
                    "team": player.team or "",
                    "salary": proj.salary,
                    "roster_position": proj.roster_position or "",
                    "projected_fp": fp,
                    "ceiling": proj.ceiling,
                    "floor": proj.floor,
                    "ownership": proj.ownership,
                    "value": proj.value,
                })

            print(f"Total pool: {len(pool)} (salary>0, proj>0)")

            # Position breakdown
            from optimizer.mlb_optimizer import _normalize_mlb_pos
            pos_counts = {}
            for p in pool:
                pos = _normalize_mlb_pos(p.get("roster_position",""), platform)
                pos_counts[pos] = pos_counts.get(pos, 0) + 1
            print(f"Positions: {pos_counts}")

            # Run optimizer with instrumentation
            cfg = PLATFORM_CONFIG[platform]
            strat = STRATEGY_CONFIG["balanced"]
            print(f"\nConfig: cap={cfg['salary_cap']} min_sal={cfg['min_salary']} "
                  f"size={cfg['player_count']} min_uniq={strat['min_unique']} "
                  f"exposure={strat['max_exposure_pct']} stack={strat['stack_size']} "
                  f"pitch_conflict={strat.get('pitch_conflict', True)}")

            opt = MLBOptimizer(pool, platform=platform, strategy="balanced")

            # Run generate with full instrumentation
            lineups = []
            player_exposure = {}
            for i in range(9):  # 3x retries
                if len(lineups) >= 3:
                    break

                lineup = opt.build_lineup(forbidden_ids=set(), random_seed=i*137 + 42)
                status = "SOLVED" if lineup else "INFEASIBLE"
                print(f"\nIter {i+1} ({status})")

                if lineup is None:
                    print(f"  → CP-SAT infeasible for lineup #{len(lineups)+1}")
                    continue

                new_ids = {p.get("id") for p in lineup["players"]}
                sal = lineup["total_salary"]
                proj = lineup["projected_score"]
                slots = [p.get("roster_slot","?") for p in lineup["players"]]
                print(f"  → {len(lineup['players'])}P \${sal} proj={proj} slots={slots[:5]}...")

                # Check overlap with previous
                ok = True
                for j, prior in enumerate(lineups):
                    prior_ids = {p.get("id") for p in prior["players"]}
                    overlap = len(new_ids & prior_ids)
                    diff = cfg["player_count"] - overlap
                    if diff < strat["min_unique"]:
                        print(f"  REJECTED: overlap={overlap} with lineup#{j+1} (diff={diff} < min_unique={strat['min_unique']})")
                        ok = False
                        break
                if not ok:
                    continue

                # Exposure check
                if strat["max_exposure_pct"]:
                    import math
                    max_uses = max(1, math.ceil(3 * strat["max_exposure_pct"] / 100.0))
                    skip = False
                    for pid in new_ids:
                        if player_exposure.get(pid, 0) >= max_uses:
                            print(f"  REJECTED: exposure — player {pid} already used {player_exposure[pid]} times (max={max_uses})")
                            skip = True
                            break
                    if skip:
                        continue

                print(f"  ACCEPTED as lineup #{len(lineups)+1}")
                lineups.append(lineup)
                for pid in new_ids:
                    player_exposure[pid] = player_exposure.get(pid, 0) + 1

            print(f"\nFINAL: {len(lineups)}/3 lineups generated")
            sys.stdout.flush()

    finally:
        await s.close()

asyncio.run(main())