"""SDK-based SGO provider — wraps the official sports-odds-api async SDK client."""

import logging
import os
from typing import Optional

from providers.sbevent import SBEvent, from_sdk_event

logger = logging.getLogger(__name__)


class SdkSgoProvider:
    """
    SportsGameOdds provider using the official AsyncSportsGameOdds SDK client.

    All responses are SDK model objects — never raw dicts.
    """

    def __init__(self, api_key: Optional[str] = None):
        from sports_odds_api import AsyncSportsGameOdds
        key = api_key or os.environ.get("SPORTSGAMEODDS_API_KEY", "")
        self._client = AsyncSportsGameOdds(api_key_header=key)

    async def _get_events(self, league_id: str) -> list:
        """Fetch events via SDK async paginator — each item is an Event."""
        paginator = await self._client.events.get(
            league_id=league_id.upper(),
            odds_available=True,
            limit=50,
        )
        events = []
        async for item in paginator:
            if hasattr(item, 'event_id'):
                events.append(item)
            elif hasattr(item, 'data') and item.data:
                events.extend(item.data)
        return events

    async def get_sb_events(self, league_id: str) -> list[SBEvent]:
        raw = await self._get_events(league_id.upper())
        return [from_sdk_event(e) for e in raw]

    async def get_raw_sdk_events(self, league_id: str) -> list:
        return await self._get_events(league_id.upper())

    async def get_teams(self, league: str) -> list:
        paginator = await self._client.teams.get(league_id=league.upper(), limit=50)
        teams = []
        async for page in paginator:
            if hasattr(page, 'data') and page.data:
                teams.extend(page.data)
        return teams

    async def get_players(self, league_id: str) -> list:
        paginator = await self._client.players.get(league_id=league_id.upper(), limit=100)
        players = []
        async for page in paginator:
            if hasattr(page, 'data') and page.data:
                players.extend(page.data)
        return players

    async def get_sports(self) -> list:
        result = await self._client.sports.get()
        if hasattr(result, 'data') and result.data:
            return result.data
        return result if isinstance(result, list) else []

    async def get_usage(self) -> dict:
        try:
            result = await self._client.account.usage()
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}