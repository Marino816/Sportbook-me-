# Phase 1 Repository Audit — Sportsbook Me DFS AI

**Date**: 2026-08-04
**Branch**: `hermes-production-build`
**Commit**: `0c7781a` feat: full 12-sport projections, optimizer, and backtesting pages

---

## 1. Repository Structure

Monorepo with four components:

```
Sports Book Me/
├── backend/          FastAPI API (Python 3.13)
├── web/              Next.js 15 frontend (TypeScript, Tailwind 4)
├── mobile/           Expo/React Native app (TypeScript)
├── prototype/        Legacy Streamlit v7 app (app.py, 515 lines)
├── mobile_prototype/ Empty directory
├── docker-compose.yml Postgres 15 + Redis 7
├── .env.example      Root env template
└── README.md         DFS Builder v7 docs (outdated - references Streamlit)
```

The README is stale — describes the Streamlit prototype, not the Next.js/Express API architecture.

## 2. Frontend — Next.js 15 (`web/`)

| Item | Status |
|------|--------|
| Pages | 7 pages: `/`, `/dashboard`, `/projections`, `/optimizer`, `/backtesting`, `/billing`, `/admin` |
| Sports coverage | 12 sports: NFL, NBA, MLB, NHL, Soccer, MLS, UFC, PGA, NCAAF, NCAAM, NCAAW, Boxing |
| State management | React Query (`@tanstack/react-query`) |
| Styling | Tailwind CSS 4 with dark theme (`#0d1117` base) |
| Security headers | Vercel config applies HSTS, X-Frame-Options, X-Content-Type-Options, XSS Protection |
| Analytics | Vercel Analytics + Speed Insights |
| Build | Next.js 15.5.14 with Turbopack |
| ESLint | Ignored during builds (`ignoreDuringBuilds: true`) |

**Notable issues:**

- **F1. Duplicate Next config files**: `next.config.js` (active, ignores ESLint) and `next.config.ts` (default empty). Only `.js` is effective; `.ts` is dead code.
- **F2. Health check hardcoded to localhost**: `web/src/lib/api.ts:157` — `checkHealth()` always fetches `http://localhost:8000/health`. Never checks a configurable backend URL.
- **F3. All data pages are demo-mode ready**: When API is unreachable, every page falls back to inline demo data. The UX is polished — demo mode is explicitly tagged.

## 3. Backend — FastAPI (`backend/`)

| Item | Status |
|------|--------|
| Framework | FastAPI with async SQLAlchemy |
| API modules | router.py (DFS), admin.py, sports.py, stats.py, billing.py |
| ML | XGBoost pipeline (pipeline.py — not integrated into any endpoint) |
| Optimizer | OR-Tools SCIP integer programming (NBA DraftKings only) |
| Integrations | BallDontLie (NBA players/stats), The Odds API (spreads/totals) |
| Billing | Stripe Checkout + Customer Portal + Webhooks |
| Worker | Celery (broken — see B3) |
| Database | PostgreSQL via asyncpg, Redis for Celery |
| Deployment | Railway with Procfile (web + worker + beat) |

### API Endpoints

| Method | Path | Module | Status |
|--------|------|--------|--------|
| GET | `/health` | main.py | Working (simple status) |
| GET | `/api/projections/{slate_id}` | router.py | Working (demo fallback) |
| POST | `/api/optimize` | router.py | Working (requires auth) |
| GET | `/api/export/csv` | router.py | Stub (auth-gated, no real CSV generation) |
| GET | `/api/admin/summary` | admin.py | Working (hardcoded churn/trials) |
| GET | `/api/admin/revenue-trends` | admin.py | Working (static array) |
| GET | `/api/admin/distribution` | admin.py | Working (DB query) |
| GET | `/api/admin/events` | admin.py | Working (DB query + demo fallback) |
| GET | `/api/admin/health` | admin.py | Working (DB query + demo fallback) |
| POST | `/api/admin/sync/trigger` | admin.py | **BROKEN** (see B1) |
| GET | `/api/stats/performance` | stats.py | Working (demo fallback) |
| GET | `/api/stats/velocity` | stats.py | Working (static array) |
| GET | `/api/stats/alpha-stacks` | stats.py | Working (static data) |
| GET | `/api/sports/lobby` | sports.py | Working (demo fallback) |
| POST | `/api/sports/slip/calculate` | sports.py | Working |
| POST | `/api/billing/checkout` | billing.py | Working (Stripe) |
| GET | `/api/billing/portal` | billing.py | Working (Stripe) |
| POST | `/api/billing/webhook` | billing.py | Working (Stripe) |
| GET | `/api/billing/status` | billing.py | Working |

## 4. Mobile Application — Expo/React Native (`mobile/`)

| Item | Status |
|------|--------|
| Framework | Expo SDK 54, React Native 0.81 |
| Screens | 7: Home, Projections, Optimizer, Sports, Performance, Billing, Admin |
| Navigation | `@react-navigation/bottom-tabs` with 5 tabs |
| API client | Mirrors web `api.ts` — same hardcoded localhost |
| Charts | `react-native-chart-kit` (Performance screen) |

**Notable issues:**

- **M1. Hardcoded localhost URL**: `mobile/src/lib/api.ts:1` — `API_BASE_URL = "http://localhost:8000/api"`. No environment variable or config.
- **M2. Billing and Admin screens exist as files but are not registered in App.tsx tab navigator** — they're unreachable.

## 5. Database (`backend/models/`)

**9 tables** (domain.py):

| Table | Purpose |
|-------|---------|
| `users` | User accounts, Stripe customer ID, subscription reference |
| `slates` | Daily contest slates (sport, site, date) |
| `players` | Canonical player entities |
| `game_logs` | Historical performance for ML training |
| `projections` | Per-player per-slate projections |
| `lineups` | Saved optimized lineups |
| `subscriptions` | Stripe subscription tracking |
| `matchups` | Sports match data with odds |
| `system_status` | Provider health monitoring |
| `stripe_events` | Webhook idempotency ledger |

**Critical issue:**

- **DB1. No Alembic migrations**: `alembic` is in requirements.txt, but there are zero migration files in the repo. Schema can only be created via `Base.metadata.create_all()`, which was intentionally removed from the lifespan handler (commit `35c173f`) because it caused 502 errors during slow DB connections. **This means there is no way to create tables in production** without running raw SQL or a separate management command that doesn't exist.

## 6. Sports-Data Integrations

### BallDontLie (`backend/integrations/balldontlie.py`)
- Fetches NBA players and game logs
- Demo fallback when no API key
- Key: `BALLDONTLIE_API_KEY`

### The Odds API (`backend/integrations/odds.py`)
- Fetches spreads and totals for NBA
- Demo fallback when no API key
- Key: `ODDS_API_KEY`

**Issue:**

- **I1. NBA-only integrations**: Both `get_nba_odds()` and `get_players()`/`get_recent_game_logs()` are NBA-specific. No NFL, MLB, NHL, or other sport data sources despite 12-sport UI coverage.

## 7. Projection Engine (`backend/ml/pipeline.py`)

- XGBoostRegressor with configurable hyperparameters
- Preprocessing: NaN fill, one-hot encoding
- Train/test split with MAE and RMSE reporting
- `predict()` method for new slate features

**Issue:**

- **PE1. Not wired to any API endpoint**: The `XGBoostProjectionModel` class is fully implemented but never instantiated or called from any route. No training endpoint, no prediction endpoint, no model persistence. The projections API (`/api/projections/{slate_id}`) returns hardcoded demo data or raw DB lookups — never ML-generated.

## 8. Lineup Optimizer (`backend/optimizer/core.py`)

- OR-Tools SCIP integer programming solver
- Binary variables per player (1 = selected, 0 = not)
- Multi-lineup generation with uniqueness constraints

**Issues:**

- **O1. DraftKings NBA only**: The constraint method is `build_nba_draftkings_constraints()` — hardcoded for $50,000 salary cap, 8-player rosters, PG/SG/SF/PF/C/G/F/UTIL positions.
- **O2. No FanDuel support**: Despite the UI toggling between DraftKings and FanDuel, the backend ignores the `site` parameter. FanDuel has different salary cap, roster sizes, and position rules (no multi-position eligibility in the same way).
- **O3. No multi-sport constraints**: NFL, MLB, NHL, etc. all have completely different roster structures. The optimizer needs per-sport constraint methods.
- **O4. Advanced settings not passed**: The optimizer receives `settings` from the frontend (locked/excluded players, max exposure, team stacks) but the `DFSOptimizer.__init__` expects `locked`/`excluded` keys while the frontend sends `locked_player_ids`/`excluded_player_ids`. The excluded filter in `build_variables()` at line 28 checks `settings.get('excluded', [])` — this key mismatch means locked/excluded players never work.

## 9. Stripe Integration (`backend/services/stripe_service.py`)

- Checkout sessions via `stripe.checkout.Session.create()`
- Customer Portal via `stripe.billing_portal.Session.create()`
- Webhook handling with idempotency (`StripeEvent` ledger)
- Subscription sync: checkout.completed, subscription.updated, payment succeeded/failed

**Issues:**

- **S1. Default test price IDs**: `price_pro_test` / `price_elite_test` used when env vars are missing.
- **S2. Billing price mismatch**: UI shows $29/mo (Pro) / $79/mo (Elite), but the DB default MRR is $49.99. Also the `PLAN_PRICE_MAP` only maps to Stripe price IDs — the actual dollar amounts come from Stripe, not from local config.
- **S3. No `STRIPE_PUBLISHABLE_KEY` in backend**: The cross-origin / Stripe Elements initialization on the frontend needs a publishable key, but `.env.example` only shows it for the web.

## 10. Authentication

**Status: Placeholder / broken.**

The `get_current_user()` dependency in `billing.py:17`:
- Uses sync `Session` type hint instead of `AsyncSession` — mismatched with `get_db()` which yields `AsyncSession`
- If no user exists, creates a default `"shark@apexdfs.io"` user — there is no registration flow
- No JWT, no OAuth, no session tokens
- CORS is wide open (`allow_origins=["*"]` when `FRONTEND_URL` is not set)

**The entire auth system is a stub.** Any request to `/api/optimize` gets the first user in the DB.

## 11. Environment Variables

### Root `.env.example`:
```
DATABASE_URL, REDIS_URL, BALLDONTLIE_API_KEY, ODDS_API_KEY, STRIPE_SECRET_KEY, FIREBASE_CREDENTIALS_JSON, USE_DEMO_DATA_FALLBACK
```

### Backend `.env.example` adds:
```
FRONTEND_URL, API_URL, STRIPE_WEBHOOK_SECRET, STRIPE_PRO_PRICE_ID, STRIPE_ELITE_PRICE_ID, NODE_ENV, DB_POOL_SIZE, DB_MAX_OVERFLOW, STITCH_API_KEY
```

### Web `.env.example`:
```
NEXT_PUBLIC_API_URL, NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY, NEXT_PUBLIC_FIREBASE_API_KEY, NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN, NODE_ENV
```

**Issues:**

- **E1. `STITCH_API_KEY` referenced but no Stitch integration code exists in the repo.**
- **E2. `FIREBASE_CREDENTIALS_JSON` and Firebase env vars exist but no Firebase code exists. `firebase-admin` is in requirements.txt unused.**
- **E3. `USE_DEMO_DATA_FALLBACK` is referenced in integrations but never read from env in the API routes — only in integration classes themselves.**

## 12. Deployments

### Vercel (Frontend)
- Configured via `web/vercel.json` with security headers
- Next.js build with Turbopack
- Analytics + Speed Insights wired in
- Domain: `sbmedfsai.com`

### Railway (Backend)
- `backend/Procfile`: web (gunicorn/uvicorn), worker (celery), beat (celery beat)
- Database URL auto-converts `postgresql://` to `postgresql+asyncpg://`
- SSL required for production (`NODE_ENV=production`)

## 13. Build Scripts / Dependencies

### Web (`package.json`)
- `dev`: `next dev --turbopack`
- `build`: `next build --turbopack`
- `start`: `next start`
- `lint`: `eslint`

All dependencies resolve cleanly — no version conflicts detected.

### Backend (`requirements.txt`)
- FastAPI, SQLAlchemy, Celery, OR-Tools, XGBoost, scikit-learn, pandas, numpy, Stripe, Firebase Admin, Redis, asyncpg, gunicorn
- **Duplicate**: `uvicorn[standard]` appears on lines 2 and 17
- **Stale file**: `requirements copy.txt` (identical duplicate)
- No version pins — all unpinned dependencies

### Mobile (`package.json`)
- Expo 54, React Native 0.81, React Navigation, lucide-react-native, react-native-chart-kit
- No version conflicts detected

## 14. Dependency Conflicts

None detected. All package.json files have compatible version ranges.

## 15. Broken Imports

| Severity | Location | Issue |
|----------|----------|-------|
| **CRITICAL** | `backend/worker/tasks.py:10` | `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:***@celery_app.task` — line is truncated/garbled. The Celery app definition is corrupt. |
| **CRITICAL** | `backend/api/admin.py:106` | `from backend.worker.tasks import sync_daily_slate` — wrong import path. When running from `backend/`, it should be `from worker.tasks import sync_daily_slate`. |
| **HIGH** | `backend/api/billing.py:17` | `get_current_user` uses sync `Session` type hint but `get_db()` yields `AsyncSession`. Mixed sync/async SQLAlchemy sessions. |

## 16. Failing Tests

**No tests exist.** No `test/` directory, no `*_test.py`, no `*.test.ts`, no test framework configured.

## 17. Security Issues

| Severity | Issue |
|----------|-------|
| **CRITICAL** | No authentication — `get_current_user()` creates a default user if DB is empty. Any request gets authed as a real user. |
| **HIGH** | CORS defaults to `["*"]` when `FRONTEND_URL` env var is not set (`backend/main.py:37`). |
| **MEDIUM** | Stripe webhook secret is checked but if `WEBHOOK_SECRET` is None, `stripe.Webhook.construct_event()` will fail with a ValueError that gets caught — but a misconfigured setup could silently accept unverified webhooks. |
| **MEDIUM** | Hardcoded password in `docker-compose.yml` (`POSTGRES_PASSWORD: password`). |
| **LOW** | `.env` files are gitignored, but `.env.example` files contain no actual secrets. |

## 18. Missing Pages (Frontend Routes)

All frontend routes referenced in Navigation.tsx exist as page files:
- `/` ✓
- `/dashboard` ✓
- `/projections` ✓
- `/optimizer` ✓
- `/backtesting` ✓
- `/billing` ✓
- `/admin` ✓

**Missing admin sub-pages** (linked from AdminSidebar but return 404):
- `/admin/projections` — MISSING
- `/admin/optimizer` — MISSING
- `/admin/billing` — MISSING
- `/admin/users` — MISSING
- `/admin/support` — MISSING
- `/admin/logs` — MISSING

## 19. Missing API Endpoints

| Need | Status |
|------|--------|
| Model training endpoint | MISSING — ML pipeline exists but not wired |
| Model prediction endpoint | MISSING — projections use demo/DB data only |
| FanDuel optimizer constraints | MISSING — DraftKings NBA only |
| Multi-sport optimizer constraints | MISSING — only NBA DK implemented |
| Registration/signup | MISSING |
| Login/logout | MISSING |
| Player lock/exclude in optimizer | BROKEN — key mismatch (see O4) |
| CSV export (actual file) | STUB — returns JSON, no file download |

## 20. Database Migrations

**No migration files exist.** Alembic is configured (in requirements.txt) but:
- No `alembic.ini`
- No `migrations/` directory
- No migration scripts
- `Base.metadata.create_all()` was removed from lifespan

The database tables can only be created manually or via a separate init script that doesn't exist.

## 21. Deployment Blockers

| # | Blocker | Impact |
|---|---------|--------|
| 1 | No database migration path | Cannot create tables in production without manual intervention |
| 2 | Worker tasks file is corrupted | Celery worker won't start — daily slate sync is dead |
| 3 | Admin manual sync import is broken | `/api/admin/sync/trigger` will 500 error |
| 4 | No authentication | Any client can call `/api/optimize` and get unlimited access (subject to subscription check which auto-creates a user) |
| 5 | Optimizer key mismatch | Locked/excluded player controls don't work |
| 6 | Billing sync/async session mismatch | `get_current_user` may fail on some query patterns |

## Summary

| Category | Score |
|----------|-------|
| Frontend completeness | 95% — polished, 12-sport UI, all pages exist |
| Backend completeness | 60% — API structure solid, but optimizer limited, ML not wired |
| Mobile completeness | 70% — 7 screens, but 2 unreachable, hardcoded localhost |
| Security | 25% — no real auth, no rate limiting, wide CORS default |
| Test coverage | 0% |
| Deployment readiness | 40% — 2 critical code corruption bugs, no DB migrations |

### Critical Blockers (Must Fix Before Production)

1. **Worker tasks file corruption** (`backend/worker/tasks.py:10`) — Celery cannot start
2. **Broken import in admin.py** (`backend/api/admin.py:106`) — manual sync crashes
3. **No database migrations** — cannot create tables in production
4. **No authentication** — zero security boundary
5. **Optimizer locked/excluded key mismatch** (`build_variables()` checks `excluded` but frontend sends `excluded_player_ids`)

### Recommended Next Phase

**Phase 2 — Hardening (before any feature work):**

1. Fix the 3 corrupted/broken code paths (worker tasks, admin import, optimizer keys)
2. Create Alembic migration infrastructure and initial migration
3. Implement proper JWT authentication (or Firebase Auth since firebase-admin is available)
4. Fix billing async/sync session mismatch
5. Remove dead code (duplicate config files, duplicate requirements, unused Stitch key)
6. Add at least smoke tests for critical paths
7. Wire ML pipeline into a `/api/projections/generate` endpoint
8. Add FanDuel optimizer constraints and multi-sport support skeleton