"""SportsGameOdds Integration Service — Redis-backed cache, single-flight, LKG fallback."""

import asyncio
import dataclasses
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from providers.sportsgameodds import SportsGameOddsProvider, SgoRateLimitError
from providers.normalizer import (
    SportsGameOddsNormalizer,
    NormalizedEvent,
    NormalizedGameOdds,
    NormalizedPlayerProp,
    NormalizedPlayer,
    NormalizedTeam,
    GameEnvironment,
)

logger = logging.getLogger(__name__)

# Cache TTLs (seconds) — shorter for live, longer for static
CACHE_TTL = {
    "sports": 86400,       # 24h
    "leagues": 86400,
    "teams": 86400,
    "players": 86400,
    "events": 180,         # ~3 min Rookie nested-event cadence
    "odds": 180,
    "props": 180,
    "scores": 180,
    "fair_odds": 180,
    "consensus": 180,
    "stats": 3600,
    "usage": 1800,
}

# Redis key prefix to namespace our cache
PREFIX = "sgo_cache"

# In-flight dedup locks (global, not per-instance)
_locks: dict[str, asyncio.Lock] = {}


def _redis():
    """Lazy Redis client."""
    from providers.redis_client import get_redis_client
    return get_redis_client()


def _redis_set(key: str, value: bytes, ttl: int):
    r = _redis()
    if r is None:
        return
    try:
        r.set(f"{PREFIX}:{key}", value, ex=ttl)
    except Exception as e:
        logger.debug(f"Redis write failed for {key}: {e}")


def _redis_get(key: str) -> Optional[bytes]:
    r = _redis()
    if r is None:
        return None
    try:
        return r.get(f"{PREFIX}:{key}")
    except Exception as e:
        logger.debug(f"Redis read failed for {key}: {e}")
        return None


def _redis_delete(key: str):
    r = _redis()
    if r is None:
        return
    try:
        r.delete(f"{PREFIX}:{key}")
    except Exception:
        pass


@dataclass
class CachedEntry:
    data: any
    fetched_at: float
    ttl: int
    source: str  # "live" or "cached"


class SGOIntegration:
    """Redis-backed integration service with single-flight dedup and LKG fallback."""

    def __init__(self):
        self._provider: SportsGameOddsProvider | None = None
        self._local_cache: dict[str, CachedEntry] = {}
        self._request_count = 0
        self._rate_limited_until: float = 0.0

    async def __aenter__(self):
        self._provider = SportsGameOddsProvider()
        await self._provider.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._provider:
            await self._provider.__aexit__(*args)

    # ── Core cache + fetch with LKG fallback ──────────────────

    async def _fetch_or_cache(self, key: str, ttl_key: str, fetch_fn, normalize_fn=None) -> tuple[any, str]:
        """
        Fetch with: Redis → local → LKG → upstream (single-flight dedup).

        Returns (data, source) where source is "live", "cached", or "lkg".
        """
        ttl = CACHE_TTL.get(ttl_key, 300)
        now = time.time()

        # 1. Local cache hit
        local = self._local_cache.get(key)
        if local and (now - local.fetched_at) < local.ttl:
            return local.data, local.source

        # 2. Redis cache hit
        try:
            raw = _redis_get(key)
            if raw:
                data = json.loads(raw)
                # For normalized objects, this will be dicts — clients must handle both
                self._local_cache[key] = CachedEntry(
                    data=data, fetched_at=now, ttl=ttl, source="cached"
                )
                return data, "cached"
        except Exception:
            pass

        # 3. Single-flight dedup: only one request per key globally
        lock = _locks.setdefault(key, asyncio.Lock())
        acquired = False
        wait_timeout = 4.0  # max wait for another in-flight request
        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=wait_timeout)
        except asyncio.TimeoutError:
            pass

        if not acquired:
            # Another request is already fetching — return last-known-good or empty
            # Try local first, then Redis
            local = self._local_cache.get(key)
            if local:
                return local.data, "lkg"
            raw = _redis_get(key)
            if raw:
                return json.loads(raw), "lkg"
            return None, "unavailable"

        try:
            # Double-check after acquiring lock
            local = self._local_cache.get(key)
            if local and (now - local.fetched_at) < local.ttl:
                return local.data, local.source
            raw = _redis_get(key)
            if raw:
                data = json.loads(raw)
                self._local_cache[key] = CachedEntry(
                    data=data, fetched_at=now, ttl=ttl, source="cached"
                )
                return data, "cached"

            # 4. Upstream fetch
            try:
                raw_data = await fetch_fn()
            except SgoRateLimitError as e:
                logger.warning(f"SGO 429 on {key}, falling back to LKG: {e}")
                # Return last-known-good from local or Redis
                local = self._local_cache.get(key)
                if local:
                    return local.data, "lkg"
                raw = _redis_get(key)
                if raw:
                    return json.loads(raw), "lkg"
                return None, "unavailable"
            except Exception as e:
                logger.error(f"SGO fetch failed for {key}: {e}")
                local = self._local_cache.get(key)
                if local:
                    return local.data, "lkg"
                raw = _redis_get(key)
                if raw:
                    return json.loads(raw), "lkg"
                raise

            # Normalize
            if normalize_fn and raw_data is not None:
                data = normalize_fn(raw_data)
            else:
                data = raw_data

            # Store
            self._request_count += 1
            self._local_cache[key] = CachedEntry(
                data=data, fetched_at=now, ttl=ttl, source="live"
            )

            # Write to Redis (best-effort) with proper dataclass→dict serialization
            try:
                if isinstance(data, list) and data and dataclasses.is_dataclass(data[0]):
                    serialized = json.dumps([dataclasses.asdict(d) for d in data], default=str)
                elif dataclasses.is_dataclass(data):
                    serialized = json.dumps(dataclasses.asdict(data), default=str)
                else:
                    serialized = json.dumps(data, default=str)
                _redis_set(key, serialized.encode(), ttl)
            except Exception:
                pass

            return data, "live"

        finally:
            lock.release()

    # ── High-level queries ────────────────────────────────────

    async def get_events(self, league_id: str) -> list:
        key = f"events:{league_id}"
        data, source = await self._fetch_or_cache(key, "events",
            lambda: self._provider.get_events(league_id=league_id),
            normalize_fn=lambda raw: [SportsGameOddsNormalizer.normalize_event(e) for e in raw]
        )
        return data if data is not None else []

    async def get_raw_events(self, league_id: str) -> list:
        """Return raw SGO event dicts preserving full odds/players/teams data."""
        key = f"raw_events:{league_id}"
        data, source = await self._fetch_or_cache(key, "events",
            lambda: self._provider.get_events(league_id=league_id)
        )
        return data if data is not None else []

    async def get_sb_events(self, league_id: str) -> list:
        """Fetch normalized SBEvent objects via the official SDK."""
        from providers.sdk_provider import SdkSgoProvider
        from providers.sbevent import from_sdk_event
        provider = SdkSgoProvider()
        raw = await provider.get_raw_sdk_events(league_id)
        return [from_sdk_event(e) for e in raw]

    async def get_odds(self, event_id: str) -> Optional[dict]:
        """Nested /v2/events markets — never dedicated /odds/{id}."""
        from providers.nested_events import extract_nested_odds_payload, find_cached_event
        evt = find_cached_event(event_id)
        return extract_nested_odds_payload(evt) if evt else None

    async def get_player_props(self, event_id: str) -> list:
        from providers.nested_events import find_cached_event, sbevent_player_props
        evt = find_cached_event(event_id)
        return sbevent_player_props(evt) if evt else []

    async def get_fair_odds(self, event_id: str) -> Optional[dict]:
        from providers.nested_events import extract_nested_fair_odds, find_cached_event
        evt = find_cached_event(event_id)
        if not evt:
            return None
        return {"event_id": event_id, "source": "nested_v2_events", "markets": extract_nested_fair_odds(evt)}

    async def get_consensus(self, event_id: str) -> Optional[dict]:
        from providers.nested_events import extract_nested_consensus, find_cached_event
        evt = find_cached_event(event_id)
        return extract_nested_consensus(evt) if evt else None

    async def get_scores(self, event_id: str) -> Optional[dict]:
        from providers.nested_events import find_cached_event
        evt = find_cached_event(event_id)
        if not evt:
            return None
        return {
            "event_id": event_id,
            "status": evt.get("status"),
            "home_score": evt.get("home_score"),
            "away_score": evt.get("away_score"),
            "period": evt.get("period"),
            "results": evt.get("results"),
            "source": "nested_v2_events",
        }

    async def get_usage(self) -> Optional[dict]:
        from providers.sdk_provider import SdkSgoProvider
        return await SdkSgoProvider().get_usage()

    async def get_leagues(self) -> list:
        from providers.sdk_provider import SdkSgoProvider
        return await SdkSgoProvider().get_leagues()

    async def get_sports(self) -> list:
        key = "sports"
        data, source = await self._fetch_or_cache(key, "sports",
            lambda: self._provider.get_sports()
        )
        return data if data is not None else []

    async def get_teams(self, league: Optional[str] = None) -> list:
        key = f"teams:{league or 'all'}"
        data, source = await self._fetch_or_cache(key, "teams",
            lambda: self._provider.get_teams(league=league),
            normalize_fn=lambda raw: [SportsGameOddsNormalizer.normalize_team(t) for t in raw]
        )
        return data if data is not None else []

    async def get_players(self, league_id: str = None, team: str = None) -> list:
        key = f"players:{league_id or 'all'}:{team or 'all'}"
        data, source = await self._fetch_or_cache(key, "players",
            lambda: self._provider.get_players(league_id=league_id, team=team),
            normalize_fn=lambda raw: [SportsGameOddsNormalizer.normalize_player(p) for p in raw]
        )
        return data if data is not None else []

    async def get_player_stats(self, player_id: str) -> Optional[dict]:
        key = f"player_stats:{player_id}"
        data, source = await self._fetch_or_cache(key, "stats",
            lambda: self._provider.get_player_stats(player_id)
        )
        return data

    async def get_team_stats(self, team_id: str) -> Optional[dict]:
        key = f"team_stats:{team_id}"
        data, source = await self._fetch_or_cache(key, "stats",
            lambda: self._provider.get_team_stats(team_id)
        )
        return data

    async def build_game_environment(self, event_id: str) -> GameEnvironment:
        from providers.nested_events import derive_game_environment, find_cached_event
        evt = find_cached_event(event_id)
        env = derive_game_environment(evt) if evt else {}
        return GameEnvironment(
            event_id=event_id,
            home_team=env.get("home_abbr") or "",
            away_team=env.get("away_abbr") or "",
            implied_total_home=env.get("sbme_implied_team_total_home"),
            implied_total_away=env.get("sbme_implied_team_total_away"),
            game_total=env.get("sbme_game_total"),
            bookmakers_available=len((evt or {}).get("bookmakers") or []),
        )