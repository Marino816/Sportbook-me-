"""
SportsGameOdds API v2 Provider Client.

Primary sports/market intelligence provider for SPORTBOOK ME DFS AI.

Usage:
    provider = SportsGameOddsProvider(api_key=os.getenv("SPORTSGAMEODDS_API_KEY"))
    sports = await provider.get_sports()
"""

import os
import time
import logging
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sportsgameodds.com/v2"
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
DEFAULT_TIMEOUT = 15  # seconds
RATE_LIMIT_PAUSE = 1.2  # seconds between requests (free plan safe)


@dataclass
class ProviderStats:
    requests: int = 0
    responses: int = 0
    errors: int = 0
    retries: int = 0
    last_request_at: Optional[datetime] = None
    objects_consumed: int = 0  # approximate — count paginated objects


class SgoRateLimitError(Exception):
    """Raised when SGO returns HTTP 429. Carries Retry-After seconds."""

    def __init__(self, path: str, retry_after: int):
        self.path = path
        self.retry_after = retry_after
        super().__init__(f"SGO rate-limited ({retry_after}s) on {path}")


class SportsGameOddsProvider:
    """
    Authenticated httpx client for SportsGameOdds API v2.

    Handles:
    - x-api-key authentication
    - timeout (15s default)
    - retries (3 with exponential backoff)
    - rate-limit safety (1.2s inter-request gap)
    - pagination (cursor + page)
    - structured error logging
    - response validation
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SPORTSGAMEODDS_API_KEY", "")
        self.stats = ProviderStats()
        self._last_call = 0.0
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"x-api-key": self.api_key, "Accept": "application/json"},
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with SportsGameOddsProvider() as p:'")
        return self._client

    async def _rate_limit(self):
        """Enforce minimum gap between requests."""
        now = time.monotonic()
        gap = now - self._last_call
        if gap < RATE_LIMIT_PAUSE:
            await asyncio.sleep(RATE_LIMIT_PAUSE - gap)
        self._last_call = time.monotonic()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        paginated: bool = False,
    ) -> dict | list:
        """
        Core request method with retries, error wrapping, and pagination.
        """
        await self._rate_limit()
        self.stats.requests += 1
        self.stats.last_request_at = datetime.now(timezone.utc)
        self.stats.objects_consumed += 1  # count each API response as 1 object

        url = f"{path}" if path.startswith("http") else path
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.request(method, url, params=params)
                self.stats.responses += 1

                # 429 Rate-limit: do NOT retry-storm. Honor Retry-After once,
                # log once, and raise so the cache layer can serve last-known-good.
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            retry_after = int(retry_after)
                        except ValueError:
                            retry_after = RETRY_DELAY
                    else:
                        retry_after = RETRY_DELAY
                    self.stats.errors += 1
                    logger.warning(
                        f"SGO 429 rate-limited on {path}; Retry-After={retry_after}s; "
                        f"surfacing cached data instead of retrying"
                    )
                    raise SgoRateLimitError(path, int(retry_after))

                # Transient server errors: limited retries with backoff.
                if resp.status_code >= 500:
                    logger.warning(f"SGO server error {resp.status_code}, attempt {attempt+1}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                        continue

                resp.raise_for_status()
                data = resp.json()

                if paginated:
                    results = data if isinstance(data, list) else data.get("data", [])
                    # Handle cursor/next-page pagination
                    next_page = data.get("next") if isinstance(data, dict) else None
                    if next_page:
                        more = await self._request("GET", next_page, paginated=True)
                        results.extend(more)
                    self.stats.objects_consumed += len(results) if isinstance(results, list) else 0
                    return results

                return data

            except httpx.TimeoutException:
                logger.error(f"SGO timeout on {path}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except httpx.HTTPStatusError as e:
                self.stats.errors += 1
                logger.error(f"SGO HTTP {e.response.status_code} on {path}: {e.response.text[:200]}")
                raise
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"SGO error on {path}: {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"SGO exhausted retries for {path}")

    # ── Discovery / Audit Methods ──

    async def get_sports(self) -> list:
        """List available sports (MLB, NFL, NBA, NHL, etc.)."""
        return await self._request("GET", "/sports", paginated=True)

    async def get_leagues(self, sport: str = None) -> list:
        """List leagues, optionally filtered by sport."""
        params = {"sport": sport} if sport else None
        return await self._request("GET", "/leagues", params=params, paginated=True)

    async def get_events(self, league_id: str = None, date: str = None,
                       extra_params: dict = None) -> list:
        """List events with leagueID (e.g., 'MLB', 'NFL', 'NBA').

        *extra_params* is merged into the query string for historical
        lookups (e.g. include=results, finalized=true, teamID=…)."""
        params = {"oddsAvailable": "true", "limit": "50"}
        if league_id:
            params["leagueID"] = league_id
        if date:
            params["date"] = date
        if extra_params:
            params.update(extra_params)
        return await self._request("GET", "/events", params=params, paginated=True)

    async def get_event(self, event_id: str) -> dict:
        """Get single event detail."""
        return await self._request("GET", f"/events/{event_id}")

    async def get_teams(self, league: str = None) -> list:
        """List teams, optionally filtered by league."""
        params = {"league": league} if league else None
        return await self._request("GET", "/teams", params=params, paginated=True)

    async def get_players(self, league_id: str = None, team: str = None) -> list:
        """List players with leagueID (e.g., 'MLB', 'NFL')."""
        params = {"limit": "100"}
        if league_id:
            params["leagueID"] = league_id
        if team:
            params["team"] = team
        return await self._request("GET", "/players", params=params, paginated=True)

    async def get_player_stats(self, player_id: str, season: str = None) -> dict:
        """Get player statistics."""
        params = {"season": season} if season else None
        return await self._request("GET", f"/players/{player_id}/stats", params=params)

    async def get_team_stats(self, team_id: str, season: str = None) -> dict:
        """Get team statistics."""
        params = {"season": season} if season else None
        return await self._request("GET", f"/teams/{team_id}/stats", params=params)

    async def get_odds(self, event_id: str) -> dict:
        """Get moneyline, spread, total, alt lines for an event."""
        return await self._request("GET", f"/odds/{event_id}")

    async def get_player_props(self, event_id: str) -> list:
        """Get player prop markets for an event."""
        return await self._request("GET", f"/props/players/{event_id}", paginated=True)

    async def get_team_props(self, event_id: str) -> list:
        """Get team prop markets."""
        return await self._request("GET", f"/props/teams/{event_id}", paginated=True)

    async def get_fair_odds(self, event_id: str) -> dict:
        """Get fair/implied odds."""
        return await self._request("GET", f"/fair-odds/{event_id}")

    async def get_consensus(self, event_id: str) -> dict:
        """Get book consensus lines."""
        return await self._request("GET", f"/consensus/{event_id}")

    async def get_scores(self, event_id: str) -> dict:
        """Get live/historical scores."""
        return await self._request("GET", f"/scores/{event_id}")

    async def get_account(self) -> dict:
        """Get account/plan/usage info."""
        return await self._request("GET", "/account")

    # ── Account ──

    async def get_usage(self) -> dict:
        """Get account usage stats."""
        return await self._request("GET", "/account/usage")