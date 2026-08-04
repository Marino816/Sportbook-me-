# Phase 4 — Staging Deployment Plan — Sportsbook Me DFS AI

**Date**: 2026-08-04
**Branch**: `hermes-production-build`
**Domain**: https://sbmedfsai.com

---

## 1. Infrastructure Summary

| Component | Platform | Directory |
|-----------|----------|-----------|
| Frontend (Next.js 15) | Vercel | `web/` |
| Backend API (FastAPI) | Railway | `backend/` |
| Worker (Celery) | Railway | `backend/` |
| Beat (Celery) | Railway | `backend/` |
| PostgreSQL 15 | Railway / Docker | — |
| Redis 7 | Railway / Docker | — |

---

## 2. Vercel Setup (Frontend)

### Project Configuration

| Setting | Value |
|---------|-------|
| Framework | Next.js |
| Root directory | `web` |
| Build command | `next build --turbopack` |
| Output directory | `.next` |
| Install command | `npm install` |
| Node version | 20.x |

### Environment Variables (Vercel)

| Key | Staging Value | Production Value |
|-----|---------------|------------------|
| `NEXT_PUBLIC_API_URL` | `https://api-staging.sbmedfsai.com/api` | `https://api.sbmedfsai.com/api` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` | `pk_live_...` |
| `NODE_ENV` | `production` | `production` |

### Custom Domains

| Domain | Environment |
|--------|-------------|
| `sbmedfsai.com` | Production |
| `www.sbmedfsai.com` | Production (redirect) |
| `staging.sbmedfsai.com` | Staging (create when ready) |

### Security Headers (vercel.json)

Already configured:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`

---

## 3. Railway Setup (Backend)

### Project Configuration

| Setting | Value |
|---------|-------|
| Root directory | `backend` |
| Runtime | Python 3.13 |
| Start command | See Procfile |

### Procfile (3 Services)

```
web:    gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
worker: celery -A worker.tasks worker --loglevel=info
beat:   celery -A worker.tasks beat --loglevel=info
```

### Environment Variables (Railway)

| Key | Required | Staging Example | Notes |
|-----|----------|-----------------|-------|
| `DATABASE_URL` | YES | `postgresql://user:pass@host:5432/staging_db` | Auto-converted to asyncpg |
| `REDIS_URL` | YES | `redis://user:pass@host:6379/0` | Celery broker + result backend |
| `JWT_SECRET_KEY` | YES | `$(python -c "import secrets; print(secrets.token_urlsafe(48))")` | Fails startup if dev default in production |
| `JWT_EXPIRE_MINUTES` | NO | `1440` | Default: 24 hours |
| `FRONTEND_URL` | YES | `https://sbmedfsai.com,https://staging.sbmedfsai.com,https://www.sbmedfsai.com` | Comma-separated CORS origins |
| `STRIPE_SECRET_KEY` | NO | `sk_test_...` | Test mode for staging |
| `STRIPE_WEBHOOK_SECRET` | NO | `whsec_...` | Test webhook secret |
| `STRIPE_PRO_PRICE_ID` | NO | `price_...` | Stripe test price ID |
| `STRIPE_ELITE_PRICE_ID` | NO | `price_...` | Stripe test price ID |
| `BALLDONTLIE_API_KEY` | NO | `...` | NBA data (demo fallback if missing) |
| `ODDS_API_KEY` | NO | `...` | The Odds API (demo fallback if missing) |
| `USE_DEMO_DATA_FALLBACK` | NO | `true` | Graceful fallback when API keys missing |
| `NODE_ENV` | YES | `production` | Enables SECRET_KEY guard + SSL |
| `DB_POOL_SIZE` | NO | `5` | Connection pool |
| `DB_MAX_OVERFLOW` | NO | `10` | Overflow connections |

---

## 4. PostgreSQL Setup

### Railway Managed Database

- Railway provides PostgreSQL via the database plugin
- Connection string auto-injected as `DATABASE_URL`
- The backend auto-converts `postgresql://` → `postgresql+asyncpg://`

### Docker (Local Staging Alternative)

```bash
docker compose up -d db redis
```

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: apex_dfs
    ports:
      - "5432:5432"
  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

---

## 5. Redis Setup

- Required by Celery for task queuing and result storage
- Railway provides Redis via plugin, or use Docker locally
- Connection string: `REDIS_URL=redis://...`
- Celery config in `backend/worker/tasks.py`:
  ```python
  REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:***$(python -c "import secrets; print(secrets.token_urlsafe(48))")"' 2>/dev/null)"
  ```
  2. Set the key in Railway environment: `JWT_SECRET_KEY=<generated_value>`
  3. Restart the web service

### 10.2 Run Database Migration

  1. SSH into Railway web service or use `railway run`
  2. Run:
     ```bash
     cd backend
     alembic upgrade head
     ```
  3. Verify: `alembic current` should show `d0ccfbefa849`

### 10.3 Configure CORS Origins

  Set `FRONTEND_URL` in Railway to a comma-separated list:
  ```
  https://sbmedfsai.com,https://www.sbmedfsai.com,https://staging.sbmedfsai.com
  ```

### 10.4 Configure Frontend API URL

  Set `NEXT_PUBLIC_API_URL` in Vercel to the Railway backend URL:
  ```
  https://api.sbmedfsai.com/api
  ```

### 10.5 Add DNS Records (When Ready)

  | Type | Name | Value |
  |------|------|-------|
  | CNAME | `staging` | `staging-frontend.vercel.app` |
  | CNAME | `api-staging` | `staging-backend.railway.app` |

---

## 11. Rollback Plan

If staging deployment fails:

1. **Revert database migration**: `alembic downgrade base`
2. **Revert to main branch**: `git checkout main`
3. **Redeploy** Vercel and Railway from main
4. **Verify** smoke tests pass on production

If production deployment fails (future):
1. **Do NOT downgrade** the database migration unless data loss is acceptable
2. **Roll back** Vercel deployment to previous commit
3. **Roll back** Railway deployment to previous commit
4. **Restore** database from backup if migration was destructive

---

## 12. Remaining Blockers for Staging

| # | Blocker | Status |
|---|---------|--------|
| 1 | Staging domain not created | Needs DNS: staging.sbmedfsai.com |
| 2 | Railway PostgreSQL not provisioned | Needs Railway account setup |
| 3 | Railway Redis not provisioned | Needs Railway plugin |
| 4 | SECRET_KEY not generated | Needs `secrets.token_urlsafe(48)` |
| 5 | Stripe test mode prices not created | Needs Stripe dashboard setup |
| 6 | Vercel staging environment not configured | Needs Vercel project settings |

---

## 13. Verification Results (Local)

| Check | Result |
|-------|--------|
| Backend tests | 23 passed, 0 failed |
| TypeScript type check | Clean |
| Next.js production build | Success (11 routes) |
| Alembic migration SQL | 10 tables + alembic_version |
| SECRET_KEY production guard | Fails on dev default in production |
| CORS multi-origin support | Comma-separated origins supported |
| Secret scan | Clean |
| Import verification | All modules import correctly |
| No localhost defaults in production | API_URL, FRONTEND_URL, DATABASE_URL, REDIS_URL all env-driven |
| Stripe test mode | Default price IDs are test (`price_*_test`) |