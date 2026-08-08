# Known Issues — Sportsbook Me DFS AI v1.1-beta

---

## High Priority

None. All known Stripe webhook issues resolved (commits 8e945de, 837e7cf, 9d06d7f).

## Medium Priority

1. **Fixture conflict**: Backend test suites cannot run together (298 pass individually). Root cause: multiple sqlite3 in-memory engines. Workaround: run suites separately.

2. **No password reset**: Password reset flow not yet implemented. Admin must reset passwords manually.

3. **Demo data only**: All sports data providers use demo/placeholder data. Live API keys not provisioned.

4. **NBA-only player pool**: Only 13 NBA demo players. Other sports are unsupported placeholders.

5. **Pytest fixture conflict**: Backend tests fail when run together. 307 pass individually using per-suite isolation.

## Low Priority

6. **Stale .next cache**: `rm -rf .next && rebuild` required when switching branches.

7. **No structured logging**: Request IDs and JSON-formatted logs not yet implemented.

8. **No CSP headers**: Content-Security-Policy headers not configured.

9. **QA account password in env var**: Required for bootstrap, rotated manually.

## Resolved (Previously Blocking)

- Stripe webhook double commit → fixed (b1b7b8c)
- RevenueLog nullable columns → fixed (daf10664307c)
- API 2026-03-25.dahlia incompatibility → fixed (stripe_dahlia.py)
- StripeObject → dict normalization → fixed (stripe_convert.py)
- stripe.Subscription.retrieve() normalization → fixed (837e7cf)
- subscription.current_period_end missing → fixed (9d06d7f)
- Canonical frontend URL for Stripe redirects → fixed (5c5f748)