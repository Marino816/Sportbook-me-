"""
Generic sport+platform slot CP-SAT optimizer.

Used for NFL / NCAAF (and any future sport that has a RosterTemplate with
verified slots). Does not reuse MLB pitcher/hitter stacking rules.
"""

from __future__ import annotations

import random
from typing import Optional

from ortools.sat.python import cp_model

from dfs.roster import (
    RosterTemplate,
    UNIQUE_LINEUP_UNAVAILABLE,
    eligible_for_slot,
    get_roster,
    slot_label,
)

STRATEGY_MIN_UNIQUE = {
    "balanced": 2,
    "cash": 1,
    "gpp": 2,
    "aggressive": 2,
    "nuclear": 2,
}


def _keys_for_player(p: dict) -> set[str]:
    keys = set()
    pid = p.get("id")
    if pid is not None and str(pid).strip():
        keys.add(str(pid).strip())
    name = (p.get("name") or "").strip().lower()
    if name:
        keys.add(name)
    return keys


class SlotOptimizer:
    def __init__(
        self,
        pool: list[dict],
        *,
        sport: str,
        platform: str = "draftkings",
        strategy: str = "balanced",
        locks: list | None = None,
        excludes: list | None = None,
        min_salary: Optional[int] = None,
        max_salary: Optional[int] = None,
        max_exposure_pct: Optional[float] = None,
        min_unique_players: Optional[int] = None,
        **_ignored,
    ):
        roster = get_roster(sport, platform)
        if roster is None:
            raise ValueError(f"No roster template for {sport}/{platform}")
        self.roster: RosterTemplate = roster
        self.sport = roster.sport
        self.platform = roster.platform
        self.strategy = (strategy or "balanced").lower()
        self.locks = {str(x) for x in (locks or []) if x and str(x).strip()}
        self.excludes = {str(x).strip().lower() for x in (excludes or []) if x and str(x).strip()}
        self.excludes |= {str(x) for x in (excludes or []) if x and str(x).strip()}
        self.min_unique = (
            int(min_unique_players)
            if min_unique_players is not None and isinstance(min_unique_players, (int, float))
            else STRATEGY_MIN_UNIQUE.get(self.strategy, roster.min_unique_default)
        )
        self.min_unique = max(1, self.min_unique)
        if roster.salary_cap is None and max_salary is None:
            raise ValueError(
                f"Salary cap is not verified for {roster.sport} {roster.platform}. "
                f"{roster.salary_cap_source}"
            )
        self.max_salary = int(max_salary) if max_salary is not None else int(roster.salary_cap)
        self.min_salary = int(min_salary) if min_salary is not None else int(roster.min_salary)
        self.max_exposure_pct = max_exposure_pct
        self.players: list[dict] = []
        self.lock_indices: set[int] = set()
        self.idx_by_id: dict[str, int] = {}
        self._load_pool(pool)

    def _load_pool(self, pool: list[dict]) -> None:
        lock_l = {x.lower() for x in self.locks}
        for p in pool:
            pid = str(p.get("id", "") or "")
            name = (p.get("name") or "").strip()
            name_l = name.lower()
            if pid in self.excludes or name_l in self.excludes:
                continue
            if (p.get("salary", 0) or 0) <= 0:
                continue
            fp = p.get("projected_fp", 0) or 0
            if fp <= 0:
                continue
            pos = p.get("roster_position") or p.get("position") or ""
            # Must be eligible for at least one slot on this roster.
            if not any(eligible_for_slot(pos, slot, self.roster) for slot in set(self.roster.slots)):
                continue
            idx = len(self.players)
            self.players.append(p)
            if pid:
                self.idx_by_id[pid] = idx
            if pid in self.locks or name_l in lock_l:
                self.lock_indices.add(idx)

    def _prior_indices(self, prior_set: set) -> list[int]:
        want = {str(x).strip().lower() for x in prior_set if x is not None and str(x).strip()}
        hit = []
        for i, p in enumerate(self.players):
            keys = {k.lower() for k in _keys_for_player(p)}
            if keys & want:
                hit.append(i)
        return hit

    def build_lineup(
        self,
        prior_ids: list[set] | None = None,
        random_seed: int | None = None,
        timeout_seconds: float = 15.0,
        num_workers: int = 4,
    ) -> dict | None:
        n = len(self.players)
        slots = list(self.roster.slots)
        n_slots = len(slots)
        if n < n_slots:
            return None

        model = cp_model.CpModel()
        # y[p][s] = player p assigned to slot index s
        y = [[model.NewBoolVar(f"y_{p}_{s}") for s in range(n_slots)] for p in range(n)]
        x = [model.NewBoolVar(f"x_{p}") for p in range(n)]

        for p in range(n):
            model.Add(sum(y[p][s] for s in range(n_slots)) == x[p])
            pos = self.players[p].get("roster_position") or self.players[p].get("position") or ""
            for s, slot in enumerate(slots):
                if not eligible_for_slot(pos, slot, self.roster):
                    model.Add(y[p][s] == 0)

        for s in range(n_slots):
            model.Add(sum(y[p][s] for p in range(n)) == 1)

        for idx in self.lock_indices:
            model.Add(x[idx] == 1)

        model.Add(
            sum(int(self.players[p].get("salary", 0)) * x[p] for p in range(n)) <= self.max_salary
        )
        if self.min_salary:
            model.Add(
                sum(int(self.players[p].get("salary", 0)) * x[p] for p in range(n)) >= self.min_salary
            )

        # Exact-roster and min-unique no-goods against prior lineups
        for prior_set in prior_ids or []:
            indices = self._prior_indices(prior_set)
            if not indices:
                continue
            # At least min_unique players must differ from this prior roster.
            model.Add(sum(x[i] for i in indices) <= n_slots - self.min_unique)

        def _obj(p: dict) -> float:
            sim = p.get("simulated_fp")
            return float(sim) if sim is not None else float(p.get("projected_fp", 0) or 0)

        model.Maximize(sum(int(_obj(self.players[p]) * 10) * x[p] for p in range(n)))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_seconds
        solver.parameters.num_search_workers = num_workers
        if random_seed is not None:
            solver.parameters.random_seed = random_seed

        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        selected = []
        total_salary = 0
        proj_score = 0.0
        for s, slot in enumerate(slots):
            chosen = None
            for p in range(n):
                if solver.Value(y[p][s]) == 1:
                    chosen = dict(self.players[p])
                    chosen["roster_slot"] = slot_label(slot, self.roster)
                    chosen["slot_index"] = s
                    break
            if chosen is None:
                return None
            selected.append(chosen)
            total_salary += int(chosen.get("salary", 0) or 0)
            proj_score += float(chosen.get("projected_fp", 0) or 0)

        return {
            "players": selected,
            "total_salary": total_salary,
            "remaining_salary": self.max_salary - total_salary,
            "projected_score": round(proj_score, 1),
            "player_count": len(selected),
            "stack_summary": "none",
            "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        }

    def generate(self, count: int = 1, regenerate_from_ids: list[list[str]] | None = None) -> list[dict]:
        extra_prior_sets: list[set[str]] = []
        if regenerate_from_ids:
            for prior in regenerate_from_ids:
                keys = {str(x).strip().lower() for x in (prior or []) if x and str(x).strip()}
                if keys:
                    extra_prior_sets.append(keys)

        lineups: list[dict] = []
        player_exposure: dict[str, int] = {}
        n_slots = self.roster.player_count

        def _lineup_keyset(lu: dict) -> set[str]:
            keys: set[str] = set()
            for p in lu["players"]:
                keys |= {k.lower() for k in _keys_for_player(p)}
            return keys

        def _overlap_count(lu: dict, prior: set[str]) -> int:
            n = 0
            for p in lu["players"]:
                if {k.lower() for k in _keys_for_player(p)} & prior:
                    n += 1
            return n

        for i in range(max(count, 1) * 6):
            if len(lineups) >= count:
                break
            prior_sets = extra_prior_sets + [_lineup_keyset(lu) for lu in lineups]
            seed = int(random.randint(0, 999999)) + i * 13
            lineup = self.build_lineup(prior_ids=prior_sets, random_seed=seed)
            if lineup is None:
                continue

            # Exact-roster rejection (never silently repeat)
            if any(_overlap_count(lineup, prior) >= n_slots for prior in extra_prior_sets):
                continue
            if any(_overlap_count(lineup, _lineup_keyset(prev)) >= n_slots for prev in lineups):
                continue

            if self.max_exposure_pct:
                import math
                max_uses = max(1, math.ceil(count * self.max_exposure_pct / 100.0))
                if any(player_exposure.get(str(p.get("id")), 0) >= max_uses for p in lineup["players"]):
                    continue

            lineup["lineup_index"] = len(lineups) + 1
            lineup["sport"] = self.sport
            lineup["platform"] = self.platform
            lineup["strategy"] = self.strategy
            lineup["data_source"] = "native"
            lineup["data_mode"] = "native"
            lineup["min_uniqueness"] = self.min_unique
            lineup["requested_lineup_count"] = count
            lineup["generated_lineup_count"] = len(lineups) + 1
            lineup["objective_function"] = (
                "MAXIMIZE SUM(projected_fp × 10 × x[i]) via OR-Tools CP-SAT — "
                "slot assignment y[p,s] for sport/platform roster template."
            )
            lineups.append(lineup)
            for p in lineup["players"]:
                pid = str(p.get("id", ""))
                player_exposure[pid] = player_exposure.get(pid, 0) + 1

        for lu in lineups:
            lu["requested_lineup_count"] = count
            lu["generated_lineup_count"] = len(lineups)
            if len(lineups) < count:
                lu["generation_warning"] = f"Only {len(lineups)}/{count} feasible lineups found"

        return lineups


def unique_lineup_unavailable_message() -> str:
    return UNIQUE_LINEUP_UNAVAILABLE
