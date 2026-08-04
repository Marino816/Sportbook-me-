# Phase 5B — Staging Infrastructure Provisioning — Sportsbook Me DFS AI

**Date**: 2026-08-04
**Branch**: `hermes-production-build`
**Status**: INFRASTRUCTURE NOT YET PROVISIONED — requires manual setup

---

## EXECUTIVE SUMMARY

Local verification is complete (49 checks passed). Staging infrastructure on Railway and Vercel must be provisioned manually. This document provides every command, URL, and environment variable needed.

---

## 1. ENVIRONMENT VARIABLE NAMING — FIXED

**Issue found**: `backend/.env.example` used `SECRET_KEY` but the application code (`auth.py`, `main.py`) reads `JWT_SECRET_KEY`. This caused confusion across all Phase reports.

**Fixed**: `backend/.env.example` now uses `JWT_SECRET_KEY` (canonical name). All deployment documentation below uses `JWT_SECRET_KEY`.

**Verification**:
- `backend/api/auth.py:33`: `os.getenv("JWT_SECRET_KEY", ...)` ✓
- `backend/main.py:16`: `os.getenv("JWT_SECRET_KEY", "")` ✓
- `backend/.env.example:4`: `JWT_SECRET_KEY=change-me-to-a-random-64-char-string` ✓

---

## 2. STAGING JWT SECRET — GENERATED

A secure 64-character staging secret has been generated locally. **It is NOT displayed in this report.**

Set it manually in Railway:
```
JWT_SECRET_KEY=<64 char value generated via secrets.token_urlsafe(48)>
```

Generate a new one if needed:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 3. RAILWAY STAGING PROJECT SETUP

### 3.1 Create Project

1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Name: `sportsbook-me-staging`
4. Add services from the GitHub repo `Marino816/Sportbook-me-`

### 3.2 Web Service (FastAPI)

| Setting | Value |
|---------|-------|
| Source | GitHub: `Marino816/Sportbook-me-` branch `hermes-production-build` |
| Root directory | `backend` |
| Start command | `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT` |
| Health check path | `/health` |

### 3.3 Worker Service (Celery)

| Setting | Value |
|---------|-------|
| Source | Same as web service |
| Root directory | `backend` |
| Start command | `celery -A worker.tasks worker --loglevel=info` |

### 3.4 Beat Service (Celery Beat — Optional)

| Setting | Value |
|---------|-------|
| Source | Same as web service |
| Root directory | `backend` |
| Start command | `celery -A worker.tasks beat --loglevel=info` |

**Note**: Beat runs the hourly slate sync. Enable only if live sports data is configured.

### 3.5 PostgreSQL Plugin

1. In Railway dashboard, click "Add Plugin"
2. Select "PostgreSQL"
3. Railway auto-generates `DATABASE_URL` environment variable

### 3.6 Redis Plugin

1. In Railway dashboard, click "Add Plugin"
2. Select "Redis"
3. Railway auto-generates `REDIS_URL` environment variable

---

## 4. RAILWAY ENVIRONMENT VARIABLES

Set these in the Railway project's "Variables" tab (shared across services):

| Variable | Value | Notes |
|----------|-------|-------|
| `NODE_ENV` | `production` | Required — enables SECRET_KEY guard + SSL |
| `JWT_SECRET_KEY` | `<generated-64-char-secret>` | Required — copy from Section 2 |
| `JWT_EXPIRE_MINUTES` | `1440` | Token lifetime in minutes (24h) |
| `DATABASE_URL` | `<auto-set-by-railway>` | Railway PostgreSQL plugin |
| `REDIS_URL` | `<auto-set-by-railway>` | Railway Redis plugin |
| `FRONTEND_URL` | `https://sbmedfsai.com,https://staging.sbmedfsai.com,https://www.sbmedfsai.com,<vercel-staging-url>` | Comma-separated CORS origins |
| `STRIPE_SECRET_KEY` | `sk_test_...` | Stripe test mode secret |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | Stripe test webhook secret |
| `STRIPE_PRO_PRICE_ID` | `price_...` | Test price ID |
| `STRIPE_ELITE_PRICE_ID` | `price_...` | Test price ID |
| `DB_POOL_SIZE` | `5` | Connection pool |
| `DB_MAX_OVERFLOW` | `10` | Overflow connections |
| `BALLDONTLIE_API_KEY` | `<your-key>` | Optional — demo fallback if empty |
| `ODDS_API_KEY` | `<your-key>` | Optional — demo fallback if empty |
| `USE_DEMO_DATA_FALLBACK` | `true` | Graceful fallback when API keys missing |

Do NOT set these on Railway (production only):
- No live Stripe keys (`sk_live_`, `pk_live_`)
- No production database URLs
- No production Redis URLs

---

## 5. DATABASE MIGRATION

After Railway PostgreSQL is provisioned and environment variables set:

### 5.1 Verify Connection

```bash
# Via Railway CLI (after login):
railway run --service web -- python -c "import os; print(os.getenv('DATABASE_URL','NOT SET'))"
```

### 5.2 Run Migration

```bash
railway run --service web -- alembic upgrade head
```

### 5.3 Verify

```bash
railway run --service web -- alembic current
```

Expected output:
```
d0ccfbefa849 (head)
```

Expected tables (10): `users`, `slates`, `players`, `game_logs`, `projections`, `lineups`, `subscriptions`, `matchups`, `system_status`, `stripe_events`

---

## 6. RAILWAY DEPLOYMENT

Railway auto-deploys on push to the connected branch. After setting up services:

1. Push to `hermes-production-build` (already done)
2. Wait for Railway to build and deploy
3. Check service logs for errors

### 6.1 Health Check

```bash
curl https://<railway-service-url>/health
# Expected: {"status":"ok"}
```

### 6.2 Verify Services

- Web service: check `/health` and `/docs` endpoints
- Worker service: check logs for "ready" message
- Beat service (if enabled): check logs for "beat: Starting..."

---

## 7. VERCEL STAGING PROJECT

### 7.1 Create Project

```bash
# If Vercel CLI were authenticated:
vercel --cwd web --name sportsbook-me-staging

# Or via Vercel dashboard:
# 1. Go to https://vercel.com/new
# 2. Import Marino816/Sportbook-me-
# 3. Set root directory to "web"
# 4. Set framework to "Next.js"
```

### 7.2 Vercel Environment Variables

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://<railway-web-url>/api` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |
| `NODE_ENV` | `production` |

### 7.3 Deploy

```bash
# If Vercel CLI were authenticated:
vercel --cwd web --prod

# Or push to hermes-production-build (if auto-deploy configured)
```

### 7.4 Get Staging URL

Vercel generates a URL like: `sportsbook-me-staging-xxxxx.vercel.app`

Note this URL — it must be added to `FRONTEND_URL` in Railway for CORS.

---

## 8. CORS CONFIGURATION

After both services are deployed, update `FRONTEND_URL` in Railway:

```
FRONTEND_URL=https://sbmedfsai.com,https://staging.sbmedfsai.com,https://www.sbmedfsai.com,https://sportsbook-me-staging-xxxxx.vercel.app
```

The multi-origin CORS middleware (added in Phase 4) supports comma-separated origins.

---

## 9. DNS RECORD (DO NOT CREATE WITHOUT APPROVAL)

When ready to point a custom domain to staging:

| Field | Value |
|-------|-------|
| Record type | `CNAME` |
| Host / Name | `staging` |
| Target / Value | `cname.vercel-dns.com` (or Vercel-provided target) |
| TTL | `3600` (1 hour) |

Steps after DNS:
1. Add `staging.sbmedfsai.com` as a custom domain in Vercel project settings
2. Update `FRONTEND_URL` in Railway to include `https://staging.sbmedfsai.com`
3. Vercel auto-provisions SSL certificate

---

## 10. STRIPE TEST MODE

### 10.1 Required Test Products

Create these in Stripe Dashboard (Test Mode):

| Plan Name | Monthly Price | Price ID Variable |
|-----------|--------------|-------------------|
| Pro Arena | $29.00 | `STRIPE_PRO_PRICE_ID` |
| Elite Stack | $99.00 | `STRIPE_ELITE_PRICE_ID` |

### 10.2 Webhook Endpoint

Stripe requires a webhook endpoint for test mode:

1. Go to https://dashboard.stripe.com/test/webhooks
2. Add endpoint: `https://<railway-web-url>/api/billing/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the signing secret → set as `STRIPE_WEBHOOK_SECRET` in Railway

### 10.3 Test Card

Use Stripe test card for checkout: `4242 4242 4242 4242` (any future expiry, any CVC)

---

## 11. LIVE STAGING SMOKE TESTS

Run these AFTER all services are deployed and accessible:

```bash
STAGING_API="https://<railway-web-url>"
STAGING_WEB="https://<vercel-staging-url>"
```

| # | Test | Command/Check | Expected |
|---|------|--------------|----------|
| 1 | Frontend loads | curl -sI $STAGING_WEB | HTTP 200 |
| 2 | Backend health | curl $STAGING_API/health | `{"status":"ok"}` |
| 3 | Frontend reaches backend | Visit $STAGING_WEB → browser console | No CORS errors |
| 4 | Registration | POST $STAGING_API/api/auth/register | 200 + access_token |
| 5 | Duplicate rejected | POST again with same email | 409 |
| 6 | Login | POST $STAGING_API/api/auth/login | 200 + access_token |
| 7 | Invalid login | POST with wrong password | 401 |
| 8 | Current user | GET $STAGING_API/api/auth/me with token | 200 + email |
| 9 | Protected reject | GET $STAGING_API/api/billing/status (no token) | 401 |
| 10 | Logout | Client-side: clear localStorage, revisit | Redirects to login |
| 11 | DB persistence | Register → login → verify me endpoint | Same email returned |
| 12 | Redis | Check Railway worker logs | "ready" message |
| 13 | Celery task | Check Railway worker logs for task registration | `worker.tasks.sync_daily_slate` |
| 14 | Optimizer locked | POST /api/optimize with locked_player_ids | Player included in lineup |
| 15 | Optimizer excluded | POST /api/optimize with excluded_player_ids | Player excluded |
| 16 | Sports lobby | GET $STAGING_API/api/sports/lobby?sport=NFL | 200 + data |
| 17 | Stripe checkout | Visit /billing, click "Upgrade to Pro" | Redirects to Stripe test checkout |
| 18 | Stripe webhook | Test via Stripe dashboard "Send test webhook" | 200 response |
| 19 | Frontend uses staging | Check browser Network tab | API calls go to staging backend |
| 20 | No production secrets | Check Railway env variables | No `sk_live_`, no prod URLs |
| 21 | No secrets in logs | Check Railway logs | No passwords, tokens, or keys |

---

## 12. STATUS SUMMARY

| Item | Status |
|------|--------|
| **Local verification** | ✅ 49 checks passed |
| **Code consistency** | ✅ JWT_SECRET_KEY naming unified |
| **Staging secret** | ✅ Generated (not in repo) |
| **Railway project** | ❌ Not yet created |
| **Railway PostgreSQL** | ❌ Not provisioned |
| **Railway Redis** | ❌ Not provisioned |
| **Railway web service** | ❌ Not deployed |
| **Railway worker** | ❌ Not deployed |
| **Railway beat** | ❌ Not deployed |
| **Database migration** | ❌ Not run on staging |
| **Vercel staging project** | ❌ Not created |
| **Frontend deploy** | ❌ Not deployed |
| **CORS configured** | ❌ Needs Railway FRONTEND_URL |
| **DNS** | ⏸️ Needs owner approval |
| **Stripe test mode** | ❌ Needs test prices created |
| **Live smoke tests** | ❌ Requires live staging infra |

---

## 13. ROLLBACK INSTRUCTIONS

If staging deployment fails:

1. Stop Railway services from dashboard
2. Drop staging database (safe — contains no production data)
3. Run `alembic downgrade base` from Railway CLI
4. Delete Vercel staging deployment
5. Fix the issue
6. Re-provision from step 3

---

## 14. PRODUCTION-READINESS RECOMMENDATION

**After staging infrastructure is provisioned and all 21 live smoke tests pass:**

- Promote Vercel deployment from staging to production
- Run `alembic upgrade head` on production database
- Set production `JWT_SECRET_KEY` (different from staging)
- Set production `STRIPE_SECRET_KEY` (live mode)
- Update `FRONTEND_URL` to production origins only
- Update `NEXT_PUBLIC_API_URL` in Vercel to production backend URL
- Run all smoke tests against production URLs
- Monitor for 24 hours

---

## 15. MANUAL OWNER ACTIONS (NEXT STEPS)

1. Create Railway account/project at https://railway.app
2. Provision PostgreSQL and Redis plugins
3. Set all 16 Railway environment variables from Section 4
4. Set JWT_SECRET_KEY to the value generated in Section 2
5. Run database migration from Section 5
6. Deploy web + worker services from Section 3
7. Create Vercel staging project from Section 7
8. Set Vercel environment variables
9. Deploy frontend
10. Update CORS origins in Railway
11. Create Stripe test prices from Section 10
12. Run live smoke tests from Section 11
13. Request DNS approval for staging.sbmedfsai.com