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

# Cache TTLs (seconds) — Rookie nested events update ~every 3 minutes
CACHE_TTL = {
    "events": 180,
    "odds": 180,
    "props": 180,
    "fair_odds": 180,
    "consensus": 180,
    "scores": 180,
    "players": 86400,      # 24h
    "teams": 86400,
    "usage": 1800,
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
        """Return nested /v2/events data from the canonical cache.

        Dedicated /odds/{id}, /props, /fair-odds, /consensus are not called.
        Customer market tools should prefer providers.nested_events helpers.
        """
        key = f"event_data:{event_id}"

        async def _fetch():
            from providers.nested_events import (
                find_cached_event,
                find_event_by_id,
                load_cached_or_fetch_events,
            )
            evt = find_cached_event(event_id)
            if evt is None:
                from providers.sgo_rookie import ROOKIE_LEAGUE_IDS
                for lg in ROOKIE_LEAGUE_IDS:
                    events = await load_cached_or_fetch_events(lg)
                    evt = find_event_by_id(events, event_id)
                    if evt is not None:
                        break
            return {
                "nested": evt,
                "odds": None,
                "props": None,
                "fair_odds": None,
                "consensus": None,
            }

        return await self._cached(key, "props", _fetch)

    async def get_events(self, league_id: str = "MLB"):
        """Nested SBEvent dicts from Redis, with one SDK /v2/events fill on miss."""
        from providers.nested_events import load_cached_or_fetch_events
        key = f"events:{league_id}"

        async def _fetch():
            return await load_cached_or_fetch_events(league_id)

        return await self._cached(key, "events", _fetch)

    async def get_usage(self):
        from providers.sdk_provider import SdkSgoProvider
        return await self._cached("usage", "usage", SdkSgoProvider().get_usage)

    def invalidate(self, key: str = None):
        """Clear cache entries. If key is None, clear all."""
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)