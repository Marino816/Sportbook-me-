# Phase 7D — SB-Me Builder Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `3016b47`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `8402689d001b` (head, 8th revision)

---

## 1. Platforms Supported

| Platform | Sport | Status |
|----------|-------|--------|
| DraftKings | NBA | Operational |
| FanDuel | NBA | Operational |
| NFL, MLB, others | — | Unsupported (returns clear error) |

### DraftKings NBA Rules
- Salary cap: $50,000
- Roster: 8 players (PG, SG, SF, PF, C, G, F, UTIL — flex-based)
- Max 4 players per team
- Player uniqueness enforced

### FanDuel NBA Rules
- Salary cap: $60,000
- Roster: 9 players (PG ×2, SG ×2, SF ×2, PF ×2, C ×1 — exact position slots)
- Max 4 players per team
- Player uniqueness enforced

## 2. Tables Created

| Table | Purpose |
|-------|---------|
| `builder_runs` | Optimization run metadata + constraints |
| `builder_lineups` | Individual lineup with explanation |
| `builder_portfolios` | Multi-lineup portfolio aggregates |
| `builder_exposure_rules` | Per-run exposure constraints |

## 3. Strategy Profiles (12)

All profiles have documented, sub-summable weights across 7 dimensions:
projection, ceiling, edge, ownership, leverage, risk, correlation.

| Strategy | Proj | Ceil | Edge | Own | Lev | Risk | Corr | Uniq |
|----------|------|------|------|-----|-----|------|------|------|
| Cash | 1.0 | 0.0 | 0.3 | 0.1 | 0.0 | 0.15 | 0.00 | 1 |
| Single Entry | 0.8 | 0.2 | 0.5 | 0.1 | 0.1 | 0.10 | 0.00 | 2 |
| Small GPP | 0.6 | 0.4 | 0.5 | 0.2 | 0.2 | 0.05 | 0.00 | 3 |
| Large GPP | 0.4 | 0.6 | 0.6 | 0.3 | 0.4 | 0.00 | 0.00 | 4 |
| 20-Max | 0.7 | 0.3 | 0.5 | 0.15 | 0.15 | 0.08 | 0.00 | 2 |
| 150-Max | 0.6 | 0.4 | 0.5 | 0.25 | 0.25 | 0.03 | 0.00 | 3 |
| Conservative | 1.0 | 0.0 | 0.3 | 0.0 | 0.0 | 0.25 | 0.00 | 1 |
| Balanced | 0.7 | 0.3 | 0.5 | 0.1 | 0.1 | 0.10 | 0.00 | 2 |
| Aggressive | 0.3 | 0.7 | 0.6 | 0.2 | 0.3 | 0.00 | 0.00 | 4 |
| Stars & Scrubs | 0.5 | 0.5 | 0.5 | 0.15 | 0.2 | 0.05 | 0.00 | 2 |
| Contrarian | 0.4 | 0.6 | 0.6 | 0.4 | 0.5 | 0.00 | 0.00 | 4 |
| High Correlation | 0.5 | 0.5 | 0.5 | 0.1 | 0.2 | 0.05 | 0.15 | 2 |

## 4. Objective Formula

```
Score per player = Σ(component_value × strategy_weight) + randomness_noise

Components:
  median_projection / 60.0     × projection_weight
  ceiling_projection / 70.0    × ceiling_weight
  edge_score / 100.0           × edge_weight
  (1.0 - ownership%)           × ownership_weight   (contrarian direction)
  leverage_score               × leverage_weight
  risk_score × -1              × risk_penalty
  correlation_bonus            × correlation_bonus

Randomness: bounded by |randomness| × 0.1
Reproducible: when randomness=0.0, identical inputs produce identical results.
Stars bonus: 10% projection/ceiling boost when salary > $9,000 (stars_and_scrubs).
Contrarian bonus: leverage boosted by (1.0 - ownership%) when prefer_contrarian=True.
```

## 5. API Endpoints

| Method | Endpoint | Auth | Tier |
|--------|----------|------|------|
| POST | `/builder/validate` | JWT | All |
| POST | `/builder/lineups` | JWT | Gated (platform-aware) |
| POST | `/builder/portfolios` | JWT | Pro+ |
| GET | `/builder/strategies` | JWT | All |
| GET | `/builder/runs/{id}` | JWT | All |
| GET | `/builder/portfolios/{id}` | JWT | All |
| POST | `/builder/rebuild/{id}` | JWT | All |

## 6. Entitlement

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Max lineups | 1 | 20 | 150 |
| Strategies | 3 (cash, balanced, conservative) | 12 | 12 |
| Portfolios | ✗ | ✓ | ✓ |
| DraftKings | ✓ | ✓ | ✓ |
| FanDuel | ✓ | ✓ | ✓ |

## 7. Exposure Engine

- Player exposure: % of lineups containing each player
- Team exposure: % of lineups containing each team
- Rule enforcement: min/max exposure violations flagged with actual values
- Unmet minimums reported clearly

## 8. Tests

| Suite | Count | Result |
|-------|-------|--------|
| Strategy profiles | 5 | Pass |
| DK validation | 7 | Pass |
| Exposure | 3 | Pass |
| Portfolio | 2 | Pass |
| Explanation | 1 | Pass |
| DK API | 10 | Pass |
| **DraftKings subtotal** | **28** | **All pass** |
| FD valid lineup | 1 | Pass |
| FD lineup count | 1 | Pass |
| FD platform validation | 1 | Pass |
| FD salary cap | 1 | Pass |
| FD roster size | 1 | Pass |
| FD lock/exclude | 1 | Pass |
| FD portfolio | 1 | Pass |
| FD free limit | 1 | Pass |
| FD pro limit | 1 | Pass |
| FD sport rejection | 1 | Pass |
| **FanDuel subtotal** | **10** | **All pass** |
| **Builder total** | **38** | **All pass** |

Cumulative: **192** (24+28+10+9+10+18+26+29+28+10)

## 9. Known Limitations

- Greedy algorithm works for demo pools; OR-Tools re-integration needed for production optimization
- Scout→Builder auto-invalidation not yet wired (manual refresh only)
- Stale-data marking exists but no cron-driven recheck
- FanDuel position slot enforcement uses cheap-fill, not position-optimal