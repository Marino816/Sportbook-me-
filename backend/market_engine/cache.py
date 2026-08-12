"""
SB ME Market Cache — shared SGO response cache for all five tools.

Coordinates caching so one SGO fetch feeds all tools.
Tracks usage for rate-limit awareness.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from providers.sportsgameodds import SportsGameOddsProvider
from providers.normalizer import SportsGameOddsNormalizer
from market_engine import MarketIdentity, MarketType, BookmakerLine, MarketSnapshot

logger = logging.getLogger(__name__)

# Cache TTLs (seconds)
CACHE_TTL = {
    "events": 900,         # 15 min
    "odds": 120,           # 2 min (pre-game market moves)
    "props": 300,          # 5 min
    "fair_odds": 300,
    "consensus": 300,
    "scores": 60,          # 1 min (live)
    "players": 86400,      # 24h
    "teams": 86400,
    "usage": 3600,
}


@dataclass
class CachedEntry:
    data: any
    fetched_at: float
    ttl: int


@dataclass
class CacheStats:
    requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    objects_consumed: int = 0
    last_request_at: Optional[datetime] = None

    def record_hit(self):
        self.cache_hits += 1

    def record_miss(self, objects: int = 1):
        self.requests += 1
        self.cache_misses += 1
        self.objects_consumed += objects
        self.last_request_at = datetime.now(timezone.utc)


class MarketCache:
    """
    Shared cache for SGO responses. A single event fetch feeds:
    - Live Odds Tracker
    - Odds Comparison
    - Player Props Analyzer
    - Arbitrage Scanner
    - Parlay Builder
    - SB ME AI
    """

    def __init__(self):
        self._cache: dict[str, CachedEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.stats = CacheStats()
        self._provider: SportsGameOddsProvider | None = None
        self._normalizer = SportsGameOddsNormalizer()

    async def __aenter__(self):
        self._provider = SportsGameOddsProvider()
        await self._provider.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._provider:
            await self._provider.__aexit__(*args)

    async def _cached(self, key: str, ttl_key: str, fetch_fn):
        """Fetch with TTL cache + dedup lock."""
        now = time.time()
        ttl = CACHE_TTL.get(ttl_key, 300)

        entry = self._cache.get(key)
        if entry and (now - entry.fetched_at) < entry.ttl:
            self.stats.record_hit()
            return entry.data

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._cache.get(key)
            if entry and (now - entry.fetched_at) < entry.ttl:
                self.stats.record_hit()
                return entry.data

            data = await fetch_fn()
            self.stats.record_miss()
            self._cache[key] = CachedEntry(data=data, fetched_at=time.time(), ttl=ttl)
            return data

    # ── Event-level fetch (one call feeds everything) ──

    async def get_event_data(self, event_id: str) -> dict:
        """Fetch all market data for an event (props + odds + fair)."""
        key = f"event_data:{event_id}"

        async def _fetch():
            odds, props, fair, consensus = await asyncio.gather(
                self._provider.get_odds(event_id),
                self._provider.get_player_props(event_id),
                self._provider.get_fair_odds(event_id),
                self._provider.get_consensus(event_id),
                return_exceptions=True,
            )
            return {
                "odds": odds if not isinstance(odds, Exception) else None,
                "props": props if not isinstance(props, Exception) else None,
                "fair_odds": fair if not isinstance(fair, Exception) else None,
                "consensus": consensus if not isinstance(consensus, Exception) else None,
            }

        return await self._cached(key, "props", _fetch)

    async def get_events(self, league_id: str = "MLB"):
        key = f"events:{league_id}"

        async def _fetch():
            return await self._provider.get_events(league_id=league_id)

        return await self._cached(key, "events", _fetch)

    async def get_usage(self):
        return await self._cached("usage", "usage",
            lambda: self._provider.get_usage())

    def invalidate(self, key: str = None):
        """Clear cache entries. If key is None, clear all."""
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)