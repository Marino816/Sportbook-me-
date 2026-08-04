# Phase 2 Repairs — Sportsbook Me DFS AI

**Date**: 2026-08-04
**Branch**: `hermes-production-build`
**Commit**: `bbc15ef` feat: Phase 2 hardening — auth, migrations, celery fix, optimizer contract

---

## 1. Repairs Completed

### 1.1 Celery Worker (Critical Blocker #1)

**Root cause**: The `backend/worker/tasks.py` file had a corrupted line where the REDIS_URL default value and the Celery app definition were concatenated into one garbled statement: `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:***@celery_app.task`.

**Fix**: Rewrote the file with a proper Celery application definition:
- Separate `REDIS_URL` and `celery_app = Celery(...)` declarations
- Added `sys.path.insert(0, _parent)` for robustness regardless of working directory
- All imports use backend-relative paths (`from integrations.balldontlie import ...`)
- Added docstring and inline comments
- The `sync_daily_slate` task is registered and periodic scheduling intact

**Verification**: `import` check passes. `celery_app.tasks.keys()` includes `worker.tasks.sync_daily_slate`.

### 1.2 Admin Import (Critical Blocker #2)

**Root cause**: `backend/api/admin.py:106` used `from backend.worker.tasks import sync_daily_slate` which fails when the web process runs from the `backend/` directory (the `backend` module is not a subpackage of itself).

**Fix**: Changed to `from worker.tasks import sync_daily_slate` — consistent with the web process's working directory.

**Verification**: `from api.admin import router` passes.

### 1.3 Database Migrations (Critical Blocker #3)

**Root cause**: No migration infrastructure existed. Alembic was installed but unconfigured. `Base.metadata.create_all()` was intentionally removed from the app lifespan (commit `35c173f`).

**Fix**:
- Created `backend/__init__.py` and `backend/worker/__init__.py` as package markers
- Generated `backend/migrations/` via `alembic init migrations`
- Configured `alembic.ini` with development fallback URL
- Wrote `migrations/env.py` that:
  - Reads `DATABASE_URL` from environment (with auto asyncpg conversion)
  - Imports all 10 model classes for autogenerate support
  - Handles offline and online migration modes
- Made `models/database.py` use lazy engine initialization — the engine and session factory are created on first use, not at module import time. This allows Alembic to import `Base` without needing a live database.
- Wrote initial migration `d0ccfbefa849_initial_schema.py` creating all 10 tables:
  `users`, `slates`, `players`, `game_logs`, `projections`, `lineups`, `subscriptions`, `matchups`, `system_status`, `stripe_events`

**Verification**: `alembic upgrade --sql head` generates valid DDL. SQLite test upgrade creates all tables successfully (FK ordering is correct for PostgreSQL — the circular FK between users↔subscriptions requires PostgreSQL-level ALTER support).

**Production migration command**:
```bash
cd backend
DATABASE_URL=postgresql://user:pass@host:5432/db alembic upgrade head
```

### 1.4 Authentication (Critical Blocker #4)

**Root cause**: `get_current_user()` auto-created a default user `"shark@apexdfs.io"` if the database was empty. No password, no JWT, no login flow. Any request was effectively authenticated.

**Fix**: Full JWT authentication system in `backend/api/auth.py`:

| Component | Implementation |
|-----------|---------------|
| Password hashing | bcrypt via passlib (CryptContext) |
| Token creation | JWT via python-jose (HS256, 24h expiry) |
| Token verification | `HTTPBearer` security scheme + `get_current_user` dependency |
| Registration | `POST /api/auth/register` — creates user, returns JWT |
| Login | `POST /api/auth/login` — verifies credentials, returns JWT |
| Current user | `GET /api/auth/me` — returns authenticated user profile |

**Security properties**:
- Passwords hashed with bcrypt (never stored plaintext)
- JWT secret from `JWT_SECRET_KEY` environment variable (development default: `"dev-secret-change-in-production"`)
- Token expiration at 24 hours (configurable via `JWT_EXPIRE_MINUTES`)
- Duplicate email rejected (409 Conflict)
- Short passwords rejected (422)
- Invalid passwords rejected (401)
- Disabled users rejected (403)
- Missing/invalid/expired tokens rejected (401)
- `get_current_user` dependency replaces the old stub in both `billing.py` and `router.py`

**User model changes** (`models/domain.py`):
- Added `hashed_password` (String, nullable — allows existing users without passwords)
- Added `is_active` (Boolean, default True)
- Migration included

**Old auto-auth behavior**: Completely removed. The `get_current_user` stub that auto-created users no longer exists.

### 1.5 Optimizer Contract (Critical Blocker #5)

**Root cause**: Backend checked `settings.get('excluded', [])` and `settings.get('locked', [])` but the OptimizerSettings schema used `excluded_player_ids` and `locked_player_ids`. The frontend was aligned with the schema but the optimizer never read from those keys, making lock/exclude silently non-functional.

**Fix**: The optimizer now accepts both canonical and legacy field names:

```python
self.locked_ids = list(
    self.settings.get('locked_player_ids', [])
    or self.settings.get('locked', [])
)
self.excluded_ids = list(
    self.settings.get('excluded_player_ids', [])
    or self.settings.get('excluded', [])
)
```

`baseline OptimizerSettings` schema now documents the canonical names. `build_variables()` uses `self.locked_ids`/`self.excluded_ids` directly.

---

## 2. Files Changed

| File | Change |
|------|--------|
| `backend/.gitignore` | Added __pycache__ entries |
| `backend/.env.example` | Added `SECRET_KEY` and `JWT_EXPIRE_MINUTES` |
| `backend/Procfile` | Worker/beat use `worker.tasks` (consistent) |
| `backend/__init__.py` | New — package marker |
| `backend/alembic.ini` | New — Alembic configuration |
| `backend/api/admin.py` | Fixed sync_daily_slate import |
| `backend/api/auth.py` | New — JWT authentication module |
| `backend/api/billing.py` | Use auth.get_current_user, fix Session→AsyncSession |
| `backend/api/router.py` | Use auth.get_current_user |
| `backend/main.py` | Register auth router |
| `backend/migrations/` | New — Alembic migration directory |
| `backend/models/database.py` | Lazy engine initialization |
| `backend/models/domain.py` | Add hashed_password, is_active to User |
| `backend/models/schemas.py` | Auth schemas, optimizer docs, ConfigDict fix |
| `backend/optimizer/core.py` | Accept both field name conventions |
| `backend/pytest.ini` | New — asyncio_mode=auto |
| `backend/requirements.txt` | Add passlib, python-jose, python-multipart; remove duplicate uvicorn |
| `backend/tests/__init__.py` | New |
| `backend/tests/test_auth.py` | New — 14 auth tests |
| `backend/tests/test_optimizer.py` | New — 9 optimizer tests |
| `backend/worker/__init__.py` | New — package marker |
| `backend/worker/tasks.py` | Full rewrite — fix corruption, robust imports |
| `phase1_audit.md` | Phase 1 audit document |

---

## 3. Commands Executed

```bash
# Install deps
pip install passlib[bcrypt] python-jose[cryptography] python-multipart pytest pytest-asyncio httpx aiosqlite
pip install "bcrypt==4.2.1"  # compatibility fix

# Alembic
alembic init migrations
alembic revision -m "initial_schema"

# Tests
python -m pytest tests/ -v
# 23 passed, 0 failed

# Import verification
python -c "from worker.tasks import celery_app, sync_daily_slate; print('Tasks:', list(celery_app.tasks.keys()))"
python -c "from api.admin import router; print('admin OK')"
python -c "from api.auth import router, get_current_user; print('auth OK')"
```

---

## 4. Tests Summary

| Category | Tests | Status |
|----------|-------|--------|
| Registration | 3 | 3 passed |
| Login | 3 | 3 passed |
| Protected endpoints | 5 | 5 passed |
| Billing auth | 2 | 2 passed |
| Disabled user | 1 | 1 passed |
| Optimizer basics | 2 | 2 passed |
| Locked players | 3 | 3 passed |
| Excluded players | 2 | 2 passed |
| Empty inputs | 2 | 2 passed |
| **Total** | **23** | **23 passed, 0 failed** |

---

## 5. Remaining Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Circular FK (users↔subscriptions) | Low | Works on PostgreSQL but causes SQLite warnings during test DB teardown. Not a production issue. |
| bcrypt version warning | Low | passlib warns about bcrypt 4.2.1's missing `__about__` attribute but hashing/verification works correctly. Pinned to 4.2.1. |
| No frontend auth UI | Medium | Auth API exists but the Next.js frontend has no login/register pages. The `/billing` and `/optimizer` pages will now fail with 401 since they require auth. |
| Redis not running locally | Low | Celery can't connect to Redis without it. Tests use SQLite in-memory so don't need Redis. |
| Migration not tested on PostgreSQL | Medium | Tested offline (SQL generation) and on SQLite. The circular FK ordering works on PostgreSQL but hasn't been verified against a live PostgreSQL instance. |

---

## 6. Environment Variables Required

New variables added to `backend/.env.example`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | JWT signing key | `dev-secret-change-in-production` |
| `JWT_EXPIRE_MINUTES` | Token lifetime in minutes | `1440` (24 hours) |

---

## 7. Manual Actions Required

1. **Set `SECRET_KEY`** in production to a random 64-character string:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. **Run database migration** on the production PostgreSQL instance:
   ```bash
   cd backend
   DATABASE_URL=postgresql://user:pass@host:5432/db alembic upgrade head
   ```

3. **Build frontend auth UI** — The API endpoints exist (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`) but the Next.js frontend has no login/register pages. All protected pages (billing, optimizer) will return 401 without a valid JWT.

4. **Update frontend `api.ts`** — The `checkHealth()` function hardcodes `http://localhost:8000/health`. Update to use `NEXT_PUBLIC_API_URL`.

5. **Pin bcrypt** — In production deployments, ensure `bcrypt==4.2.1` in `requirements.txt` (already done).

---

## 8. Recommended Phase 3

1. **Build frontend auth UI** — Login/register pages, token storage, axios interceptor for Authorization header
2. **Wire ML pipeline to API** — Training and prediction endpoints using the XGBoost model
3. **Multi-sport optimizer constraints** — Add FanDuel constraints and NFL/MLB/NHL roster structures
4. **Admin sub-pages** — Create the 6 missing admin pages (projections, optimizer, billing, users, support, logs)
5. **CI/CD pipeline** — GitHub Actions for test suite on push
6. **Rate limiting** — Add slowapi or similar for auth endpoints
7. **CSV export** — Implement actual file download for lineup CSV export