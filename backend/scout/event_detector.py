"""
Scout event detection engine.

Detects changes across all registered providers and generates
structured events with severity, affected entities, and refresh flags.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scout.models import ScoutEvent, ScoutEventSeverity, ScoutEventType
from scout.providers.base import (
    ProviderCategory, DataFreshness, list_provider_statuses,
)
from scout.providers import adapters  # noqa — triggers provider registration


class EventDetector:
    """Monitors providers for changes and emits ScoutEvents."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_providers(self, sport: str = "nba") -> List[ScoutEvent]:
        """Scan all providers for data changes and emit events."""
        events = []
        statuses = list_provider_statuses()

        for status in statuses:
            if status.freshness in (DataFreshness.STALE, DataFreshness.EXPIRED):
                event = await self._create_event(
                    event_type=ScoutEventType.PROJECTION_INVALIDATION,
                    severity=ScoutEventSeverity.WARNING,
                    source=status.provider_name,
                    title=f"{status.provider_name} data is {status.freshness.value}",
                    description=f"Last sync: {status.last_sync}. Freshness: {status.freshness.value}.",
                    sport=sport,
                    refresh_required=True,
                )
                events.append(event)

        return events

    async def detect_injury_change(
        self, player_id: int, old_status: str, new_status: str, sport: str = "nba"
    ) -> ScoutEvent:
        """Emit an injury update event."""
        severity = ScoutEventSeverity.CRITICAL if new_status in ("Out", "Doubtful") else ScoutEventSeverity.WARNING
        return await self._create_event(
            event_type=ScoutEventType.INJURY_UPDATE,
            severity=severity,
            source="injury_feed",
            title=f"Player {player_id} injury status changed",
            description=f"Status: {old_status} → {new_status}",
            sport=sport,
            affected_entities=[{"type": "player", "id": player_id}],
            refresh_required=True,
        )

    async def detect_lineup_change(
        self, team: str, changes: List[dict], sport: str = "nba"
    ) -> ScoutEvent:
        """Starting lineup confirmation or change."""
        return await self._create_event(
            event_type=ScoutEventType.LINEUP_CONFIRMATION,
            severity=ScoutEventSeverity.INFO,
            source="lineups_feed",
            title=f"{team} lineup confirmed",
            description=f"{len(changes)} changes detected",
            sport=sport,
            affected_entities=[{"type": "team", "id": team}],
            refresh_required=True,
        )

    async def detect_odds_movement(
        self, game_id: int, line_type: str, old_val: float, new_val: float, sport: str = "nba"
    ) -> ScoutEvent:
        """Significant odds movement."""
        delta = abs(new_val - old_val)
        severity = ScoutEventSeverity.WARNING if delta >= 2.0 else ScoutEventSeverity.INFO
        return await self._create_event(
            event_type=ScoutEventType.ODDS_MOVEMENT,
            severity=severity,
            source="odds_feed",
            title=f"Odds movement on game {game_id}",
            description=f"{line_type}: {old_val} → {new_val} (Δ {delta:+.1f})",
            sport=sport,
            affected_entities=[{"type": "game", "id": game_id}],
            refresh_required=delta > 1.0,
        )

    async def _create_event(
        self,
        event_type,
        severity,
        source: str,
        title: str,
        description: str = "",
        sport: str = "nba",
        league: str = "NBA",
        affected_entities: list = None,
        refresh_required: bool = False,
    ) -> ScoutEvent:
        """Persist a new ScoutEvent with idempotency guard."""
        # Normalize: accept both strings and enum values
        type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        sev_str = severity.value if hasattr(severity, "value") else str(severity)
        event_id = f"{type_str}:{uuid.uuid4().hex[:12]}"

        # Idempotency: check for recent duplicate
        existing_result = await self.db.execute(
            select(ScoutEvent).where(
                ScoutEvent.event_type == type_str,
                ScoutEvent.source == source,
                ScoutEvent.title == title,
            ).limit(1)
        )
        existing = existing_result.scalars().first()
        if existing:
            return existing

        event = ScoutEvent(
            event_id=event_id,
            event_type=type_str,
            sport=sport,
            league=league,
            severity=sev_str,
            source=source,
            title=title,
            description=description,
            affected_entities=affected_entities or [],
            refresh_required=refresh_required,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
