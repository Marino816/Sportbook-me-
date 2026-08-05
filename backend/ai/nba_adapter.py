"""
NBA sport adapter for Sportsbook Me DFS AI.

Implements the SportAdapter interface for NBA projections.
Uses deterministic formulas with available input data.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from ai.sport_adapter import SportAdapter

# ── DraftKings NBA roster rules ──────────────────────────────
DK_SALARY_CAP = 50000
DK_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
DK_MIN_PLAYERS = 8

# FanDuel NBA roster rules (placeholder — no optimizer yet)
FD_SALARY_CAP = 60000
FD_SLOTS = ["PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C"]
FD_MIN_PLAYERS = 9


class NBAAdapter(SportAdapter):
    sport = "nba"
    league = "NBA"

    REQUIRED_COLUMNS = {"id", "name", "team", "salary", "roster_position"}
    OPTIONAL_COLUMNS = {"projected_fp", "ownership", "minutes", "avg_fp_last_5",
                        "opponent_def_rating", "is_home", "rest_days",
                        "injury_status", "starting_status", "player_id"}

    # ── Validation ────────────────────────────────────────────

    def validate_input(self, data: pd.DataFrame) -> List[str]:
        errors = []
        missing = self.REQUIRED_COLUMNS - set(data.columns)
        if missing:
            errors.append(f"Missing required columns: {sorted(missing)}")
        if len(data) < DK_MIN_PLAYERS:
            errors.append(f"Insufficient players: need {DK_MIN_PLAYERS}, got {len(data)}")
        if "salary" in data.columns and data["salary"].max() > DK_SALARY_CAP * 2:
            errors.append(f"Salary values exceed reasonable maximum")
        return errors

    def normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        # Normalize position strings
        if "roster_position" in df.columns:
            df["roster_position"] = df["roster_position"].astype(str).str.upper()
        # Ensure numeric types
        for col in ["salary", "projected_fp"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # ── Features ──────────────────────────────────────────────

    def build_features(self, data: pd.DataFrame, game_logs: pd.DataFrame,
                       matchups: pd.DataFrame, injuries: pd.DataFrame) -> pd.DataFrame:
        df = self.normalize_data(data)
        df["avg_fp_last_5"] = np.nan
        df["minutes"] = np.nan
        df["opponent_def_rating"] = np.nan
        df["is_home"] = False
        df["rest_days"] = 1
        df["injury_status"] = "unknown"
        df["starting_status"] = "unknown"

        if not game_logs.empty and "player_id" in df.columns:
            for idx in df.index:
                pid = df.at[idx, "player_id"]
                player_logs = game_logs[game_logs["player_id"] == pid].tail(5)
                if not player_logs.empty and "fantasy_points" in player_logs.columns:
                    df.at[idx, "avg_fp_last_5"] = float(player_logs["fantasy_points"].mean())

        return df

    # ── Projections ───────────────────────────────────────────

    def calculate_projection(self, features: pd.DataFrame, idx: int) -> float:
        row = features.loc[idx]
        base = float(row.get("projected_fp", row.get("avg_fp_last_5", 0.0)))
        if pd.isna(base):
            base = 0.0
        return round(base, 1)

    def calculate_floor(self, features: pd.DataFrame, idx: int, median: float) -> float:
        row = features.loc[idx]
        avg = row.get("avg_fp_last_5", median)
        if pd.isna(avg):
            avg = median
        std_est = abs(median - avg) * 0.5 if avg > 0 else median * 0.25
        return round(max(0.0, median - std_est), 1)

    def calculate_ceiling(self, features: pd.DataFrame, idx: int, median: float) -> float:
        row = features.loc[idx]
        avg = row.get("avg_fp_last_5", median)
        if pd.isna(avg):
            avg = median
        std_est = abs(median - avg) * 0.5 if avg > 0 else median * 0.25
        return round(median + std_est, 1)

    def calculate_boom_probability(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        row = features.loc[idx]
        if pd.isna(row.get("avg_fp_last_5")):
            return None
        return None  # Requires historical variance data — unavailable in Phase 7A

    def calculate_bust_probability(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        return None  # Same as boom — requires historical variance

    # ── Confidence ────────────────────────────────────────────

    def calculate_confidence(self, features: pd.DataFrame, idx: int,
                             missing_fields: List[str], is_stale: bool) -> float:
        base = 1.0
        # Deduct for each missing optional field
        base -= 0.05 * len(missing_fields)
        # Heavier deduction for missing salary or position
        if "salary" in missing_fields:
            base -= 0.15
        if "roster_position" in missing_fields:
            base -= 0.15
        # Deduct for stale data
        if is_stale:
            base -= 0.20
        # Deduct for unknown injury/starting status
        row = features.loc[idx]
        if row.get("injury_status", "unknown") == "unknown":
            base -= 0.05
        if row.get("starting_status", "unknown") == "unknown":
            base -= 0.05
        # Deduct for insufficient sample
        if pd.isna(row.get("avg_fp_last_5")):
            base -= 0.10
        return max(0.10, round(base, 2))

    # ── DFS Metrics ───────────────────────────────────────────

    def calculate_value(self, features: pd.DataFrame, idx: int,
                        median: float, salary: Optional[int]) -> Optional[float]:
        if salary is None or salary == 0:
            return None
        return round(median / (salary / 1000), 2)

    def calculate_matchup_score(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        row = features.loc[idx]
        opp_def = row.get("opponent_def_rating")
        if pd.isna(opp_def):
            return None
        return round(max(0.0, min(100.0, 100.0 - float(opp_def))), 1)

    def calculate_correlation(self, player_a: int, player_b: int,
                              features: pd.DataFrame) -> Optional[float]:
        return None  # Requires team-level correlation data — unavailable Phase 7A

    # ── Explanation ───────────────────────────────────────────

    def explain_projection(self, features: pd.DataFrame, idx: int,
                           median: float, floor: float, ceiling: float,
                           missing_fields: List[str], is_stale: bool) -> str:
        row = features.loc[idx]
        name = row.get("name", f"Player #{row.get('id', '?')}")
        parts = [f"Projection for {name}: median {median:.1f}, floor {floor:.1f}, ceiling {ceiling:.1f} fantasy points."]

        avg = row.get("avg_fp_last_5")
        if not pd.isna(avg):
            parts.append(f"Based on a recent 5-game average of {avg:.1f} FP.")
        else:
            parts.append("Recent game-log data is unavailable. Projection uses baseline estimate.")

        injury = row.get("injury_status", "unknown")
        parts.append(f"Injury status: {injury}.")

        starter = row.get("starting_status", "unknown")
        parts.append(f"Starting status: {starter}.")

        if missing_fields:
            parts.append(f"Missing data: {', '.join(sorted(missing_fields))}.")
        if is_stale:
            parts.append("WARNING: Data is stale and may not reflect current conditions.")

        return " ".join(parts)

    # ── Platform Rules ────────────────────────────────────────

    def validate_platform_rules(self, lineup: List[int],
                                features: pd.DataFrame, platform: str) -> List[str]:
        errors = []
        if platform.lower() not in ("draftkings", "fanduel"):
            errors.append(f"Unsupported platform: {platform}")
            return errors

        min_players = DK_MIN_PLAYERS if platform.lower() == "draftkings" else FD_MIN_PLAYERS
        cap = DK_SALARY_CAP if platform.lower() == "draftkings" else FD_SALARY_CAP

        if len(lineup) != min_players:
            errors.append(f"Lineup must have exactly {min_players} players, got {len(lineup)}")

        total_salary = 0
        for pid in lineup:
            match = features[features["id"] == pid]
            if match.empty:
                errors.append(f"Player {pid} not found in feature data")
            else:
                total_salary += int(match.iloc[0]["salary"])
        if total_salary > cap:
            errors.append(f"Salary ${total_salary:,} exceeds ${cap:,} cap")

        return errors


# ── Adapter registry ──────────────────────────────────────────

_ADAPTERS: Dict[str, SportAdapter] = {
    "nba": NBAAdapter(),
    "NBA": NBAAdapter(),
}


def get_adapter(sport: str) -> SportAdapter:
    """Look up a sport adapter by sport key. Raises UnsupportedSportError."""
    from ai.sport_adapter import UnsupportedSportError

    key = sport.lower()
    adapter = _ADAPTERS.get(key) or _ADAPTERS.get(sport)
    if adapter is None:
        raise UnsupportedSportError(sport)
    return adapter


def registered_sports() -> List[str]:
    return sorted(set(a.sport for a in _ADAPTERS.values()))