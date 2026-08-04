# Phase 6 — Stripe Subscription Implementation Plan

**Date**: August 4, 2026
**Branch**: `feature/phase6-stripe` (to be created from `hermes-production-build`)
**Status**: DESIGN REVIEW — no code written yet

---

## 0. Existing State Audit

The codebase already contains a working Stripe integration skeleton. This plan
extends it rather than rebuilding.

### What Already Works

| Component | Status | File |
|-----------|--------|------|
| Checkout session creation | Working | `backend/api/billing.py:16` |
| Billing portal session | Working | `backend/api/billing.py:35` |
| Webhook signature verification | Working | `backend/services/stripe_service.py:58` |
| Idempotency ledger | Working | `backend/services/stripe_service.py:66` |
| Subscription sync | Working | `backend/services/stripe_service.py:137` |
| Plan→price mapping | Working | `backend/services/stripe_service.py:13` |
| Frontend billing page | UI exists | `web/src/app/billing/page.tsx` |

### What Needs Fixing

| Bug | File | Line | Fix |
|-----|------|------|-----|
| `current_period_end` uses `DateTime` without `timezone=True` | `domain.py:90` | 90 | Add `timezone=True` |
| `_sync_subscription` uses `datetime.fromtimestamp(..., tz=timezone.utc)` on naive column | `stripe_service.py:159` | 159 | Fix column type, use `datetime.fromtimestamp(ts, tz=timezone.utc)` |
| Portal return URL hardcoded to localhost | `billing.py:44` | 44 | Use `FRONTEND_URL` env var |
| No trial period support | `stripe_service.py` | — | Add trialing status handling |
| No CORS on webhook responses (500 hides CORS headers) | `billing.py:64` | 64 | Add explicit CORS header on error |
| Frontend `createCheckout` sends plan as query param | `api.ts:175` | 175 | Change to JSON body |

---

## 1. Backend Architecture

### 1.1 Checkout Flow

```
User clicks "Upgrade to Pro"
        │
        ▼
POST /api/billing/checkout  ───  JWT required (get_current_user)
  Body: {"plan": "Pro Arena"}
        │
        ▼
StripeService.create_checkout_session()
  ├── stripe.checkout.Session.create(
  │     mode='subscription',
  │     customer_email=user.email,
  │     line_items=[{price: PLAN_PRICE_MAP[plan], quantity: 1}],
  │     success_url=FRONTEND_URL + "/billing?success=true&session_id={CHECKOUT_SESSION_ID}",
  │     cancel_url=FRONTEND_URL + "/billing?canceled=true",
  │     metadata={"user_id": str(user.id), "plan_name": plan},
  │     allow_promotion_codes=true,
  │   )
        │
        ▼
Response: {"url": "https://checkout.stripe.com/..."}
        │
Frontend: window.location.href = url
        │
        ▼
User completes payment on Stripe's hosted page
```

### 1.2 Webhook Flow

```
Stripe POSTs event to /api/billing/webhook
        │
        ▼
1. Signature verification (stripe.Webhook.construct_event)
   ├── Valid   → continue
   └── Invalid → HTTP 400 "Invalid signature"
        │
2. Idempotency check (StripeEvent.event_id)
   ├── Already processed → HTTP 200 (no-op)
   └── New               → continue
        │
3. Record event in StripeEvent table (flush to reserve ID)
        │
4. Route to handler based on event['type']:
   │
   ├── checkout.session.completed
   │     └── _handle_checkout_completed()
   │           ├── Lookup user by metadata.user_id (not email)
   │           ├── Set user.stripe_customer_id
   │           ├── Create/update Subscription record
   │           ├── Set user.is_pro = True
   │           └── Set user.active_subscription_id
   │
   ├── customer.subscription.updated
   │     └── _handle_subscription_updated()
   │           ├── Lookup user by stripe_customer_id
   │           ├── Sync subscription status, plan, period_end
   │           └── Update user.is_pro based on status
   │
   ├── customer.subscription.deleted
   │     └── _handle_subscription_updated()  (status='canceled')
   │           └── Set user.is_pro = False
   │
   ├── invoice.payment_succeeded
   │     └── _handle_payment_succeeded()
   │           └── Log revenue (future: Revenue table)
   │
   └── invoice.payment_failed
         └── _handle_payment_failed()
               ├── Set subscription.status = 'past_due'
               └── Set user.is_pro = False (immediate downgrade)
        │
5. db.commit() — all changes in one transaction
```

### 1.3 Billing Portal Flow

```
User clicks "Manage in Stripe"
        │
        ▼
GET /api/billing/portal  ───  JWT required
        │
        ▼
StripeService.create_portal_session()
  ├── stripe.billing_portal.Session.create(
  │     customer=user.stripe_customer_id,
  │     return_url=FRONTEND_URL + "/billing",
  │   )
        │
        ▼
Response: {"url": "https://billing.stripe.com/..."}
        │
Frontend: window.location.href = url
```

### 1.4 Subscription Status

```
GET /api/billing/status  ───  JWT required
        │
        ▼
Query: SELECT * FROM subscriptions WHERE id = user.active_subscription_id
        │
        ▼
Response:
{
  "plan": "Pro Arena",
  "status": "active",
  "next_billing": "2026-09-04T00:00:00+00:00",
  "is_canceled": false,
  "has_access": true,
  "trial_end": null
}
```

### 1.5 Failure Recovery

- **Webhook retries**: Stripe retries webhooks for up to 3 days with exponential backoff. Our idempotency ledger (StripeEvent) ensures double-delivery is safe.
- **Sync drift**: Add `POST /api/billing/sync` (admin-only) to force a re-sync of subscription state from Stripe.
- **Missing webhook**: If a user completes checkout but the webhook doesn't arrive, the `/status` endpoint returns `"free"` until sync. Add a polling fallback: on checkout success page load, poll `/status` for 30 seconds to detect the webhook result.

---

## 2. Frontend Architecture

### 2.1 Billing Page (`/billing`)

Already exists at `web/src/app/billing/page.tsx`. Needs these enhancements:

- **Trial badge**: If `sub.status === "trialing"`, show "7-day free trial — $X/month starting DATE"
- **Cancel confirmation**: Replace `alert()` with a proper toast/modal before redirecting to portal
- **Plan comparison**: Add a third "Starter" card showing current free features
- **Invoice history**: Fetch from Stripe API or display a message to use the portal

### 2.2 Success Page

No separate page needed. The billing page handles `?success=true` via query parameter. Enhancement: after return from Stripe checkout, poll `/api/billing/status` every 3 seconds (max 10 polls) until `has_access === true`, then show success banner.

### 2.3 Canceled Page

No separate page needed. The billing page handles `?canceled=true`. Enhancement: include a "Try again" CTA button.

### 2.4 Authentication Requirement

The billing page already sits behind the AuthProvider. Add explicit redirect: if `!isAuthenticated && !isLoading`, redirect to `/login`.

---

## 3. Database Changes

### 3.1 Fix: subscriptions.current_period_end

| Column | Current | New |
|--------|---------|-----|
| `subscriptions.current_period_end` | `DateTime` | `DateTime(timezone=True)` |

### 3.2 New: subscriptions.trial_end

| Column | Type | Default |
|--------|------|---------|
| `trial_end` | `DateTime(timezone=True)` | `NULL` |

### 3.3 New: revenue_logs table

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` | PK |
| `user_id` | `Integer` | FK → users |
| `subscription_id` | `Integer` | FK → subscriptions |
| `amount` | `Float` | Amount in dollars |
| `currency` | `String` | `"usd"` |
| `stripe_invoice_id` | `String` | Unique |
| `status` | `String` | `"paid"`, `"refunded"` |
| `period_start` | `DateTime(timezone=True)` | |
| `period_end` | `DateTime(timezone=True)` | |
| `created_at` | `DateTime(timezone=True)` | Default: `now(utc)` |

### 3.4 Alembic Migration

Single migration `fix_subscription_timezone_and_add_trial_and_revenue` containing:
1. `ALTER subscriptions.current_period_end TYPE TIMESTAMPTZ`
2. `ALTER subscriptions ADD trial_end TIMESTAMPTZ`
3. `CREATE TABLE revenue_logs (...)`

---

## 4. Stripe Objects

### 4.1 Products and Prices

| Product | Plan Name | Test Price ID Variable | Prod Price ID Variable | Amount |
|---------|-----------|----------------------|----------------------|--------|
| Pro Arena | Pro Arena | `STRIPE_PRO_PRICE_ID` | `STRIPE_PRO_PRICE_ID_LIVE` | $29/mo |
| Elite Stack | Elite Stack | `STRIPE_ELITE_PRICE_ID` | `STRIPE_ELITE_PRICE_ID_LIVE` | $79/mo |

### 4.2 Customer Portal Configuration

Configure in Stripe Dashboard (https://dashboard.stripe.com/settings/billing/portal):
- Allow customers to update payment methods
- Allow customers to cancel subscriptions
- Allow customers to switch plans
- Show invoice history

### 4.3 Webhook Events Registered

| Event | Handled |
|-------|---------|
| `checkout.session.completed` | Create subscription, link customer |
| `customer.subscription.updated` | Sync plan/status |
| `customer.subscription.deleted` | Downgrade user |
| `invoice.payment_succeeded` | Log revenue |
| `invoice.payment_failed` | Downgrade immediately |

---

## 5. Security

### 5.1 Webhook Signature Verification

Already implemented in `stripe_service.py:61` using `stripe.Webhook.construct_event()`. The `STRIPE_WEBHOOK_SECRET` env var must be set. This is the ONLY way to verify webhook authenticity.

### 5.2 JWT Interaction

- All user-facing billing endpoints require `get_current_user` dependency
- Webhook endpoint does NOT use JWT — it uses Stripe signature verification
- User ID is stored in checkout session `metadata.user_id` for webhook lookup (not email, which can change)

### 5.3 Replay Protection

Already implemented: `StripeEvent` table with unique `event_id` constraint. Duplicate webhooks are detected and silently ignored.

### 5.4 Secret Management

| Secret | Environment Variable |
|--------|---------------------|
| Stripe secret key | `STRIPE_SECRET_KEY` |
| Webhook signing secret | `STRIPE_WEBHOOK_SECRET` |
| Test price IDs | `STRIPE_PRO_PRICE_ID`, `STRIPE_ELITE_PRICE_ID` |
| Live price IDs | `STRIPE_PRO_PRICE_ID_LIVE`, `STRIPE_ELITE_PRICE_ID_LIVE` |

---

## 6. Environment Variables

### Test Mode

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...  (test)
STRIPE_ELITE_PRICE_ID=price_...  (test)
```

### Production (future)

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID_LIVE=price_...  (live)
STRIPE_ELITE_PRICE_ID_LIVE=price_...  (live)
```

---

## 7. Testing Plan

### 7.1 Unit Tests (`tests/test_billing.py`)

| Test | What It Verifies |
|------|-----------------|
| `test_status_free_user` | User with no subscription returns Starter plan |
| `test_status_paid_user` | User with active subscription returns plan details |
| `test_checkout_requires_auth` | Unauthenticated request returns 401 |
| `test_portal_requires_auth` | Unauthenticated request returns 401 |
| `test_portal_no_customer` | User without stripe_customer_id returns 400 |
| `test_webhook_valid_signature` | Valid webhook processes successfully |
| `test_webhook_invalid_signature` | Invalid signature returns 400 |
| `test_webhook_duplicate_idempotent` | Same event_id twice → second is no-op |
| `test_checkout_completed_creates_subscription` | Full flow: event → subscription created |
| `test_subscription_updated_syncs_status` | Status change synced to DB |
| `test_subscription_deleted_downgrades_user` | Cancel → is_pro = False |
| `test_payment_failed_downgrades` | Failed invoice → status past_due |
| `test_sync_subscription_from_stripe` | Force-sync endpoint reconciles state |

Mock `stripe` library to avoid live API calls.

### 7.2 Integration Tests (requires Stripe test mode)

| Test | What It Verifies |
|------|-----------------|
| Full checkout → webhook → status verification | End-to-end flow |
| Upgrade Pro Arena → Elite Stack | Plan change sync |
| Cancel via portal → webhook → downgrade | Cancel flow |
| Trial signup → trial expiry → auto-downgrade | Trial handling |

### 7.3 End-to-End Tests (requires live staging)

| Test | What It Verifies |
|------|-----------------|
| Register → upgrade → Stripe checkout → webhook → has_access | Full user journey |
| Cancel subscription → webhook → status shows canceled | Cancel flow |
| Payment failure → webhook → user downgraded | Failure recovery |

---

## 8. Deployment Plan

### Step 1: Create feature branch
```bash
git checkout hermes-production-build
git checkout -b feature/phase6-stripe
```

### Step 2: Implement backend changes
1. Fix `current_period_end` column type (add `timezone=True`)
2. Add `trial_end` column
3. Create `revenue_logs` table
4. Create Alembic migration
5. Update `stripe_service.py`:
   - Use `metadata.user_id` for checkout lookup instead of email
   - Add trial period handling
   - Add force-sync endpoint
   - Fix portal return URL to use `FRONTEND_URL`
6. Update `billing.py`:
   - Change checkout to accept JSON body
   - Add `sync` endpoint
   - Add proper error handling with CORS headers
7. Add unit tests

### Step 3: Implement frontend changes
1. Add trial badge to billing page
2. Add polling for subscription status after checkout return
3. Add explicit auth redirect
4. Create Stripe test products in dashboard

### Step 4: Stage and test
1. Push to `feature/phase6-stripe`
2. Deploy to Vercel Preview
3. Test checkout flow with Stripe test card (4242 4242 4242 4242)
4. Verify webhooks via `stripe listen --forward-to`
5. Run test suite

### Step 5: Merge
1. PR `feature/phase6-stripe` → `hermes-production-build`
2. Review + merge
3. Deploy to staging

---

## 9. Rollback Plan

### If Stripe checkout breaks
1. Revert frontend billing page to show "Subscription unavailable" banner
2. Disable `POST /api/billing/checkout` endpoint (return 503)
3. Webhooks continue processing (no change)

### If webhooks break
1. Stripe retries automatically (3-day window)
2. Fix webhook handler → deploy → Stripe delivers queued events
3. Lost events: run `POST /api/billing/sync` for affected users

### Database rollback
```bash
alembic downgrade -1  # reverts the timezone+trial+revenue migration
```

---

## 10. Files Changed

| File | Change Type |
|------|-------------|
| `backend/models/domain.py` | Fix timezone, add trial_end, add RevenueLog |
| `backend/models/schemas.py` | Add billing request/response schemas |
| `backend/api/billing.py` | Fix portal URL, add sync endpoint, fix checkout body |
| `backend/services/stripe_service.py` | Fix user lookup, add trial, fix timezone |
| `backend/migrations/versions/*.py` | New migration |
| `backend/tests/test_billing.py` | 13 unit tests |
| `web/src/app/billing/page.tsx` | Trial badge, polling, auth guard |
| `web/src/lib/api.ts` | Fix checkout to send JSON body |

---

## 11. Success Criteria

- [ ] User can subscribe to Pro Arena via Stripe test checkout
- [ ] User can subscribe to Elite Stack via Stripe test checkout
- [ ] Checkout success → webhook → `has_access: true` within 3 polls
- [ ] Checkout cancel → no charges → user remains on Starter
- [ ] Billing portal opens for subscribed users
- [ ] Subscription cancel via portal → webhook → user downgraded
- [ ] Payment failure → webhook → user downgraded immediately
- [ ] Duplicate webhooks are idempotent (no double-processing)
- [ ] Invalid webhook signatures return 400
- [ ] 13 unit tests pass
- [ ] TSC passes
- [ ] Next.js build passes