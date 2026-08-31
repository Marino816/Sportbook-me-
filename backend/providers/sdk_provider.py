"""SDK-based SGO provider — wraps the official sports-odds-api async SDK client."""

import logging
import os
from typing import Optional

from providers.sbevent import SBEvent, from_sdk_event
from providers.sgo_rookie import (
    NESTED_EVENT_TTL_SECONDS,
    catalog_fallback,
    normalize_league_id,
    parse_account_usage,
)

logger = logging.getLogger(__name__)


class SdkSgoProvider:
    """
    SportsGameOdds provider using the official AsyncSportsGameOdds SDK client.

    All responses are SDK model objects — never raw dicts — until SBEvent conversion.
    """

    def __init__(self, api_key: Optional[str] = None):
        from sports_odds_api import AsyncSportsGameOdds
        key = api_key or os.environ.get("SPORTSGAMEODDS_API_KEY", "")
        # Stainless default max_retries=2 immediately retries 429s and
        # multiplies rate-limit pressure. The httpx adapter already refuses
        # to retry-storm; the SDK client matches that policy. Event consumers
        # must go through load_canonical_sb_events for cache/LKG/cooldown.
        self._client = AsyncSportsGameOdds(api_key_header=key, max_retries=0)

    async def _get_events(
        self,
        league_id: str,
        *,
        finalized: bool = False,
        odds_available: bool = True,
        expand_results: bool = False,
        starts_after: str | None = None,
        starts_before: str | None = None,
        limit: int = 50,
    ) -> list:
        """Fetch events via SDK async paginator with Rookie nested-event flags."""
        league = normalize_league_id(league_id)
        kwargs = dict(
            league_id=league,
            odds_available=odds_available,
            finalized=finalized,
            include_alt_lines=True,
            include_open_close_odds=True,
            limit=limit,
        )
        if expand_results:
            kwargs["expand_results"] = True
        if starts_after:
            kwargs["starts_after"] = starts_after
        if starts_before:
            kwargs["starts_before"] = starts_before
        paginator = await self._client.events.get(**kwargs)
        return [event async for event in paginator]

    async def get_sb_events(self, league_id: str) -> list[SBEvent]:
        raw = await self._get_events(normalize_league_id(league_id), finalized=False, odds_available=True)
        return [from_sdk_event(e) for e in raw]

    async def get_raw_sdk_events(self, league_id: str) -> list:
        return await self._get_events(normalize_league_id(league_id), finalized=False, odds_available=True)

    async def get_finalized_events(
        self,
        league_id: str,
        *,
        starts_after: str | None = None,
        starts_before: str | None = None,
        limit: int = 20,
    ) -> list:
        """Recent finalized events with expanded results (Rookie settlement, not Pro archive)."""
        return await self._get_events(
            normalize_league_id(league_id),
            finalized=True,
            odds_available=False,
            expand_results=True,
            starts_after=starts_after,
            starts_before=starts_before,
            limit=limit,
        )

    async def get_teams(self, league: str) -> list:
        paginator = await self._client.teams.get(league_id=normalize_league_id(league), limit=50)
        teams = []
        async for page in paginator:
            if hasattr(page, "data") and page.data:
                teams.extend(page.data)
        return teams

    async def get_players(self, league_id: str) -> list:
        paginator = await self._client.players.get(league_id=normalize_league_id(league_id), limit=100)
        players = []
        async for page in paginator:
            if hasattr(page, "data") and page.data:
                players.extend(page.data)
        return players

    async def get_sports(self) -> list:
        result = await self._client.sports.get()
        if hasattr(result, "data") and result.data:
            return result.data
        return result if isinstance(result, list) else []

    async def get_leagues(self) -> list[dict]:
        """GET /v2/leagues/ — leagues available to this API key."""
        try:
            paginator = await self._client.leagues.get(limit=100)
            rows = []
            async for item in paginator:
                if hasattr(item, "data") and item.data:
                    rows.extend(item.data)
                else:
                    rows.append(item)
            parsed = []
            for row in rows:
                if isinstance(row, dict):
                    parsed.append({
                        "leagueID": row.get("leagueID") or row.get("league_id"),
                        "name": row.get("name"),
                        "shortName": row.get("shortName") or row.get("short_name"),
                        "sportID": row.get("sportID") or row.get("sport_id"),
                        "enabled": row.get("enabled", True),
                        "source": "sportsgameodds_v2_leagues",
                    })
                else:
                    parsed.append({
                        "leagueID": getattr(row, "league_id", None) or getattr(row, "leagueID", None),
                        "name": getattr(row, "name", None),
                        "shortName": getattr(row, "short_name", None) or getattr(row, "shortName", None),
                        "sportID": getattr(row, "sport_id", None) or getattr(row, "sportID", None),
                        "enabled": getattr(row, "enabled", True),
                        "source": "sportsgameodds_v2_leagues",
                    })
            parsed = [p for p in parsed if p.get("leagueID")]
            return parsed or catalog_fallback()
        except Exception as exc:
            logger.warning("SGO /leagues fetch failed: %s", exc)
            return catalog_fallback()

    async def get_usage(self) -> dict:
        try:
            result = await self._client.account.usage()
            parsed = parse_account_usage(result)
            parsed["cache_ttl_seconds"] = NESTED_EVENT_TTL_SECONDS
            return parsed
        except Exception as exc:
            logger.warning("SGO /account/usage fetch failed: %s", exc)
            return {"available": False, "tier": None, "reason": type(exc).__name__}
