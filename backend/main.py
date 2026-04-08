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
    # NOTE: Database table creation is intentionally omitted here.
    # Running Base.metadata.create_all() during lifespan causes the app to hang
    # when the database connection is slow or unavailable at boot time, resulting
    # in 502 errors across all workers. Use Alembic migrations or a separate
    # management command to manage schema changes.
    logging.info("Starting up Sportsbook ME DFS AI API...")
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
from api import admin, stats, sports, billing

# Allow CORS for Next.js / Expo frontend
FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("NEXT_PUBLIC_WEB_URL", "*"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"], 
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
