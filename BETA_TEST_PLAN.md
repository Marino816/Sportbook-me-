# SB-Me DFS AI — Closed Beta Test Plan

**Date**: August 6, 2026
**Version**: v1.1-beta
**Mode**: Invite-only closed beta

---

## Beta Overview

- **Size**: 10-25 invited users
- **Duration**: 2-4 weeks
- **Access**: Admin-managed beta flag (is_beta)
- **Stripe**: Test mode only during beta

---

## Onboarding

1. Admin creates user account
2. Admin toggles `is_beta = true`
3. User receives invite email (manual)
4. User logs in, sees Beta Banner
5. User can submit feedback

---

## Test Focus Areas

| Area | Priority | Detail |
|------|----------|--------|
| Registration | High | Verify email signup works |
| Login | High | JWT token, session persistence |
| Billing | High | Checkout flows (test mode) |
| Optimizer | High | DK/FD lineup generation |
| Projections | Medium | NBA projections display |
| Dashboard | Medium | Loading, empty, error states |
| Mission Control | Medium | Widget display |
| Scout | Low | Provider status |
| Analyst | Low | Edge scores |
| Builder | Low | Portfolio generation |
| Coach | Low | Contest import |
| Assistant | Low | AI chat intent routing |

---

## Success Criteria

- 0 critical bugs
- All 4 checkout flows pass
- 100% opt-ins remain active after week 1
- Average session > 5 minutes
- Feedback received from 50%+ of users

---

## Known Limitations for Beta

- Live data providers not yet configured (demo data only)
- NBA-only player pool (13 players)
- No mobile app
- Password reset not implemented
- Email verification not implemented
- Stripe test cards only
- No production monitoring

---

## Feedback Channels

- Email: qa@sportbookme.ai
- Launch Center feedback form
- Direct message to admin