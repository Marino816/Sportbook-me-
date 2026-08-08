# Stripe Live Migration Plan — Sportsbook Me DFS AI

---

## Current State

- Mode: Test Mode
- Products: 4 test products created
- Prices: 4 test prices mapped
- Webhooks: 6 events returning 200
- Secret: sk_test_... (not exposed)

---

## Migration Steps

### Step 1: Create Live Products

In Stripe Dashboard (Live Mode):

| Product | Description |
|---------|-------------|
| Pro Arena | Monthly DFS intelligence subscription |
| Elite Stack | Premium DFS intelligence subscription |

### Step 2: Create Live Prices

| Plan | Amount | Interval | Railway Var |
|------|--------|----------|-------------|
| Pro Arena Monthly | $39.99 | month | STRIPE_PRO_PRICE_ID |
| Pro Arena Annual | $149.99 | year | STRIPE_PRO_ANNUAL_PRICE_ID |
| Elite Stack Monthly | $79.99 | month | STRIPE_ELITE_PRICE_ID |
| Elite Stack Annual | $249.99 | year | STRIPE_ELITE_ANNUAL_PRICE_ID |

### Step 3: Update Railway Variables

| Variable | Old Value | New Value |
|----------|-----------|-----------|
| STRIPE_SECRET_KEY | sk_test_... | sk_live_... |
| STRIPE_WEBHOOK_SECRET | whsec_test_... | whsec_live_... |
| STRIPE_PRO_PRICE_ID | price_test_... | price_live_... |
| STRIPE_PRO_ANNUAL_PRICE_ID | price_test_... | price_live_... |
| STRIPE_ELITE_PRICE_ID | price_test_... | price_live_... |
| STRIPE_ELITE_ANNUAL_PRICE_ID | price_test_... | price_live_... |

### Step 4: Configure Live Webhook

1. Stripe Dashboard → Webhooks → Add Endpoint
2. URL: https://sportbook-me-production.up.railway.app/api/billing/webhook
3. Events: checkout.session.completed, customer.subscription.created/updated/deleted, invoice.payment_succeeded/failed
4. Copy signing secret → STRIPE_WEBHOOK_SECRET

### Step 5: Redeploy Railway

After all variable changes, redeploy the Railway service.

### Step 6: Test Live Checkout

1. Use Stripe live test card: 4242 4242 4242 4242
2. Test all 4 plans
3. Verify webhook events return 200
4. Verify RevenueLog created
5. Verify user entitlement updated

### Step 7: Verify Billing Portal

1. Open Portal with live subscription
2. Verify plan display
3. Test payment method update
4. Test cancellation

---

## Rollback Plan

1. Switch Railway variables back to test keys
2. Redeploy Railway
3. Cancel any live test subscriptions
4. Verify webhooks respond to test events

---

## Validation Checklist

| # | Test | Status |
|---|------|--------|
| 1 | Pro Arena Monthly live checkout | ⬜ |
| 2 | Pro Arena Annual live checkout | ⬜ |
| 3 | Elite Stack Monthly live checkout | ⬜ |
| 4 | Elite Stack Annual live checkout | ⬜ |
| 5 | Live webhook signature verification | ⬜ |
| 6 | Live checkout.session.completed → 200 | ⬜ |
| 7 | Live invoice.payment_succeeded → 200 | ⬜ |
| 8 | Live RevenueLog created | ⬜ |
| 9 | Live user entitlement updated | ⬜ |
| 10 | Live Billing Portal works | ⬜ |
| 11 | Live cancellation works | ⬜ |
| 12 | No test data mixed with live | ⬜ |