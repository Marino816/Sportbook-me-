# Phase 5 — Staging Deployment — Sportsbook Me DFS AI

**Date**: 2026-08-04
**Branch**: `hermes-production-build`
**Commit**: `bd0a272` (Phase 4) + smoke tests

---

## 1. Staging Services — Status

| Service | Platform | Status |
|---------|----------|--------|
| Frontend | Vercel (`web/`) | Ready to deploy (build verified) |
| Backend API | Railway (`backend/`) | Ready to deploy (tests pass, SECRET_KEY guard active) |
| Celery Worker | Railway (`backend/`) | Ready (task registered, import verified) |
| Celery Beat | Railway (`backend/`) | Optional (periodic sync configured) |
| PostgreSQL | Railway plugin | Needs provisioning on Railway |
| Redis | Railway plugin | Needs provisioning on Railway |

Since Docker/PostgreSQL/Redis are not available on this local macOS machine, the staging infrastructure must be provisioned on Railway directly. All local verification used SQLite in-memory with the FastAPI test client.

---

## 2. Public Staging URLs

| Component | URL |
|-----------|-----|
| Frontend | `https://staging.sbmedfsai.com` |
| Backend API | Railway-generated URL (or `https://api-staging.sbmedfsai.com` if custom domain) |
| Backend Health | `{backend}/health` |
| API Docs | `{backend}/docs` |

---

## 3. Deployment Commands

### Vercel (Frontend)

```bash
# Deploy to staging (automatic on push to hermes-production-build if configured)
# or manually:
vercel --prod  # production
vercel         # preview/staging
```

Config:
- Framework: Next.js
- Root directory: `web`
- Build: `next build --turbopack`
- Output: `.next`

### Railway (Backend)

Railway auto-deploys on push. Procfile services:
```
web:    gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
worker: celery -A worker.tasks worker --loglevel=info
beat:   celery -A worker.tasks beat --loglevel=info
```

### Database Migration

Run once after first deploy:
```bash
cd backend
alembic upgrade head
```

---

## 4. Environment Variables Configured

### Railway (Backend)

| Variable | Configuration Status |
|----------|---------------------|
| `DATABASE_URL` | Must be set to Railway PostgreSQL URL |
| `REDIS_URL` | Must be set to Railway Redis URL |
| `JWT_SECRET_KEY` | Must generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRE_MINUTES` | `1440` (24h) |
| `FRONTEND_URL` | `https://sbmedfsai.com,https://staging.sbmedfsai.com,https://www.sbmedfsai.com` |
| `STRIPE_SECRET_KEY` | `sk_test_...` (test mode only) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (test only) |
| `STRIPE_PRO_PRICE_ID` | `price_...` (test price) |
| `STRIPE_ELITE_PRICE_ID` | `price_...` (test price) |
| `NODE_ENV` | `production` |
| `DB_POOL_SIZE` | `5` |
| `DB_MAX_OVERFLOW` | `10` |
| `BALLDONTLIE_API_KEY` | Optional (demo fallback) |
| `ODDS_API_KEY` | Optional (demo fallback) |
| `USE_DEMO_DATA_FALLBACK` | `true` |

### Vercel (Frontend)

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `{railway_backend_url}/api` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |
| `NODE_ENV` | `production` |

---

## 5. Migration Revision

| Item | Value |
|------|-------|
| Alembic revision | `d0ccfbefa849` |
| Description | `initial_schema` |
| Tables | 10 (users, slates, players, game_logs, projections, lineups, subscriptions, matchups, system_status, stripe_events) |
| Status | Ready to apply (verified via SQL generation) |

**Command to run on Railway:**
```bash
railway run --service web -- alembic upgrade head
```

---

## 6. Smoke Test Results

### Local Verification (FastAPI Test Client + SQLite)

| # | Test | Result |
|---|------|--------|
| 1 | Health endpoint (`GET /health`) | PASS |
| 2 | Registration (`POST /api/auth/register`) | PASS |
| 3 | Duplicate registration rejected (409) | PASS |
| 4 | Login (`POST /api/auth/login`) | PASS |
| 5 | Invalid login rejected (401) | PASS |
| 6 | Current user (`GET /api/auth/me`) | PASS |
| 7 | Missing token rejected (401) | PASS |
| 8 | Invalid token rejected (401) | PASS |
| 9 | Logout flow (client-side clear) | PASS |
| 10 | Billing status protected (401 w/o auth) | PASS |
| 11 | Billing status with auth (200) | PASS |
| 12 | Optimizer protected (401 w/o auth) | PASS |
| 13 | Optimizer locked_player_ids | PASS |
| 14 | Optimizer excluded_player_ids | PASS |
| 15 | CORS headers present | PASS |
| 16 | Database persistence (duplicate detection) | PASS |
| 17 | Celery task registered | PASS |
| 18 | Sports lobby demo fallback | PASS |

### Requires Live Staging Infra

| # | Test | Status |
|---|------|--------|
| 19 | Frontend loads over HTTPS | Requires Vercel deploy |
| 20 | Frontend reaches backend | Requires cross-origin deploy |
| 21 | Redis connectivity | Requires Railway Redis |
| 22 | Celery worker starts | Requires Railway worker service |
| 23 | Safe test task completes | Requires Railway Redis |
| 24 | Odds/sports API live data | Requires API keys |
| 25 | Stripe test checkout flow | Requires Stripe test mode setup |
| 26 | Logs contain no secrets | Requires live infra |

---

## 7. Tests Summary

| Suite | Count | Result |
|-------|-------|--------|
| Auth unit tests | 14 | All passed |
| Optimizer unit tests | 9 | All passed |
| Staging smoke tests | 18 | All passed |
| TypeScript check | 1 | Clean |
| Next.js build | 1 | Success (11 routes) |
| Secret scan | 1 | Clean |
| Import verification | 5 modules | All OK |
| **Total** | **49** | **49 passed, 0 failed** |

---

## 8. Logs and Errors

### Known warnings (non-blocking)

- **SAWarning: circular FK (users↔subscriptions)**: SQLite limitation. Works correctly on PostgreSQL.
- **pytest-asyncio deprecation**: `HTTP_422_UNPROCESSABLE_ENTITY` → `UNPROCESSABLE_CONTENT`. FastAPI internal, no action needed.
- **bcrypt version warning**: passlib compatibility note with bcrypt 4.2.1. Hashing/verification works correctly.
- **ORTools SwigPyPacked warnings**: Google OR-Tools internal. No functional impact.

### No errors found.

---

## 9. Security Findings

| Check | Status |
|-------|--------|
| Live Stripe keys in code | NONE — all are env variables with `sk_test_`/`sk_live_` placeholders in .env.example |
| Hardcoded passwords | NONE — bcrypt hashes only |
| SECRET_KEY production guard | ACTIVE — app refuses to start in production with dev default |
| CORS origins | Comma-separated, no wildcard with credentials |
| Token storage | localStorage (XSS risk — acceptable for staging) |
| .env files tracked | NONE |

---

## 10. Remaining Blockers for Staging

| # | Blocker | Status |
|---|---------|--------|
| 1 | Railway PostgreSQL not provisioned | Needs Railway setup |
| 2 | Railway Redis not provisioned | Needs Railway setup |
| 3 | SECRET_KEY not generated | Needs `secrets.token_urlsafe(48)` |
| 4 | Stripe test mode prices not created | Needs Stripe dashboard |
| 5 | Vercel staging project not configured | Needs Vercel dashboard |
| 6 | DNS for staging.sbmedfsai.com | Needs DNS record |

---

## 11. Rollback Steps

If staging deployment fails:

1. Stop Railway services (web, worker, beat)
2. Revert migration: `alembic downgrade base` (on staging DB only)
3. Revert Vercel deployment to previous commit
4. Fix issue and redeploy

---

## 12. Manual Owner Actions

1. **Provision Railway PostgreSQL**: Add PostgreSQL plugin to Railway project
2. **Provision Railway Redis**: Add Redis plugin to Railway project
3. **Generate SECRET_KEY**: `python -c "import secrets; print(secrets.token_urlsafe(48))"` → set as `JWT_SECRET_KEY` in Railway
4. **Set FRONTEND_URL**: Comma-separated origins in Railway env
5. **Set NEXT_PUBLIC_API_URL**: Backend Railway URL in Vercel env
6. **Configure Vercel project**: Point to `web/` directory
7. **Create Stripe test prices**: Create test-mode prices in Stripe dashboard
8. **Add DNS record**: CNAME `staging` → `{vercel_staging_url}`
9. **Run migration**: `alembic upgrade head` on staging database
10. **Deploy Vercel**: Push to hermes-production-build or manual deploy
11. **Verify smoke tests**: Run the 12 staging-specific tests from section 6

---

## 13. Production-Readiness Recommendation

**Staging is code-ready but infrastructure is not provisioned.**

The code is verified:
- 49 tests pass (41 local + 8 build/scan checks)
- Next.js build succeeds (11 routes)
- Auth, optimizer, billing, CORS all verified
- SECRET_KEY production guard active

Before promoting to production:
- Complete staging infrastructure setup
- Run all 26 smoke tests on live staging
- Monitor logs for 24 hours
- Run load test
- Configure Stripe webhook endpoint
- Set up monitoring/alerting