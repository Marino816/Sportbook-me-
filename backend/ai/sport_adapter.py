"""
Sport adapter interface for Sportsbook Me DFS AI.

Each sport implements this contract. Unsupported sports raise clear errors.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import pandas as pd


class SportAdapter(ABC):
    """Abstract base for sport-specific projection adapters."""

    sport: str
    league: str

    @abstractmethod
    def validate_input(self, data: pd.DataFrame) -> List[str]:
        """Return list of validation errors. Empty = valid."""

    @abstractmethod
    def normalize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names, types, and units."""

    @abstractmethod
    def build_features(self, data: pd.DataFrame, game_logs: pd.DataFrame,
                       matchups: pd.DataFrame, injuries: pd.DataFrame) -> pd.DataFrame:
        """Build feature matrix for projection model."""

    @abstractmethod
    def calculate_projection(self, features: pd.DataFrame, idx: int) -> float:
        """Median projection for a single player/fighter row."""

    @abstractmethod
    def calculate_floor(self, features: pd.DataFrame, idx: int, median: float) -> float:
        """10th-percentile outcome."""

    @abstractmethod
    def calculate_ceiling(self, features: pd.DataFrame, idx: int, median: float) -> float:
        """90th-percentile outcome."""

    @abstractmethod
    def calculate_boom_probability(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        """Probability of exceeding ceiling projection. None if unavailable."""

    @abstractmethod
    def calculate_bust_probability(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        """Probability of falling below floor projection. None if unavailable."""

    @abstractmethod
    def calculate_confidence(self, features: pd.DataFrame, idx: int,
                             missing_fields: List[str], is_stale: bool) -> float:
        """0-1 confidence score based on data quality and availability."""

    @abstractmethod
    def calculate_value(self, features: pd.DataFrame, idx: int,
                        median: float, salary: Optional[int]) -> Optional[float]:
        """Value = projected_fp / (salary/1000). None if salary missing."""

    @abstractmethod
    def calculate_matchup_score(self, features: pd.DataFrame, idx: int) -> Optional[float]:
        """0-100 matchup favorability. None if matchup data unavailable."""

    @abstractmethod
    def calculate_correlation(self, player_a: int, player_b: int,
                              features: pd.DataFrame) -> Optional[float]:
        """Correlation coefficient between two players. None if unavailable."""

    @abstractmethod
    def explain_projection(self, features: pd.DataFrame, idx: int,
                           median: float, floor: float, ceiling: float,
                           missing_fields: List[str], is_stale: bool) -> str:
        """Generate structured explanation text from available data."""

    @abstractmethod
    def validate_platform_rules(self, lineup: List[int],
                                features: pd.DataFrame, platform: str) -> List[str]:
        """Return list of rule violations. Empty = valid lineup."""


class UnsupportedSportError(Exception):
    """Raised when a sport has no registered adapter."""
    def __init__(self, sport: str):
        super().__init__(f"Sport '{sport}' is not supported. Available: NBA")
