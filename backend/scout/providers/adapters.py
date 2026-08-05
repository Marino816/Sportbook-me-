"""
Concrete Scout provider implementations.

Each provider implements the ScoutProvider interface for a specific
data source. Currently uses demo/placeholder data until external APIs
are fully provisioned.
"""

from datetime import datetime, timezone
from typing import Optional

from scout.providers.base import (
    ScoutProvider, ProviderCategory, ProviderResult, DataFreshness,
    register_provider,
)


class _BaseScoutProvider(ScoutProvider):
    """Common base with in-memory sync tracking."""
    def __init__(self):
        self._last_sync: Optional[datetime] = None
        self._healthy: bool = True

    def last_sync_time(self) -> Optional[datetime]:
        return self._last_sync

    async def health_check(self) -> bool:
        self._healthy = True
        return True

    def _mark_sync(self):
        self._last_sync = datetime.now(timezone.utc)


# ── Injury Provider ──────────────────────────────────────────

class InjuryProvider(_BaseScoutProvider):
    name = "injury_feed"
    category = ProviderCategory.INJURY

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "players": [],
                "source": "demo_injury_feed",
                "sport": sport,
            },
        )


# ── Lineups Provider ─────────────────────────────────────────

class LineupsProvider(_BaseScoutProvider):
    name = "lineups_feed"
    category = ProviderCategory.LINEUPS

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "lineups": [],
                "source": "demo_lineups_feed",
                "sport": sport,
            },
        )


# ── Schedule Provider ────────────────────────────────────────

class ScheduleProvider(_BaseScoutProvider):
    name = "schedule_feed"
    category = ProviderCategory.SCHEDULE

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "games": [],
                "source": "demo_schedule_feed",
                "sport": sport,
            },
        )


# ── Weather Provider ─────────────────────────────────────────

class WeatherProvider(_BaseScoutProvider):
    name = "weather_feed"
    category = ProviderCategory.WEATHER

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "conditions": [],
                "source": "demo_weather_feed",
                "sport": sport,
            },
        )


# ── Odds Provider ────────────────────────────────────────────

class OddsProvider(_BaseScoutProvider):
    name = "odds_feed"
    category = ProviderCategory.ODDS

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "odds": [],
                "source": "demo_odds_feed",
                "sport": sport,
            },
        )


# ── Salary Provider ──────────────────────────────────────────

class SalaryProvider(_BaseScoutProvider):
    name = "salary_feed"
    category = ProviderCategory.SALARY

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "salaries": [],
                "source": "demo_salary_feed",
                "sport": sport,
            },
        )


# ── Roster/Status Provider ───────────────────────────────────

class StatusProvider(_BaseScoutProvider):
    name = "status_feed"
    category = ProviderCategory.STATUS

    async def fetch(self, sport: str = "nba", **kwargs):
        self._mark_sync()
        return ProviderResult(
            success=True,
            data={
                "players": [],
                "source": "demo_status_feed",
                "sport": sport,
            },
        )


# ── Register all providers ───────────────────────────────────

for _cls in [
    InjuryProvider, LineupsProvider, ScheduleProvider,
    WeatherProvider, OddsProvider, SalaryProvider, StatusProvider,
]:
    register_provider(_cls())
