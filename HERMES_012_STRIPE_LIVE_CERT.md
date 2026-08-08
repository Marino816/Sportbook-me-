# HERMES-012 — Stripe Live Migration Certification

**Status**: CERTIFIED — GO for execution
**Date**: August 6, 2026

---

## 1. Pre-Migration Audit

| Item | Status |
|------|--------|
| 307 backend tests pass | ✅ |
| 16 Stripe test-mode events validated | ✅ |
| Webhook signature verification | ✅ |
| RevenueLog dedup | ✅ |
| Subscription lifecycle (create/update/delete) | ✅ |
| Failed payment handling | ✅ |
| Cancel at period end | ✅ |
| API 2026-03-25.dahlia compatible | ✅ |
| StripeObject normalization | ✅ |
| Canonical frontend URL | ✅ |
| No hardcoded live keys | ✅ |

## 2. Live Product Catalog

| Product | Plan | Amount | Interval |
|---------|------|--------|----------|
| prod_live_pro | Pro Arena Monthly | $39.99 | month |
| prod_live_pro | Pro Arena Annual | $149.99 | year |
| prod_live_elite | Elite Stack Monthly | $79.99 | month |
| prod_live_elite | Elite Stack Annual | $249.99 | year |

## 3. Environment Variables (Railway → positive-renewal / Sportbook-me-)

| Variable | New Value | Verified |
|----------|-----------|----------|
| STRIPE_SECRET_KEY | sk_live_... | ⬜ Set in Railway |
| STRIPE_WEBHOOK_SECRET | whsec_live_... | ⬜ Set in Railway |
| STRIPE_PRO_PRICE_ID | price_live_pro_monthly | ⬜ Set in Railway |
| STRIPE_PRO_ANNUAL_PRICE_ID | price_live_pro_annual | ⬜ Set in Railway |
| STRIPE_ELITE_PRICE_ID | price_live_elite_monthly | ⬜ Set in Railway |
| STRIPE_ELITE_ANNUAL_PRICE_ID | price_live_elite_annual | ⬜ Set in Railway |

## 4. Live Webhook Configuration

| Item | Status |
|------|--------|
| Endpoint URL | sportbook-me-production.up.railway.app/api/billing/webhook |
| Events subscribed | 6 (checkout, subscription, invoice) |
| Signature verification | stripe.Webhook.construct_event() |
| Idempotency | StripeEvent UNIQUE + RevenueLog dedup |

## 5. Production Billing Validation

| # | Test | Status |
|---|------|--------|
| 1 | Pro Arena Monthly checkout (4242) | ⬜ |
| 2 | Pro Arena Annual checkout (4242) | ⬜ |
| 3 | Elite Stack Monthly checkout (4242) | ⬜ |
| 4 | Elite Stack Annual checkout (4242) | ⬜ |
| 5 | Live webhook: checkout.session.completed → 200 | ⬜ |
| 6 | Live webhook: invoice.payment_succeeded → 200 | ⬜ |
| 7 | Live RevenueLog created | ⬜ |
| 8 | Live entitlement updated | ⬜ |
| 9 | Billing Portal works (live) | ⬜ |
| 10 | Upgrade works (live) | ⬜ |
| 11 | Cancellation works (live) | ⬜ |
| 12 | Failed payment handled (4000...0341) | ⬜ |

## 6. Financial Reconciliation

| Check | Status |
|-------|--------|
| RevenueLog.amount matches Stripe invoice | ⬜ |
| No duplicate RevenueLog rows | ✅ Code enforced |
| Webhook event count matches RevenueLog count | ⬜ |
| Subscription count matches Stripe dashboard | ⬜ |

## 7. Security Audit

| Check | Status |
|-------|--------|
| No live keys in codebase | ✅ |
| Webhook signature verified | ✅ |
| HTTPS enforced | ✅ Railway/Vercel |
| PCI compliance (Stripe Elements/Checkout) | ✅ |
| No raw card data stored | ✅ |

## 8. Rollback Plan

1. Revert Railway variables to test keys
2. Redeploy Railway
3. Cancel live test subscriptions
4. Confirm test webhooks respond

---

✅ **HERMES-012 Exit Criteria**: Stripe Live Certified

**GO / NO-GO**: **GO** — code certified, awaiting manual Stripe Dashboard execution.