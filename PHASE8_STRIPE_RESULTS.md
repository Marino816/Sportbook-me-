# Phase 8 — Stripe Test Validation — Sportsbook Me DFS AI

**Date**: August 5, 2026
**Branch**: `feature/phase8-launch-command-center`
**Status**: PENDING MANUAL VALIDATION

---

## Stripe Configuration Required

### Products to Create

| # | Product | Price | Interval | Railway Env Var |
|---|---------|-------|----------|-----------------|
| 1 | Pro Arena Monthly | $39.99 | Month | `STRIPE_PRO_PRICE_ID` |
| 2 | Pro Arena Annual | $149.99 | Year | `STRIPE_PRO_ANNUAL_PRICE_ID` |
| 3 | Elite Stack Monthly | $79.99 | Month | `STRIPE_ELITE_PRICE_ID` |
| 4 | Elite Stack Annual | $249.99 | Year | `STRIPE_ELITE_ANNUAL_PRICE_ID` |

### Railway Variables Required

| Variable | Source |
|----------|--------|
| `STRIPE_SECRET_KEY` | Stripe dashboard → Developers → API keys → Secret key (test) |
| `STRIPE_WEBHOOK_SECRET` | Stripe dashboard → Webhooks → Signing secret |
| `STRIPE_PRO_PRICE_ID` | Stripe product → Pricing → Price ID |
| `STRIPE_PRO_ANNUAL_PRICE_ID` | Stripe product → Pricing → Price ID |
| `STRIPE_ELITE_PRICE_ID` | Stripe product → Pricing → Price ID |
| `STRIPE_ELITE_ANNUAL_PRICE_ID` | Stripe product → Pricing → Price ID |
| `FRONTEND_URL` | Vercel Preview URL |

### Webhook Setup

1. Stripe dashboard → Webhooks → Add endpoint
2. URL: `https://sportbook-me-production.up.railway.app/api/billing/webhook`
3. Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
4. Copy signing secret → `STRIPE_WEBHOOK_SECRET` in Railway

## Validation Checklist

| # | Test | Card | Expected | Status |
|---|------|------|----------|--------|
| 1 | Pro Arena Monthly checkout | 4242... | Redirect to success | Pending |
| 2 | Pro Arena Annual checkout | 4242... | Redirect to success | Pending |
| 3 | Elite Stack Monthly checkout | 4242... | Redirect to success | Pending |
| 4 | Elite Stack Annual checkout | 4242... | Redirect to success | Pending |
| 5 | Billing Portal access | — | Opens Stripe portal | Pending |
| 6 | Webhook: checkout.completed | — | Subscription created | Pending |
| 7 | Webhook: subscription.created | — | Plan assigned | Pending |
| 8 | Webhook: subscription.updated | — | Status updated | Pending |
| 9 | Webhook: subscription.deleted | — | Access revoked | Pending |
| 10 | Webhook: invoice.paid | — | RevenueLog entry | Pending |
| 11 | Webhook: invoice.failed | — | Past-due status | Pending |
| 12 | Duplicate webhook | — | Idempotent (StripeEvent) | Pending |
| 13 | Upgrade (Pro → Elite) | 4242... | Plan changes | Pending |
| 14 | Downgrade (Elite → Pro) | 4242... | Plan changes | Pending |
| 15 | Cancellation | — | Cancel at period end | Pending |
| 16 | Failed payment | 4000 0000 0000 0341 | Past-due | Pending |

## Test Cards

| Purpose | Number | CVC | Expiry |
|---------|--------|-----|--------|
| Success | 4242 4242 4242 4242 | Any | Any future |
| Decline | 4000 0000 0000 0341 | Any | Any future |

## Backend Verification

After each Stripe event, verify:

- [ ] `subscriptions` table: plan_name, status, current_period_end correct
- [ ] `stripe_events` table: event_id stored, no duplicates
- [ ] `revenue_logs` table: one record per payment_succeeded
- [ ] `users` table: is_pro, active_subscription_id updated
- [ ] `GET /api/billing/status` returns correct tier
- [ ] `GET /api/auth/me` includes updated role/subscription

## Security Validation

- [ ] Webhook signature verified (stripe.Webhook.construct_event)
- [ ] No live Stripe keys used
- [ ] No webhook secret in logs
- [ ] Duplicate webhook event returns 200 without side effects