"""
MLB Constrained Optimizer — OR-Tools CP-SAT MILP.

Replaces greedy slot-fill with true mathematical optimization.
Supports: DraftKings, FanDuel, stacking, pitcher conflict, salary min,
multi-lineup uniqueness, exposure caps, strategy behavior.

Usage:
    opt = MLBOptimizer(pool, platform="draftkings", strategy="balanced")
    lineups = opt.generate(count=3)
"""

import random
from typing import Optional
from ortools.sat.python import cp_model

# ══════════════════════════════════════════════════════════════
#  Platform Configuration
# ══════════════════════════════════════════════════════════════

PLATFORM_CONFIG = {
    "draftkings": {
        "salary_cap": 50000,
        "min_salary": 42000,
        "player_count": 10,
        "slots": {
            "P": 2, "C": 1, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "OF": 3,
        },
    },
    "fanduel": {
        "salary_cap": 35000,
        "min_salary": 28000,
        "player_count": 9,
        "slots": {
            "P": 1, "C1B": 1, "2B": 1, "3B": 1, "SS": 1, "OF": 3, "UTIL": 1,
        },
    },
}

STRATEGY_CONFIG = {
    "balanced":   {"min_unique": 2, "max_exposure_pct": None, "stack_size": 0,    "pitch_conflict": True},
    "cash":       {"min_unique": 1, "max_exposure_pct": None, "stack_size": 0,    "pitch_conflict": True},
    "gpp":        {"min_unique": 2, "max_exposure_pct": 50,   "stack_size": 3,    "pitch_conflict": False},
    "aggressive": {"min_unique": 3, "max_exposure_pct": 40,   "stack_size": 4,    "pitch_conflict": False},
    "nuclear":    {"min_unique": 4, "max_exposure_pct": 30,   "stack_size": 5,    "pitch_conflict": False},
}


# ══════════════════════════════════════════════════════════════
#  Position Normalization
# ══════════════════════════════════════════════════════════════

def _normalize_mlb_pos(pos_str: str, platform: str = "draftkings") -> str:
    """Map raw position to roster slot."""
    p = str(pos_str).upper()
    if p in ("SP", "RP", "P"): return "P"
    if platform == "fanduel":
        if p in ("C", "1B"): return "C1B"
    if p == "C": return "C"
    if p == "1B": return "1B"
    if p == "2B": return "2B"
    if p == "3B": return "3B"
    if p == "SS": return "SS"
    if p in ("OF", "LF", "RF", "CF", "DH"): return "OF"
    return p


# ══════════════════════════════════════════════════════════════
#  Core Optimizer
# ══════════════════════════════════════════════════════════════

# Slot ordering for display
SLOT_ORDER = {
    "draftkings": ["P","P","C","1B","2B","3B","SS","OF","OF","OF"],
    "fanduel": ["P","C1B","2B","3B","SS","OF","OF","OF","UTIL"],
}


class MLBOptimizer:
    """
    OR-Tools CP-SAT optimizer for MLB DFS.

    Maximizes total projected fantasy points subject to:
    - Exact positional slot requirements
    - Platform salary cap + minimum salary
    - Pitcher/opposing-hitter conflict prevention
    - Team stacking (optional, strategy-driven)
    - Multi-lineup uniqueness + exposure caps
    """

    def __init__(
        self,
        pool: list[dict],
        platform: str = "draftkings",
        strategy: str = "balanced",
    ):
        self.pool = pool
        self.platform = platform
        self.strategy = strategy
        self.config = PLATFORM_CONFIG[platform]
        self.slots = self.config["slots"]
        self.strat = STRATEGY_CONFIG.get(strategy, STRATEGY_CONFIG["balanced"])

        # Build index maps
        self._build_maps()

    def _build_maps(self):
        """Build position eligibility and index lookups."""
        self.players = []  # eligible player dicts
        self.pos_mask = {}  # player_idx -> normalized slot
        self.team_map = {}  # team_name -> list of player indices
        self.idx_by_id = {}  # player_id -> index
        self.pitchers = set()
        self.hitters = set()

        for p in self.pool:
            if (p.get("salary", 0) or 0) <= 0:
                continue
            if (p.get("projected_fp", 0) or 0) <= 0:
                continue
            idx = len(self.players)
            self.players.append(p)
            pos = _normalize_mlb_pos(p.get("roster_position", ""), self.platform)
            self.pos_mask[idx] = pos
            self.idx_by_id[p.get("id", idx)] = idx
            team = p.get("team", "")
            if team not in self.team_map:
                self.team_map[team] = []
            self.team_map[team].append(idx)
            if pos == "P":
                self.pitchers.add(idx)
            else:
                self.hitters.add(idx)

    def _eligible_for_slot(self, player_idx: int, slot_name: str) -> bool:
        """Check if player can fill a slot."""
        pos = self.pos_mask[player_idx]
        if slot_name == "UTIL":
            return player_idx in self.hitters
        if slot_name == "C1B":
            return pos in ("C", "1B", "C1B")
        return pos == slot_name

    def _get_opposing_hitters(self, pitcher_idx: int) -> set[int]:
        """Find hitters whose team matches the pitcher's opponent.
        Requires 'opponent' field in player dict. Returns empty set if unavailable."""
        pitcher = self.players[pitcher_idx]
        opp = pitcher.get("opponent")
        if not opp:
            return set()
        return {i for i in self.hitters if self.players[i].get("team") == opp}

    def build_lineup(self, forbidden_ids: set[int] = None, random_seed: int = None, prior_ids: list[set[int]] = None) -> dict | None:
        """
        Build one optimal MLB lineup via CP-SAT.
        prior_ids: list of player-id sets from previous lineups to avoid.
        Returns {players, total_salary, projected_score, ...} or None.
        """
        n = len(self.players)
        if n < self.config["player_count"]:
            return None

        forbidden = forbidden_ids or set()
        cap = self.config["salary_cap"]
        min_sal = self.config["min_salary"]
        total_slots = self.config["player_count"]

        model = cp_model.CpModel()

        # Decision variables: x[i] = 1 if player i selected
        x = [model.NewBoolVar(f"x_{i}") for i in range(n)]

        # Objective: maximize total projected_fp
        model.Maximize(
            sum(int(self.players[i].get("projected_fp", 0) * 10) * x[i] for i in range(n))
        )

        # Exactly total_slots players
        model.Add(sum(x[i] for i in range(n)) == total_slots)

        # Salary cap
        model.Add(
            sum(int(self.players[i].get("salary", 0)) * x[i] for i in range(n)) <= cap
        )

        # Minimum salary (soft — only if feasible pool permits)
        model.Add(
            sum(int(self.players[i].get("salary", 0)) * x[i] for i in range(n)) >= min_sal
        )

        # Positional slot constraints — >= needed (non-overlapping slots)
        for slot_name, needed in self.slots.items():
            if slot_name == "UTIL":
                continue  # UTIL filled by remaining slots automatically
            eligible = [i for i in range(n) if self._eligible_for_slot(i, slot_name) and i not in forbidden]
            if len(eligible) < needed:
                return None
            model.Add(sum(x[i] for i in eligible) >= needed)

        # Pitcher/opposing-hitter conflict
        if self.strat.get("pitch_conflict", True):
            for pi in self.pitchers:
                if pi in forbidden:
                    continue
                opposing = self._get_opposing_hitters(pi)
                for hi in opposing:
                    if hi in forbidden:
                        continue
                    model.Add(x[pi] + x[hi] <= 1)

        # Team stacking
        stack_size = self.strat.get("stack_size", 0)
        if stack_size >= 2:
            # At least one team must have >= stack_size hitters selected
            stack_vars = []
            for team, indices in self.team_map.items():
                hitter_indices = [i for i in indices if i in self.hitters and i not in forbidden]
                if len(hitter_indices) >= stack_size:
                    stack_var = model.NewBoolVar(f"stack_{team}")
                    model.Add(sum(x[i] for i in hitter_indices) >= stack_size * stack_var)
                    stack_vars.append(stack_var)
            if stack_vars:
                model.Add(sum(stack_vars) >= 1)

        # No-good constraints: prevent reproducing prior lineups
        prior_ids = prior_ids or []
        for prior_set in prior_ids:
            prior_indices = [i for i in range(n) if self.players[i].get("id") in prior_set]
            if prior_indices:
                model.Add(sum(x[i] for i in prior_indices) <= total_slots - self.strat["min_unique"])

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15
        solver.parameters.num_search_workers = 4
        if random_seed is not None:
            solver.parameters.random_seed = random_seed

        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        # Extract solution
        selected = [self.players[i] for i in range(n) if solver.Value(x[i]) > 0.5]
        total_salary = sum(p.get("salary", 0) for p in selected)
        proj_score = sum(p.get("projected_fp", 0) for p in selected)

        # Assign roster_slot to each player
        used_in_pos = {s: 0 for s in self.slots}
        for p in selected:
            idx = self.idx_by_id.get(p.get("id"))
            pos = self.pos_mask.get(idx, "?")
            # Determine slot: fill required non-UTIL slots first, rest go to UTIL
            assigned = None
            for slot_name in self.slots:
                if slot_name == "UTIL":
                    continue
                if self._eligible_for_slot(idx, slot_name) and used_in_pos[slot_name] < self.slots[slot_name]:
                    assigned = slot_name
                    used_in_pos[slot_name] += 1
                    break
            if assigned is None and "UTIL" in self.slots:
                assigned = "UTIL"
            elif assigned is None:
                assigned = pos
            p["roster_slot"] = assigned

        # Sort by canonical slot order + add slot_index
        order = SLOT_ORDER.get(self.platform, SLOT_ORDER["draftkings"])
        slot_index = {s: i for i, s in enumerate(order)}
        for p in selected:
            p["slot_index"] = slot_index.get(p.get("roster_slot", "?"), 99)
        selected.sort(key=lambda p: p.get("slot_index", 99))

        # Stack summary
        team_counts = {}
        for p in selected:
            t = p.get("team", "")
            team_counts[t] = team_counts.get(t, 0) + 1
        max_stack = max(team_counts.values()) if team_counts else 0
        stack_team = max(team_counts, key=team_counts.get) if max_stack >= 2 else None

        return {
            "players": selected,
            "total_salary": total_salary,
            "remaining_salary": cap - total_salary,
            "projected_score": round(proj_score, 1),
            "player_count": len(selected),
            "stack_summary": f"{stack_team} {max_stack}-man" if stack_team else "none",
        }

    def generate(self, count: int = 1) -> list[dict]:
        """
        Generate count lineups with uniqueness + exposure enforcement.
        Iterative CP-SAT solving — each solution adds no-good constraints.
        """
        lineups = []
        player_exposure = {}

        for i in range(count * 3):
            if len(lineups) >= count:
                break

            prior_sets = [{p.get("id") for p in lu["players"]} for lu in lineups]
            lineup = self.build_lineup(
                forbidden_ids=set(),
                random_seed=i * 137 + random.randint(0, 99),
                prior_ids=prior_sets,
            )
            if lineup is None:
                lineup = self.build_lineup(
                    forbidden_ids=set(),
                    random_seed=i * 137 + random.randint(100, 999),
                    prior_ids=prior_sets,
                )
                if lineup is None:
                    continue

            new_ids = {p.get("id") for p in lineup["players"]}

            # Check uniqueness against all prior lineups
            ok = True
            for prior in lineups:
                overlap = len(new_ids & {p.get("id") for p in prior["players"]})
                if (self.config["player_count"] - overlap) < self.strat["min_unique"]:
                    ok = False
                    break
            if not ok:
                continue

            # Exposure check
            if self.strat["max_exposure_pct"]:
                import math
                max_uses = max(1, math.ceil(count * self.strat["max_exposure_pct"] / 100.0))
                skip = False
                for pid in new_ids:
                    if player_exposure.get(pid, 0) >= max_uses:
                        skip = True
                        break
                if skip:
                    continue

            # Build response
            lineup["lineup_index"] = len(lineups) + 1
            lineup["sport"] = "MLB"
            lineup["platform"] = self.platform
            lineup["strategy"] = self.strategy
            lineup["data_source"] = "sportsdataio"
            lineup["data_mode"] = "TRIAL_SCRAMBLED"
            lineup["min_uniqueness"] = self.strat["min_unique"]
            lineup["requested_lineup_count"] = count
            lineup["generated_lineup_count"] = len(lineups) + 1
            lineups.append(lineup)

            # Track exposure
            for pid in new_ids:
                player_exposure[pid] = player_exposure.get(pid, 0) + 1

        # Add generation metadata to each lineup
        for lu in lineups:
            lu["requested_lineup_count"] = count
            lu["generated_lineup_count"] = len(lineups)
            if len(lineups) < count:
                lu["generation_warning"] = (
                    f"Only {len(lineups)}/{count} feasible lineups found"
                )

        return lineups