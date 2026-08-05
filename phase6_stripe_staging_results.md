# Phase 6 — Stripe Staging Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Merge commit**: `0e5a8cb`
**Latest commit**: `4953bc9`
**Branch**: `hermes-production-build`
**Tag**: Not yet created

---

## 1. Merge + Build Verification

| Check | Result |
|-------|--------|
| Tests (5 suites) | 71 passed |
| TypeScript | Clean |
| Next.js build | Passes (11 routes) |
| Secret scan | Clean |
| Migration head (local) | `df12511b7d71` |

---

## 2. Final Pricing (4 Plans)

| Plan | Price | Interval | Env Variable |
|------|-------|----------|-------------|
| Pro Arena | $39.99 | Monthly | `STRIPE_PRO_PRICE_ID` |
| Pro Arena Annual | $149.99 | Yearly | `STRIPE_PRO_ANNUAL_PRICE_ID` |
| Elite Stack | $79.99 | Monthly | `STRIPE_ELITE_PRICE_ID` |
| Elite Stack Annual | $249.99 | Yearly | `STRIPE_ELITE_ANNUAL_PRICE_ID` |

All 4 plans mapped in `backend/services/stripe_service.py` `PLAN_PRICE_MAP`.
All 4 displayed in `web/src/app/billing/page.tsx` (4-column layout).

---

## 3. Railway Deployment

| Check | Status |
|-------|--------|
| Build | ⏸️ Pending Railway auto-deploy |
| `/health` | ⏸️ Pending |
| Migration | ⏸️ Pending: `alembic upgrade head` |
| Revision | ⏸️ Should be `df12511b7d71` after deploy |

---

## 4. Stripe Test Products (Dashboard)

Create at https://dashboard.stripe.com/test/products:

| Product | Price | Interval | Recurring |
|---------|-------|----------|-----------|
| Pro Arena Monthly | $39.99 | month | Yes |
| Pro Arena Annual | $149.99 | year | Yes |
| Elite Stack Monthly | $79.99 | month | Yes |
| Elite Stack Annual | $249.99 | year | Yes |

---

## 5. Environment Variables

### Railway

| Variable | Value |
|----------|-------|
| `STRIPE_SECRET_KEY` | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRO_PRICE_ID` | `price_...` |
| `STRIPE_PRO_ANNUAL_PRICE_ID` | `price_...` |
| `STRIPE_ELITE_PRICE_ID` | `price_...` |
| `STRIPE_ELITE_ANNUAL_PRICE_ID` | `price_...` |
| `JWT_SECRET_KEY` | Generated 64-char |
| `NODE_ENV` | `production` |
| `FRONTEND_URL` | Vercel preview + `sbmedfsai.com` |

### Vercel

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Railway backend URL `/api` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |

---

## 6. Webhook Endpoint

Stripe Dashboard → Webhooks → Add endpoint:

| Field | Value |
|-------|-------|
| URL | `https://sportbook-me-production.up.railway.app/api/billing/webhook` |
| Events | `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed` |

---

## 7. Live Staging Tests

| # | Test | Plan | Status |
|---|------|------|--------|
| 1 | Login as staging user | — | ⏸️ |
| 2 | Open Billing page | — | ⏸️ |
| 3 | Checkout Pro Arena monthly | Pro Arena | ⏸️ |
| 4 | Pay with 4242 4242 4242 4242 | Pro Arena | ⏸️ |
| 5 | Success redirect | Pro Arena | ⏸️ |
| 6 | Webhook received + verified | Pro Arena | ⏸️ |
| 7 | User becomes Pro Arena | Pro Arena | ⏸️ |
| 8 | Checkout Pro Arena annual | Pro Arena Annual | ⏸️ |
| 9 | Checkout Elite Stack monthly | Elite Stack | ⏸️ |
| 10 | Checkout Elite Stack annual | Elite Stack Annual | ⏸️ |
| 11 | Subscription rows populated | All | ⏸️ |
| 12 | trial_end timezone-aware | All | ⏸️ |
| 13 | current_period_end TIMESTAMPTZ | All | ⏸️ |
| 14 | stripe_events stores event ID | All | ⏸️ |
| 15 | Duplicate webhook → idempotent | Any | ⏸️ |
| 16 | revenue_logs receives record | Any | ⏸️ |
| 17 | Billing Portal redirect works | Any | ⏸️ |
| 18 | invoice.payment_failed → downgrade | Any | ⏸️ |
| 19 | Subscription cancellation → is_pro:false | Any | ⏸️ |

---

## 8. Webhook Mapping

Each Stripe price ID must map correctly in `_sync_subscription`:

```
price_pro_xxx        → "Pro Arena"       (monthly)
price_pro_annual_xxx → "Pro Arena Annual" (yearly)
price_elite_xxx      → "Elite Stack"      (monthly)
price_elite_annual_xxx → "Elite Stack Annual" (yearly)
```

The `stripe.Subscription.retrieve()` response includes the interval in `items.data[0].plan.interval`. The `cancel_at_period_end` and `current_period_end` fields are synced regardless of interval.

---

## 9. Database Verification

Post-migration, run on Railway:

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'subscriptions'
AND column_name IN ('current_period_end', 'trial_end');
-- Expected: both 'timestamp with time zone'

SELECT * FROM alembic_version;
-- Expected: df12511b7d71

SELECT table_name FROM information_schema.tables
WHERE table_name = 'revenue_logs';
-- Expected: revenue_logs
```

---

## 10. Remaining Blockers

| # | Blocker | Priority |
|---|---------|----------|
| 1 | Railway migration `df12511b7d71` not applied | HIGH |
| 2 | 4 Stripe test products not created | HIGH |
| 3 | Webhook endpoint not configured | HIGH |
| 4 | 6 env vars not set in Railway | HIGH |

---

## 11. After All Tests Pass

```bash
git tag -a v1.1-beta -m "Stripe billing: 4-tier pricing, timezone fix, trial support, revenue logging"
git push origin v1.1-beta
```

Update CHANGELOG.md with v1.1-beta section.