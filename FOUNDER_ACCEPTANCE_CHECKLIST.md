# SPORTBOOK ME DFS AI — Founder Acceptance Checklist

## Phase 0 — Multi-Lineup Production Fix

| # | Test | Expected | Status |
|---|------|----------|--------|
| 0.1 | DK MLB + Balanced + 3 lineups | 3 unique lineups returned | |
| 0.2 | FD MLB + Balanced + 3 lineups | 3 unique lineups returned | |
| 0.3 | Each lineup has legal roster (DK:10, FD:9) | All valid | |
| 0.4 | No slate_id=0 sent | Never | |

**Phase 0 BLOCKED until DK and FD both return 3 lineups.**

---

## Phase 1 — Authentication & Session

| # | Test | Expected | Status |
|---|------|----------|--------|
| 1.1 | Login with Founder email + password | JWT returned, role=admin | |
| 1.2 | Session persists across app restart | No re-login needed | |
| 1.3 | Logout clears token | Login screen shown | |
| 1.4 | Invalid credentials rejected | 401, error message shown | |
| 1.5 | Password survives Railway deploy | No overwrite | |

---

## Phase 2 — SportsDataIO / Data

| # | Test | Expected | Status |
|---|------|----------|--------|
| 2.1 | SportsDataIO labeled TRIAL_SCRAMBLED | Visible on mobile | |
| 2.2 | MLB slates load from production DB | slate_id=1,2 | |
| 2.3 | Player pool > 0 for both slates | Counts shown | |
| 2.4 | DK salaries use DraftKingsSalary | Correct source | |
| 2.5 | FD salaries use FanDuelSalary | Correct source | |
| 2.6 | Ownership shows N/A | No fake 5% | |
| 2.7 | Re-ingestion idempotent | No duplicates | |

---

## Phase 3 — DraftKings MLB Optimizer

| # | Test | Expected | Status |
|---|------|----------|--------|
| 3.1 | MLB + DK → 10 players | Exactly 10 | |
| 3.2 | Roster: 2P/C/1B/2B/3B/SS/3OF | Verified order | |
| 3.3 | Salary ≤ $50,000 | Under cap | |
| 3.4 | 3 lineups: each different | Unique | |
| 3.5 | Lineup detail: player names, teams, positions | All present | |
| 3.6 | Projected score = sum of player projections | Reconciles | |
| 3.7 | Slate filter shows ONLY DK slate | Not FD | |

---

## Phase 4 — FanDuel MLB Optimizer

| # | Test | Expected | Status |
|---|------|----------|--------|
| 4.1 | MLB + FD → 9 players | Exactly 9 | |
| 4.2 | Roster: P/C1B/2B/3B/SS/3OF/UTIL | Verified order | |
| 4.3 | Salary ≤ $35,000 | Under FD cap | |
| 4.4 | 3 lineups: each different | Unique | |
| 4.5 | UTIL = hitter (not pitcher) | Verified | |
| 4.6 | Slate filter shows ONLY FD slate | Not DK | |

---

## Phase 5 — Strategies

| # | Test | Expected | Status |
|---|------|----------|--------|
| 5.1 | Balanced → 3 lineups | 3 unique | |
| 5.2 | Cash → 3 lineups | High exposure allowed | |
| 5.3 | GPP → 3 lineups | Stacking present | |
| 5.4 | Aggressive → 3 lineups | More diversity | |
| 5.5 | Nuclear → 3 lineups | Max diversity | |

---

## Phase 6 — SB ME Intelligent AI

| # | Test | Expected | Status |
|---|------|----------|--------|
| 6.1 | AI chat opens | No errors | |
| 6.2 | Ask about current slate | References MLB slate | |
| 6.3 | Ask about specific player | Uses real data | |
| 6.4 | No hallucinated data | Admits when unavailable | |

---

## Phase 7 — Mobile UX

| # | Test | Expected | Status |
|---|------|----------|--------|
| 7.1 | Bottom tabs: Home, AI, Optimizer, Lineups, Profile | Clean layout | |
| 7.2 | Loading states | Spinner/indicator | |
| 7.3 | Error states | Clear message | |
| 7.4 | Build button disabled during load | No double-submit | |
| 7.5 | Slate selector filtered by platform | Correct | |
| 7.6 | Platform switch resets slate | No stale ID | |

---

## Phase 8 — Profile & Billing

| # | Test | Expected | Status |
|---|------|----------|--------|
| 8.1 | Plan shown: Elite Stack / Pro Arena / Free | Correct | |
| 8.2 | Role: admin for Founder | Admin | |
| 8.3 | Admin can generate 150 lineups | Not limited | |
| 8.4 | Free user limited to 1 lineup | Enforced | |

---

## Phase 9 — Production Safety

| # | Test | Expected | Status |
|---|------|----------|--------|
| 9.1 | No demo fallback in production | 503, not NBA_DEMO | |
| 9.2 | No synthetic ownership | N/A only | |
| 9.3 | No slate_id=0 path | Blocked at mobile | |
| 9.4 | No NBA default for MLB | 400 error | |
| 9.5 | Password not overwritten on deploy | Survives | |
| 9.6 | Secrets never in logs/response | Redacted | |

---

## Launch Gate

**PUBLIC LAUNCH BLOCKED** until:
- [ ] SportsDataIO unscrambled (LIVE_PRODUCTION) entitlement active
- [ ] Multi-lineup returns 3/3 for DK and FD
- [ ] All Phase checks PASS

**Technical readiness may precede data entitlement.**
