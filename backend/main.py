from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
from contextlib import asynccontextmanager

# from api import slates_router, projections_router, optimizer_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ML models if necessary, connect to redis, etc.
    print("Starting up Apex DFS API...")
    
    # Initialize DB tables in production (safe for already existing tables)
    from models.database import engine
    from models.domain import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    # Shutdown: Clean up connections
    print("Shutting down SPORTSBOOK ME DFS AI API...")

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
