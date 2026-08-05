"""
SB-Me Builder — Lineup construction and validation engines.

Supports: DraftKings NBA, FanDuel NBA.
"""

from typing import Dict, List, Optional, Tuple


# ── DraftKings NBA Rules ─────────────────────────────────────

DK_CAP = 50000
DK_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
DK_MIN_PLAYERS = 8
DK_MAX_TEAM_PLAYERS = 4  # max from one team

# ── FanDuel NBA Rules ────────────────────────────────────────

FD_CAP = 60000
FD_SLOTS = ["PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C"]
FD_MIN_PLAYERS = 9
FD_MAX_TEAM_PLAYERS = 4


class BuilderValidator:
    """Pre-optimization validation of constraints."""

    @staticmethod
    def validate_platform(platform: str) -> Optional[str]:
        if platform.lower() not in ("draftkings", "fanduel"):
            return f"Unsupported platform: {platform}"
        return None

    @staticmethod
    def validate_sport(sport: str) -> Optional[str]:
        if sport.lower() != "nba":
            return f"Unsupported sport: {sport}. Builder currently supports NBA only."
        return None

    @staticmethod
    def validate_constraints(
        locked_ids: List[int],
        excluded_ids: List[int],
        player_pool: List[dict],
    ) -> List[str]:
        errors = []
        locked_set = set(locked_ids)
        excluded_set = set(excluded_ids)
        pool_ids = {p.get("id") for p in player_pool if p.get("id")}

        conflicts = locked_set & excluded_set
        if conflicts:
            errors.append(f"Players locked and excluded: {sorted(conflicts)}")

        for pid in locked_set:
            if pid not in pool_ids:
                errors.append(f"Locked player {pid} not in player pool")
        for pid in excluded_set:
            if pid not in pool_ids:
                errors.append(f"Excluded player {pid} not in player pool")

        return errors

    @staticmethod
    def validate_roster(lineup: List[dict], platform: str, player_data: List[dict]) -> List[str]:
        errors = []
        rules = {
            "draftkings": (DK_CAP, DK_MIN_PLAYERS, DK_MAX_TEAM_PLAYERS),
            "fanduel": (FD_CAP, FD_MIN_PLAYERS, FD_MAX_TEAM_PLAYERS),
        }
        cap, min_players, max_team = rules.get(platform.lower(), (50000, 8, 4))
        total_salary = sum(p.get("salary", 0) for p in lineup)
        if total_salary > cap:
            errors.append(f"Salary ${total_salary:,} exceeds ${cap:,} cap")
        if len(lineup) != min_players:
            errors.append(f"Expected {min_players} players, got {len(lineup)}")
        return errors


# ── Exposure Engine ──────────────────────────────────────────

class ExposureEngine:
    """Calculate and enforce exposure constraints across lineups."""

    @staticmethod
    def calculate_exposure(lineups: List[List[dict]]) -> dict:
        if not lineups:
            return {"players": {}, "teams": {}}
        total = len(lineups)
        player_exposure = {}
        team_exposure = {}
        for lu in lineups:
            seen_players = set()
            for p in lu:
                pid = p.get("id")
                if pid and pid not in seen_players:
                    player_exposure[pid] = player_exposure.get(pid, 0) + 1
                    seen_players.add(pid)
                team = p.get("team")
                if team:
                    team_exposure[team] = team_exposure.get(team, 0) + 1
        return {
            "players": {k: round(v / total * 100, 1) for k, v in player_exposure.items()},
            "teams": {k: round(v / total * 100, 1) for k, v in team_exposure.items()},
        }

    @staticmethod
    def check_exposure_rules(
        exposure: dict,
        rules: List[dict],
    ) -> List[dict]:
        """Returns list of unsatisfied rules."""
        unsatisfied = []
        player_exp = exposure.get("players", {})
        team_exp = exposure.get("teams", {})
        for rule in rules:
            entity_type = rule.get("entity_type", "player")
            eid = str(rule.get("entity_id", ""))
            exp_map = player_exp if entity_type == "player" else team_exp
            actual = exp_map.get(int(eid) if entity_type == "player" else eid, 0)
            if "max_exposure" in rule and actual > rule["max_exposure"]:
                unsatisfied.append({**rule, "actual": actual, "violation": f"Exceeded max {rule['max_exposure']}%"})
            if "min_exposure" in rule and actual < rule["min_exposure"]:
                unsatisfied.append({**rule, "actual": actual, "violation": f"Below min {rule['min_exposure']}%"})
        return unsatisfied


# ── Portfolio Engine ─────────────────────────────────────────

class PortfolioEngine:
    """Multi-lineup portfolio generation with exposure controls."""

    @staticmethod
    def build_portfolio(
        lineups: List[dict],
        strategy: str,
    ) -> dict:
        if not lineups:
            return {"lineup_count": 0}
        avg_proj = sum(l.get("projected_score", 0) for l in lineups) / len(lineups)
        avg_salary = sum(l.get("total_salary", 0) for l in lineups) / len(lineups)
        avg_ceiling = sum(l.get("ceiling_score", 0) or 0 for l in lineups) / len(lineups)
        exposure = ExposureEngine.calculate_exposure(
            [[{"id": p["id"], "team": p.get("team", "")} for p in l.get("players", [])] for l in lineups]
        )
        return {
            "lineup_count": len(lineups),
            "avg_projection": round(avg_proj, 1),
            "avg_ceiling": round(avg_ceiling, 1),
            "avg_salary": round(avg_salary, 0),
            "exposure": exposure,
            "strategy": strategy,
        }


# ── Lineup Explanation Generator ─────────────────────────────

class ExplanationGenerator:
    """Generate structured lineup explanations."""

    @staticmethod
    def explain(lineup: dict, strategy: str, model_version: str,
                locks: List[int], exclusions: List[int]) -> dict:
        players = lineup.get("players", [])
        top_edge = sorted(players, key=lambda p: p.get("edge_score", 0) or 0, reverse=True)[:3]
        risks = [p.get("name", "?") for p in players if (p.get("risk_score", 0) or 0) > 0.3]
        return {
            "strategy": strategy,
            "projected_score": lineup.get("projected_score"),
            "ceiling": lineup.get("ceiling_score"),
            "total_salary": lineup.get("total_salary"),
            "remaining_salary": lineup.get("remaining_salary", 0),
            "top_edge_players": [{"name": p.get("name"), "edge": p.get("edge_score")} for p in top_edge],
            "main_risks": risks,
            "locks_applied": locks,
            "exclusions_applied": exclusions,
            "model_version": model_version,
        }