from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
from contextlib import asynccontextmanager

# from api import slates_router, projections_router, optimizer_router

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

    # NOTE: Database table creation is intentionally omitted here.
    # Running Base.metadata.create_all() during lifespan causes the app to hang
    # when the database connection is slow or unavailable at boot time, resulting
    # in 502 errors across all workers. Use Alembic migrations or a separate
    # management command to manage schema changes.
    yield
    # Shutdown
    logging.info("Shutting down Sportsbook ME DFS AI API...")

app = FastAPI(
    title="Sportsbook Me DFS AI API",
    description="Backend for DFS Optimizer and ML Predictions",
    version="1.0.0",
    lifespan=lifespan
)

from api import router as api_router
from api import admin, stats, sports, billing, auth, ai_routes, scout_routes, analyst_routes, builder_routes, coach_routes, mc_routes

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
app.include_router(builder_routes.router, tags=["SB-Me Builder"])
app.include_router(coach_routes.router, tags=["SB-Me Coach"])
app.include_router(mc_routes.router, tags=["SB-Me Mission Control"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
