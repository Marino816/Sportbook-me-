# Phase 6 — Stripe Staging Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Merge commit**: `0e5a8cb`
**Branch**: `hermes-production-build`
**Tag**: Not yet created (pending all staging tests)

---

## 1. Merge Verification

| Check | Result |
|-------|--------|
| Tests (5 suites) | 71 passed (24 auth + 9 optimizer + 10 rbac + 18 smoke + 10 billing) |
| TypeScript | Clean |
| Next.js build | Passes (11 routes) |
| Secret scan | Clean (no live keys in code) |
| Migration head (local) | `df12511b7d71` |
| Working tree | Clean |

---

## 2. Railway Deployment

| Check | Status |
|-------|--------|
| Build | ⏸️ Pending Railway auto-deploy |
| Health check | ⏸️ Pending: `curl /health` after deploy |
| Migration applied | ⏸️ Pending: `alembic upgrade head` |
| Current revision | ⏸️ Should be `df12511b7d71` after deploy |

**Railway CLI not accessible from this terminal.** Owner must verify:
```bash
railway run --service web -- alembic upgrade head
railway run --service web -- alembic current
# Expected: df12511b7d71 (head)
```

---

## 3. Stripe Test Mode Configuration

### Required Environment Variables (Railway)

| Variable | Test Mode Value |
|----------|----------------|
| `STRIPE_SECRET_KEY` | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRO_PRICE_ID` | `price_...` (Pro Arena, $29/mo) |
| `STRIPE_ELITE_PRICE_ID` | `price_...` (Elite Stack, $79/mo) |
| `FRONTEND_URL` | Vercel preview URL + `https://sbmedfsai.com` |

### Required Environment Variables (Vercel)

| Variable | Test Mode Value |
|----------|----------------|
| `NEXT_PUBLIC_API_URL` | `https://sportbook-me-production.up.railway.app/api` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |

### Required Stripe Test Products

Create at https://dashboard.stripe.com/test/products:

| Product | Monthly Price | Price ID Variable |
|---------|--------------|-------------------|
| Pro Arena | $29.00 | `STRIPE_PRO_PRICE_ID` |
| Elite Stack | $79.00 | `STRIPE_ELITE_PRICE_ID` |

### Required Webhook Endpoint

Create at https://dashboard.stripe.com/test/webhooks:

| Field | Value |
|-------|-------|
| URL | `https://sportbook-me-production.up.railway.app/api/billing/webhook` |
| Events | `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed` |
| Signing secret | Copy to `STRIPE_WEBHOOK_SECRET` in Railway |

---

## 4. Live Staging Tests — Results

### 4.1 Local Verification (passed)

| # | Test | Result |
|---|------|--------|
| 1 | Registration works | PASS |
| 2 | Login works | PASS |
| 3 | `/api/billing/status` returns free plan | PASS |
| 4 | `/api/billing/checkout` requires auth | PASS |
| 5 | Checkout creates Stripe session (mocked) | PASS |
| 6 | Invalid plan returns 400 | PASS |
| 7 | Portal requires auth | PASS |
| 8 | Portal requires customer ID | PASS |
| 9 | Portal creates session (mocked) | PASS |
| 10 | Webhook invalid signature → 400 | PASS |

### 4.2 Live Staging (requires Railway + Stripe test mode)

| # | Test | Status |
|---|------|--------|
| 11 | Login as staging user | ⏸️ |
| 12 | Open Billing page | ⏸️ |
| 13 | Start Pro Arena checkout | ⏸️ |
| 14 | Complete with test card 4242 | ⏸️ |
| 15 | Success redirect → `/billing?success=true` | ⏸️ |
| 16 | Webhook received + signature verified | ⏸️ |
| 17 | User becomes Pro Arena (`has_access: true`) | ⏸️ |
| 18 | subscriptions row populated | ⏸️ |
| 19 | trial_end uses timezone-aware value | ⏸️ |
| 20 | current_period_end uses TIMESTAMPTZ | ⏸️ |
| 21 | stripe_events stores event ID | ⏸️ |
| 22 | Duplicate webhook → no duplicate processing | ⏸️ |
| 23 | revenue_logs receives exactly 1 record | ⏸️ |
| 24 | Test Billing Portal redirect | ⏸️ |
| 25 | Test Elite Stack upgrade | ⏸️ |
| 26 | Test invoice.payment_failed → downgrade | ⏸️ |
| 27 | Test subscription cancellation → `is_pro: false` | ⏸️ |

---

## 5. Database Verification (post-migration)

Run on Railway Postgres:

```sql
-- Verify column types
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'subscriptions'
  AND column_name IN ('current_period_end', 'trial_end');
-- Expected: both should be 'timestamp with time zone'

-- Verify revenue_logs table exists
SELECT table_name FROM information_schema.tables WHERE table_name = 'revenue_logs';

-- Verify migration state
SELECT * FROM alembic_version;
-- Expected: df12511b7d71
```

---

## 6. Remaining Blockers

| # | Blocker | Priority |
|---|---------|----------|
| 1 | Railway migration not applied | HIGH — blocks all Stripe features |
| 2 | Stripe test products not created | HIGH — blocks checkout |
| 3 | Webhook endpoint not configured | HIGH — blocks subscription sync |
| 4 | STRIPE_SECRET_KEY not set in Railway | HIGH — blocks Stripe API |

---

## 7. Next Steps After All Tests Pass

```bash
git tag -a v1.1-beta -m "Stripe billing: timezone fix, trial support, revenue logging"
git push origin v1.1-beta
```

Then update `CHANGELOG.md` with v1.1-beta entry.