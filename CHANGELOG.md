# Changelog — Sportsbook Me DFS AI

## v1.1-beta (August 2026)

### Added
- Stripe billing: 4 plans (Pro Arena $39.99/mo, $149.99/yr; Elite Stack $79.99/mo, $249.99/yr)
- Stripe webhook handling: 6 events, signature verification, idempotency
- RevenueLog for payment tracking with dedup
- Stripe API 2026-03-25.dahlia compatibility
- StripeObject → dict normalization layer
- Subscription gating across 7 SB-Me modules
- QA staging account bootstrap (idempotent, production-disabled)
- `/admin/launch-center` operational dashboard
- `/admin/health` live component monitoring
- Canonical frontend URL helper for Stripe redirects
- is_beta field: admin-managed closed beta flag
- BetaBanner component for invite-only phase
- Closed beta documentation (BETA_TEST_PLAN, KNOWN_ISSUES, PRODUCTION_CHECKLIST)

### Fixed
- Stripe webhook double-commit (b1b7b8c)
- RevenueLog nullable columns (daf10664307c)
- Stripe redirect URLs using comma-separated CORS list (5c5f748)
- subscription.current_period_end KeyError in dahlia API (9d06d7f)
- StripeObject → dict normalization for webhook handlers (8e945de)
- stripe.Subscription.retrieve() normalization (837e7cf)

### Removed
- Brand references to "Apex" (replaced with "Sportsbook Me DFS AI" / "SB-Me")

---

## v1.0-beta

### Added
- User registration and login (JWT, bcrypt)
- RBAC (admin/user roles)
- Admin dashboard
- Projections page
- Optimizer page (DK/FD NBA)
- Backtesting page
- Billing page (Stripe integration code)
- Scout, Analyst, Builder, Coach, Assistant, Mission Control (SB-Me Intelligence)
- 7 SB-Me modules, 43 database tables, 12 Alembic migrations
- PostgreSQL + Redis on Railway
- Vercel frontend deployment