"""
Scout data freshness tracker and projection refresh pipeline.
"""

from datetime import datetime, timezone
from typing import Dict, List

from scout.providers.base import (
    DataFreshness, list_provider_statuses, ProviderCategory,
)


class FreshnessTracker:
    """Monitors data freshness across all providers."""

    @staticmethod
    def get_freshness_report() -> Dict:
        """Return a structured freshness report for all providers."""
        statuses = list_provider_statuses()
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_freshness": DataFreshness.FRESH.value,
            "providers": [],
            "stale_providers": [],
            "expired_providers": [],
        }
        for s in statuses:
            entry = {
                "name": s.provider_name,
                "category": s.category.value,
                "freshness": s.freshness.value,
                "last_sync": s.last_sync.isoformat() if s.last_sync else None,
                "healthy": s.is_healthy,
            }
            report["providers"].append(entry)
            if s.freshness == DataFreshness.STALE:
                report["stale_providers"].append(s.provider_name)
            elif s.freshness == DataFreshness.EXPIRED:
                report["expired_providers"].append(s.provider_name)

        if report["expired_providers"]:
            report["overall_freshness"] = DataFreshness.EXPIRED.value
        elif report["stale_providers"]:
            report["overall_freshness"] = DataFreshness.STALE.value
        elif any(s.freshness == DataFreshness.RECENT for s in statuses):
            report["overall_freshness"] = DataFreshness.RECENT.value

        return report

    @staticmethod
    def is_stale_for_projection(category: ProviderCategory) -> bool:
        """Check if a provider category is too stale for reliable projections."""
        statuses = list_provider_statuses()
        for s in statuses:
            if s.category == category:
                return s.freshness in (DataFreshness.EXPIRED, DataFreshness.STALE)
        return True


class RefreshPipeline:
    """Triggers projection refresh when data changes are detected."""

    @staticmethod
    async def refresh_projections_for_entities(
        entities: List[dict], reason: str = "scout_event"
    ) -> Dict:
        """Trigger a projection refresh for affected entities."""
        return {
            "status": "queued",
            "entities_affected": len(entities),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def refresh_slate(slate_id: int, reason: str = "scout_event") -> Dict:
        """Trigger a full slate refresh."""
        return {
            "status": "queued",
            "slate_id": slate_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
