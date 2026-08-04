# Changelog

All notable changes to Sportsbook Me DFS AI.

## v1.0-beta — August 4, 2026

### Added
- User registration endpoint (`POST /api/auth/register`)
- User login endpoint (`POST /api/auth/login`)
- Current user endpoint (`GET /api/auth/me`)
- JWT authentication with HS256, 24-hour token expiry
- Role-based access control (`user` / `admin` roles)
- Backend `require_admin` dependency enforcing admin-only endpoints
- Frontend admin route guard (non-admin → dashboard redirect)
- Protected route middleware for optimizer, billing, and admin
- AuthProvider React context with `useAuth()` hook
- localStorage token persistence with auto-injection
- Auth-aware navigation (sign in / join vs user card + logout)

### Infrastructure
- Railway backend deployment (FastAPI + Gunicorn + Uvicorn)
- Railway PostgreSQL staging database
- Railway Redis staging service
- Railway Celery worker service
- Vercel frontend Preview deployment (Next.js 15)
- Alembic migration infrastructure (3 revisions)
- Docker Compose for local development

### Changed
- Celery worker task definition repaired (corrupted REDIS_URL)
- Admin sync import path fixed (`worker.tasks.sync_daily_slate`)
- Billing database session split (async for FastAPI, sync for Stripe webhooks)
- Optimizer contract normalized (`locked_player_ids` / `excluded_player_ids`)
- CORS supports multiple comma-separated origins
- SECRET_KEY guard prevents startup with dev default in production

### Fixed
- Alembic env.py converted to async engine for PostgreSQL/asyncpg compatibility
- bcrypt pinned to 4.2.1 for passlib compatibility
- Password validation enforces minimum 8 characters
- DateTime columns converted to `TIMESTAMP WITH TIME ZONE` (5 columns)
- JWT `sub` claim converted from int to string (JWT spec compliance)
- OAuth2PasswordBearer replaced with HTTPBearer for stable token extraction
- admin events endpoint join ambiguity resolved
- AmbiguousForeignKeysError in admin events query

---

Notable: the initial pre-audit repository had a corrupted `tasks.py` that prevented
Celery from importing, and `admin.py` referenced a non-existent import path.
Both were repaired in the initial hardening phase before auth was added.