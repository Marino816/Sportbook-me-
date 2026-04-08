import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Expecting this format: postgresql+asyncpg://postgres:password@localhost/apex_dfs
# Railway provides postgresql:// — we auto-convert for asyncpg compatibility
_raw_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/apex_dfs")
DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1) if _raw_url.startswith("postgresql://") else _raw_url

# In production, we often need SSL or a connection pooler like PgBouncer
# Railway and Supabase require SSL for external connections
is_production = os.getenv("NODE_ENV") == "production"
connect_args = {}
if is_production:
    connect_args = {"ssl": "require"}

# Create async engine
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10))
)

# Session factory
SessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
