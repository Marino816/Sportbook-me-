"""
Live Context Provider Architecture for SPORTBOOK ME DFS AI.

Centralized data freshness, provider abstraction, and context aggregation
for MLB optimizer, Scout, and SB ME Intelligent AI.

Data Modes:
  TRIAL_SCRAMBLED  — SportsDataIO trial (scrambled)
  LIVE_PRODUCTION  — Paid/unscrambled production entitlement
  UNAVAILABLE      — Feed not available under current tier
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class DataFreshness(str, Enum):
    FRESH = "fresh"          # < 15 min
    AGING = "aging"          # 15 min – 1 hour
    STALE = "stale"          # 1 – 4 hours
    UNAVAILABLE = "unavailable"  # never synced / feed down


class PlayerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PROBABLE = "PROBABLE"
    QUESTIONABLE = "QUESTIONABLE"
    DOUBTFUL = "DOUBTFUL"
    OUT = "OUT"
    IL = "IL"
    SUSPENDED = "SUSPENDED"
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    PROJECTED = "PROJECTED"
    SCRATCHED = "SCRATCHED"


class DataMode(str, Enum):
    TRIAL_SCRAMBLED = "TRIAL_SCRAMBLED"
    LIVE_PRODUCTION = "LIVE_PRODUCTION"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class FreshnessMeta:
    source: str = "sportsdataio"
    provider: str = "sportsdataio"
    updated_at: Optional[datetime] = None
    data_mode: DataMode = DataMode.TRIAL_SCRAMBLED

    def age_seconds(self) -> float | None:
        if self.updated_at is None:
            return None
        return (datetime.now(timezone.utc) - self.updated_at).total_seconds()

    def freshness(self) -> DataFreshness:
        age = self.age_seconds()
        if age is None:
            return DataFreshness.UNAVAILABLE
        if age < 900:
            return DataFreshness.FRESH
        if age < 3600:
            return DataFreshness.AGING
        return DataFreshness.STALE

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "provider": self.provider,
            "updated_at": str(self.updated_at) if self.updated_at else None,
            "age_seconds": round(self.age_seconds()) if self.age_seconds() else None,
            "freshness": self.freshness().value,
            "data_mode": self.data_mode.value,
        }


@dataclass
class LiveContext:
    """Aggregated live context for a selected MLB slate."""
    slate_id: int
    sport: str = "MLB"
    platform: str = "draftkings"
    data_mode: DataMode = DataMode.TRIAL_SCRAMBLED

    # Slate metadata
    slate_label: str = ""
    slate_date: str = ""
    game_count: int = 0

    # Player pool
    player_count: int = 0
    salary_count: int = 0
    projection_count: int = 0

    # Status counts
    confirmed_starters: int = 0
    probable_starters: int = 0
    injury_count: int = 0
    scratched_count: int = 0

    # Context availability
    starting_lineups_available: bool = False
    injuries_available: bool = False
    weather_available: bool = False
    odds_available: bool = False

    # Freshness
    freshness: FreshnessMeta = field(default_factory=FreshnessMeta)

    # Warnings
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "slate_id": self.slate_id,
            "sport": self.sport,
            "platform": self.platform,
            "data_mode": self.data_mode.value,
            "slate_label": self.slate_label,
            "slate_date": self.slate_date,
            "game_count": self.game_count,
            "player_count": self.player_count,
            "salary_count": self.salary_count,
            "projection_count": self.projection_count,
            "confirmed_starters": self.confirmed_starters,
            "probable_starters": self.probable_starters,
            "injury_count": self.injury_count,
            "scratched_count": self.scratched_count,
            "starting_lineups_available": self.starting_lineups_available,
            "injuries_available": self.injuries_available,
            "weather_available": self.weather_available,
            "odds_available": self.odds_available,
            "freshness": self.freshness.to_dict(),
            "warnings": self.warnings,
        }


@dataclass
class ProviderCapability:
    """What a provider can deliver under current entitlement."""
    schedule: bool = False
    slates: bool = False
    players: bool = True
    salaries_dk: bool = True
    salaries_fd: bool = True
    projections: bool = True
    injuries: bool = False      # SCRAMBLED in trial
    starting_lineups: bool = False
    probable_pitchers: bool = False
    batting_order: bool = False
    weather: bool = False
    odds: bool = False
    game_status: bool = False

    @classmethod
    def trial(cls):
        return cls(
            schedule=True, slates=True, players=True,
            salaries_dk=True, salaries_fd=True, projections=True,
            injuries=False, starting_lineups=False,
            probable_pitchers=False, batting_order=False,
            weather=False, odds=False, game_status=False,
        )

    @classmethod
    def production(cls):
        return cls(
            schedule=True, slates=True, players=True,
            salaries_dk=True, salaries_fd=True, projections=True,
            injuries=True, starting_lineups=True,
            probable_pitchers=True, batting_order=True,
            weather=True, odds=True, game_status=True,
        )