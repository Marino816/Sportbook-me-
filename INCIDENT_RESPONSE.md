# Incident Response — Sportsbook Me DFS AI

---

## Severity Levels

| Level | Definition | Response Time |
|-------|-----------|---------------|
| P1 — Critical | Platform down, payments failing, data loss | Immediate (15 min) |
| P2 — High | Login broken, optimizer down, webhook errors | 1 hour |
| P3 — Medium | Stale data, dashboard errors, minor feature break | 4 hours |
| P4 — Low | Cosmetic issues, non-blocking bugs | Next business day |

---

## Escalation Path

1. Monitoring alert triggered
2. On-call engineer acknowledges within SLA
3. Initial triage: identify affected component
4. If P1: rollback to last known good commit
5. Root cause analysis
6. Fix + test + deploy
7. Post-incident review

---

## Common Incidents

### Platform Down (P1)

1. Check Railway status: https://status.railway.app
2. Check Vercel status: https://www.vercel-status.com
3. Check Stripe status: https://status.stripe.com
4. Check database health: Railway → Sportbook-me- → Metrics
5. Rollback: `git revert <bad-commit> && git push origin hermes-production-build`

### Webhook Failures (P2)

1. Check Railway logs for webhook errors
2. Verify STRIPE_WEBHOOK_SECRET matches Stripe dashboard
3. Check Stripe Dashboard → Webhooks → Attempts
4. Replay failed events after fix

### Database Issues (P1)

1. Check Railway → PostgreSQL → Metrics
2. Verify connection pool not exhausted
3. Check for long-running migrations
4. Restore from backup if corruption detected

### Authentication Issues (P2)

1. Verify JWT_SECRET_KEY is set in Railway
2. Check for expired tokens
3. Verify bcrypt compatibility

---

## Rollback Procedure

1. Identify bad commit: `git log --oneline -5`
2. Revert: `git revert <sha>`
3. Push: `git push origin hermes-production-build`
4. Railway auto-deploys
5. Verify health: `curl https://sportbook-me-production.up.railway.app/health`

### Database Rollback

1. Railway → PostgreSQL → Backups
2. Click most recent backup
3. Restore to new database
4. Update DATABASE_URL in Railway

---

## Contact

- Admin: qa@sportbookme.ai
- Railway: positive-renewal / Sportbook-me-
- Stripe: Test mode (sk_test_...)