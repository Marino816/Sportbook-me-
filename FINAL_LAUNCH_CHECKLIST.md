# FINAL LAUNCH CHECKLIST — Sportsbook Me DFS AI

**Date**: August 6, 2026
**Target**: v2.0 public production launch

---

## Pre-Launch Verification

### Code Readiness

| # | Item | Status |
|---|------|--------|
| 1 | Repository clean | ✅ |
| 2 | All tests pass | ✅ 307 |
| 3 | TSC clean | ✅ |
| 4 | Build passes | ✅ 18 routes |
| 5 | Secret scan clean | ✅ |
| 6 | No debug/TODO blockers | ✅ |
| 7 | No hardcoded secrets | ✅ |
| 8 | Migration chain clean | ✅ 13 revisions |

### Stripe Live Switch

| # | Item | Status |
|---|------|--------|
| 1 | Create live products (4) | ⬜ Stripe Dashboard |
| 2 | Create live prices (4) | ⬜ Stripe Dashboard |
| 3 | Set STRIPE_SECRET_KEY (live) | ⬜ Railway |
| 4 | Set STRIPE_WEBHOOK_SECRET (live) | ⬜ Railway |
| 5 | Set 4 STRIPE_*_PRICE_ID vars (live) | ⬜ Railway |
| 6 | Configure live webhook endpoint | ⬜ Stripe Dashboard |
| 7 | Test live checkout (4242 card) | ⬜ |
| 8 | Verify RevenueLog for live payment | ⬜ |
| 9 | Verify webhook idempotency (live) | ⬜ |

### DNS & SSL

| # | Item | Status |
|---|------|--------|
| 1 | DNS: sbmedfsai.com → Vercel | ⬜ DNS provider |
| 2 | DNS: www.sbmedfsai.com → Vercel | ⬜ DNS provider |
| 3 | SSL: Vercel auto-provision | ✅ Auto |
| 4 | CORS includes sbmedfsai.com | ✅ Railway FRONTEND_URL |

### Infrastructure

| # | Item | Status |
|---|------|--------|
| 1 | Railway production service | ✅ sportbook-me-production |
| 2 | Vercel production deployment | ✅ Auto-deploy from main |
| 3 | PostgreSQL backup verified | ⬜ Railway Dashboard |
| 4 | Redis persistence verified | ⬜ Railway Dashboard |
| 5 | QA bootstrap disabled (production) | ✅ Auto-disabled |

### Monitoring

| # | Item | Status |
|---|------|--------|
| 1 | Health endpoint | ✅ GET /admin/health |
| 2 | Stripe webhook monitoring | ⬜ Set up alerting |
| 3 | API error tracking | ⬜ Sentry or similar |
| 4 | Uptime monitoring | ⬜ UptimeRobot or similar |
| 5 | Database monitoring | ⬜ Railway metrics |

### Legal

| # | Item | Status |
|---|------|--------|
| 1 | Privacy Policy | ❌ Not drafted |
| 2 | Terms of Service | ❌ Not drafted |
| 3 | Subscription Terms | ❌ Not drafted |
| 4 | Refund Policy | ❌ Not drafted |
| 5 | Age restriction | ❌ Not implemented |
| 6 | Responsible gaming notice | ❌ Not drafted |
| 7 | Attorney review | ❌ Required |

## Launch Sequence

1. ✅ Run final test suite
2. ⬜ Switch Stripe to live mode
3. ⬜ Run live checkout test
4. ⬜ Deploy to Vercel production
5. ⬜ Verify DNS resolves
6. ⬜ Verify HTTPS
7. ⬜ Verify login, billing, optimizer
8. ⬜ Announce launch

## Rollback Plan

| Component | Rollback |
|-----------|----------|
| Code | `git revert` merge commit |
| Database | Railway restore from backup |
| DNS | Revert to previous records |
| Stripe | Switch back to test keys |
| Vercel | Redeploy previous commit |

## Go/No-Go Criteria

- **Go**: All ✅ items confirmed, legal docs in place, Stripe live tested
- **No-Go**: Any Stripe live checkout fails, legal docs missing, critical bug outstanding