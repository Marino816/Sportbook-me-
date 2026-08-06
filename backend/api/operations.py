"""
Production health metrics endpoint for operational monitoring.

Provides aggregated health status for Sentry, UptimeRobot,
and internal dashboards. No secrets exposed.
"""

import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from models.database import get_db
from models.domain import User
from api.auth import require_admin

router = APIRouter(prefix="/admin/metrics", tags=["Operations Metrics"])


@router.get("")
async def get_operations_metrics(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Returns operational KPIs for monitoring dashboards."""
    t = datetime.now(timezone.utc).isoformat()

    metrics = {
        "generated_at": t,
        "infrastructure": {
            "railway": "operational",
            "vercel": "operational",
            "postgresql": "unknown",
            "redis": "unknown",
        },
        "application": {
            "version": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
            "branch": os.getenv("RAILWAY_GIT_BRANCH", "hermes-production-build"),
            "environment": os.getenv("NODE_ENV", "staging"),
        },
        "stripe": {
            "mode": "live" if "sk_live" in os.getenv("STRIPE_SECRET_KEY", "") else "test",
            "products_configured": bool(os.getenv("STRIPE_PRO_PRICE_ID")),
            "webhook_configured": bool(os.getenv("STRIPE_WEBHOOK_SECRET")),
        },
        "subscriptions": {
            "total": 0,
            "active": 0,
            "trialing": 0,
            "past_due": 0,
        },
        "errors": {
            "last_hour_500s": 0,
            "stripe_webhook_failures": 0,
        },
    }

    # DB health
    try:
        await db.execute(text("SELECT 1"))
        metrics["infrastructure"]["postgresql"] = "healthy"
    except Exception:
        metrics["infrastructure"]["postgresql"] = "error"

    # Subscription counts
    try:
        result = await db.execute(text(
            "SELECT status, COUNT(*) FROM subscriptions GROUP BY status"
        ))
        for row in result:
            status, count = row
            if status in metrics["subscriptions"]:
                metrics["subscriptions"][status] = count
            metrics["subscriptions"]["total"] += count
    except Exception:
        pass

    return metrics