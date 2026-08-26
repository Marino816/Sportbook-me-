from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

BCDFS_TICK_INTERVAL = int(os.getenv("BCDFS_TICK_INTERVAL", "600"))  # seconds (default 10 min)
_bcdfs_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Starting up Sportsbook ME DFS AI API...")

    # Production safety: reject dev JWT secret in production
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    is_production = os.getenv("NODE_ENV") == "production"
    if is_production and jwt_secret in ("", "dev-secret-change-in-production"):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    # QA staging account bootstrap (idempotent, skipped unless configured)
    try:
        from models.database import SessionLocal
        from scripts.bootstrap_qa import bootstrap_qa_account
        async with SessionLocal() as db:
            await bootstrap_qa_account(db)
    except Exception:
        logging.exception("QA bootstrap failed (non-fatal)")

    # ── BCDFS automated scheduler (activation via env var) ──
    if os.getenv("BCDFS_SCHEDULER_ENABLED", "").lower() in ("true", "1", "yes"):
        logging.info(
            "BCDFS scheduler ENABLED — tick interval %ds", BCDFS_TICK_INTERVAL
        )
        global _bcdfs_task
        _bcdfs_task = asyncio.create_task(_bcdfs_scheduler_loop())
    else:
        logging.info("BCDFS scheduler disabled (set BCDFS_SCHEDULER_ENABLED=true to activate)")

    yield
    # Shutdown
    logging.info("Shutting down Sportsbook ME DFS AI API...")
    if _bcdfs_task is not None:
        _bcdfs_task.cancel()
        try:
            await _bcdfs_task
        except asyncio.CancelledError:
            pass


async def _bcdfs_scheduler_loop() -> None:
    """Run scheduler_tick() every BCDFS_TICK_INTERVAL seconds.

    Each tick checks which endpoints are actually due — a wake-up
    does NOT equal a provider request.  All budget / priority /
    backoff rules are enforced inside scheduler_tick().

    Never crashes the FastAPI process — a single failing tick is
    logged and the loop continues.
    """
    while True:
        try:
            from models.database import _SessionLocal
            from dfs.bcdfs_scheduler import scheduler_tick

            async with _SessionLocal() as db:
                result = await scheduler_tick(db)

            synced = result.get("synced", 0)
            if synced > 0:
                logger.info(
                    "BCDFS tick: %d endpoints synced, auto budget %d/%d",
                    synced,
                    result.get("auto_budget_remaining", "?"),
                    result.get("auto_budget_limit", "?"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("BCDFS scheduler tick failed — continuing loop")
        await asyncio.sleep(BCDFS_TICK_INTERVAL)

app = FastAPI(
    title="Sportsbook Me DFS AI API",
    description="Backend for DFS Optimizer and ML Predictions",
    version="1.0.0",
    lifespan=lifespan
)

from api import router as api_router
from api import admin, stats, sports, billing, auth, ai_routes, scout_routes, analyst_routes, builder_routes, coach_routes, mc_routes, assistant_routes, admin_health, operations, intelligence_routes, dfs_admin, dfs_customer, market_tools, sgo_data, data_hub, player_stats
from assistant import chat_router
from services.logging import RequestLogMiddleware, configure_structured_logging

# Allow CORS for Next.js / Expo frontend
# Supports: production, staging, and local dev
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in FRONTEND_URL.split(",")
    if origin.strip()
] if FRONTEND_URL else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

configure_structured_logging()

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(api_router.router, prefix="/api", tags=["DFS"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(stats.router, prefix="/api/stats", tags=["Performance"])
app.include_router(sports.router, prefix="/api/sports", tags=["Sports"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(ai_routes.router, tags=["AI Engine"])
app.include_router(scout_routes.router, tags=["SB-Me Scout"])
app.include_router(analyst_routes.router, tags=["SB-Me Analyst"])
app.include_router(builder_routes.router, prefix="/api", tags=["SB-Me Builder"])
app.include_router(coach_routes.router, tags=["SB-Me Coach"])
app.include_router(mc_routes.router, tags=["SB-Me Mission Control"])
app.include_router(assistant_routes.router, prefix="/api", tags=["SB-Me AI Assistant"])
app.include_router(admin_health.router, tags=["Admin Health"])
app.include_router(operations.router, tags=["Operations Metrics"])
app.include_router(intelligence_routes.router, prefix="/api", tags=["SB-Me Intelligence"])
app.include_router(dfs_admin.router, prefix="/api", tags=["Admin DFS"])
app.include_router(dfs_customer.router, prefix="/api", tags=["DFS Slates"])
app.include_router(market_tools.router, prefix="/api", tags=["SB-Me Market Tools"])
app.include_router(sgo_data.router, prefix="/api", tags=["SGO Data"])
app.include_router(data_hub.router, prefix="/api", tags=["SB-Me Data Hub"])
app.include_router(player_stats.router, prefix="/api", tags=["Player Stats"])
app.include_router(chat_router.router)  # canonical POST /api/ai/chat

if __name__ == "__main__":
    import os
    os.environ.setdefault("NODE_ENV", "production")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
