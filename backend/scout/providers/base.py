"""
Scout provider abstraction layer.

Defines the pluggable interface for all data providers.
No provider-specific logic lives in this module.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class ProviderCategory(str, Enum):
    INJURY = "injury"
    LINEUPS = "lineups"
    SCHEDULE = "schedule"
    WEATHER = "weather"
    ODDS = "odds"
    SALARY = "salary"
    ROSTER = "roster"
    STATUS = "status"


class DataFreshness(str, Enum):
    FRESH = "fresh"            # < 15 min old
    RECENT = "recent"          # 15 min – 1 hour
    STALE = "stale"            # 1 – 4 hours
    EXPIRED = "expired"        # > 4 hours
    UNKNOWN = "unknown"        # never synced


@dataclass
class ProviderStatus:
    """Snapshot of a provider's current health."""
    provider_name: str
    category: ProviderCategory
    sport: str
    is_healthy: bool
    last_sync: Optional[datetime] = None
    last_sync_result: Optional[str] = None
    freshness: DataFreshness = DataFreshness.UNKNOWN
    latency_ms: Optional[float] = None
    error_count: int = 0
    data_source_mode: str = "live"  # "live", "cached", "demo"


@dataclass
class ProviderResult:
    """Result from a provider data fetch."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now())


class ScoutProvider(ABC):
    """Abstract base for all data source adapters."""

    name: str
    category: ProviderCategory

    @abstractmethod
    async def fetch(self, sport: str, **kwargs) -> ProviderResult:
        """Fetch data from the provider. Must be implemented per adapter."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Ping the provider. Returns True if reachable."""

    @abstractmethod
    def last_sync_time(self) -> Optional[datetime]:
        """Return the last successful sync timestamp."""

    def freshness(self) -> DataFreshness:
        """Calculate freshness based on last sync time."""
        last = self.last_sync_time()
        if last is None:
            return DataFreshness.UNKNOWN
        from datetime import timezone as _tz
        delta = (datetime.now(_tz.utc) - last).total_seconds()
        if delta < 900:      # 15 minutes
            return DataFreshness.FRESH
        elif delta < 3600:   # 1 hour
            return DataFreshness.RECENT
        elif delta < 14400:  # 4 hours
            return DataFreshness.STALE
        return DataFreshness.EXPIRED


# ── Registry ──────────────────────────────────────────────────

_PROVIDERS: Dict[str, ScoutProvider] = {}


def register_provider(provider: ScoutProvider) -> None:
    """Register a provider in the global registry."""
    key = f"{provider.category.value}:{provider.name}"
    _PROVIDERS[key] = provider


def get_provider(category: ProviderCategory, name: str) -> Optional[ScoutProvider]:
    """Look up a provider by category and name."""
    return _PROVIDERS.get(f"{category.value}:{name}")


def list_providers() -> List[str]:
    """Return all registered provider keys."""
    return sorted(_PROVIDERS.keys())


def list_provider_statuses() -> List[ProviderStatus]:
    """Return health status for all registered providers."""
    results = []
    for key, provider in _PROVIDERS.items():
        cat, name = key.split(":", 1)
        results.append(ProviderStatus(
            provider_name=name,
            category=ProviderCategory(cat),
            sport="nba",
            is_healthy=True,
            last_sync=provider.last_sync_time(),
            freshness=provider.freshness(),
        ))
    return results
