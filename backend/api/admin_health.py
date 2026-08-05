"""
Admin health endpoint for SB-Me Launch Command Center.

Returns operational status of all components without exposing secrets.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from models.database import get_db
from models.domain import User
from api.auth import get_current_user, require_admin

router = APIRouter(prefix="/admin/health", tags=["Admin Health"])


class ComponentStatus(BaseModel):
    name: str
    status: str  # healthy, warning, error, not_instrumented, unavailable
    checked_at: str
    latency_ms: Optional[float] = None
    source: str  # live, configured, static, not_instrumented
    details: str = ""


async def _check_db(db: AsyncSession) -> ComponentStatus:
    start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        # Get migration head
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        head = row[0] if row else "unknown"
        return ComponentStatus(
            name="PostgreSQL", status="healthy", source="live",
            checked_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=round(latency, 1),
            details=f"Connected (migration: {head})",
        )
    except Exception as e:
        return ComponentStatus(
            name="PostgreSQL", status="error", source="live",
            checked_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=(time.time() - start) * 1000,
            details=str(e)[:200],
        )


@router.get("")
async def admin_health(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Returns live health check for all platform components."""
    components = []

    # DB check (live)
    components.append(await _check_db(db))

    # Redis check (not instrumented — no client available in health endpoint)
    components.append(ComponentStatus(
        name="Redis", status="not_instrumented", source="not_instrumented",
        checked_at=datetime.now(timezone.utc).isoformat(),
        details="Redis client not accessible from health endpoint",
    ))

    # Auth (configured)
    jwt_set = bool(os.getenv("JWT_SECRET_KEY"))
    components.append(ComponentStatus(
        name="Authentication", status="healthy" if jwt_set else "error",
        source="configured",
        checked_at=datetime.now(timezone.utc).isoformat(),
        details="JWT configured" if jwt_set else "JWT_SECRET_KEY not set",
    ))

    # Non-instrumented services
    for name in ["Analyst", "Builder", "Coach", "Assistant", "Mission Control",
                 "Celery/Worker", "Scheduler"]:
        components.append(ComponentStatus(
            name=name, status="not_instrumented", source="not_instrumented",
            checked_at=datetime.now(timezone.utc).isoformat(),
            details="Service status not independently monitored",
        ))

    return {
        "status": "ok",
        "components": [c.model_dump() for c in components],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }