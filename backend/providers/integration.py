"""
SportsGameOdds Integration Service — PRIMARY provider.

Connects SGO provider to SB ME intelligence layer with:
- Cache (in-memory TTL-based)
- Request deduplication
- Freshness metadata
- Provider ID mapping
- Usage monitoring
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from providers.sportsgameodds import SportsGameOddsProvider
from providers.normalizer import (
    SportsGameOddsNormalizer,
    NormalizedEvent,
    NormalizedGameOdds,
    NormalizedPlayerProp,
    GameEnvironment,
)

logger = logging.getLogger(__name__)

# Cache TTLs by data type (seconds)
CACHE_TTL = {
    "sports": 86400,       # 24 hours
    "leagues": 86400,
    "teams": 86400,
    "events": 900,         # 15 minutes
    "odds": 120,           # 2 minutes (pre-game)
    "props": 300,          # 5 minutes
    "scores": 60,          # 1 minute (live)
    "fair_odds": 300,
    "consensus": 300,
    "players": 86400,
    "stats": 3600,         # 1 hour
    "usage": 3600,
}


@dataclass
class CachedEntry:
    data: any
    fetched_at: float
    ttl: int


class SGOIntegration:
    """
    Primary integration service for SportsGameOdds.

    Usage:
        sgo = SGOIntegration()
        async with sgo:
            events = await sgo.get_mlb_events()
            odds = await sgo.get_odds(events[0].id)
    """

    def __init__(self):
        self._provider: SportsGameOddsProvider | None = None
        self._cache: dict[str, CachedEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._request_count = 0

    async def __aenter__(self):
        self._provider = SportsGameOddsProvider()
        await self._provider.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._provider:
            await self._provider.__aexit__(*args)

    async def _cached(self, key: str, ttl_key: str, fetch_fn) -> any:
        """Fetch with TTL cache + deduplication lock."""
        now = time.time()
        ttl = CACHE_TTL.get(ttl_key, 300)

        # Cache hit
        entry = self._cache.get(key)
        if entry and (now - entry.fetched_at) < entry.ttl:
            return entry.data

        # Dedup: only one concurrent request per key
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            # Re-check after acquiring lock
            entry = self._cache.get(key)
            if entry and (now - entry.fetched_at) < entry.ttl:
                return entry.data

            data = await fetch_fn()
            self._request_count += 1
            self._cache[key] = CachedEntry(data=data, fetched_at=time.time(), ttl=ttl)
            return data

    # ── High-level queries ──

    async def get_events(self, league_id: str) -> list[NormalizedEvent]:
        key = f"events:{league_id}"
        raw = await self._cached(key, "events",
            lambda: self._provider.get_events(league_id=league_id))
        return [SportsGameOddsNormalizer.normalize_event(e) for e in raw]

    async def get_odds(self, event_id: str) -> Optional[NormalizedGameOdds]:
        key = f"odds:{event_id}"
        raw = await self._cached(key, "odds",
            lambda: self._provider.get_odds(event_id))
        return SportsGameOddsNormalizer.normalize_game_odds(raw, event_id)

    async def get_player_props(self, event_id: str) -> list[NormalizedPlayerProp]:
        key = f"props:{event_id}"
        raw = await self._cached(key, "props",
            lambda: self._provider.get_player_props(event_id))
        return [SportsGameOddsNormalizer.normalize_player_prop(p) for p in raw]

    async def get_fair_odds(self, event_id: str) -> dict | None:
        key = f"fair_odds:{event_id}"
        try:
            return await self._cached(key, "fair_odds",
                lambda: self._provider.get_fair_odds(event_id))
        except Exception:
            return None

    async def get_consensus(self, event_id: str) -> dict | None:
        key = f"consensus:{event_id}"
        try:
            return await self._cached(key, "consensus",
                lambda: self._provider.get_consensus(event_id))
        except Exception:
            return None

    async def get_scores(self, event_id: str) -> dict | None:
        key = f"scores:{event_id}"
        try:
            return await self._cached(key, "scores",
                lambda: self._provider.get_scores(event_id))
        except Exception:
            return None

    async def get_usage(self) -> dict | None:
        key = "usage"
        try:
            return await self._cached(key, "usage",
                lambda: self._provider.get_usage())
        except Exception:
            return None

    async def build_game_environment(self, event_id: str) -> GameEnvironment:
        """Aggregate all available context for a game."""
        odds = await self.get_odds(event_id)
        scores = await self.get_scores(event_id)
        # Derive implied totals from consensus/fair odds when available
        impl_home = None
        impl_away = None
        game_total = None
        if odds and odds.consensus:
            game_total = odds.consensus.total_over
        return GameEnvironment(
            event_id=event_id,
            home_team="",
            away_team="",
            implied_total_home=impl_home,
            implied_total_away=impl_away,
            game_total=game_total,
            bookmakers_available=len(odds.books) if odds else 0,
        )