# Phase 7D — SB-Me Builder Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `c72c79c`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `8402689d001b` (head, 8th revision)

---

## 1. Platforms Supported

| Platform | Sport | Status |
|----------|-------|--------|
| DraftKings | NBA | Operational |
| FanDuel | NBA | Rules implemented, not yet wired to separate optimizer |
| NFL, MLB, others | — | Unsupported (returns clear error) |

## 2. Tables Created

| Table | Purpose |
|-------|---------|
| `builder_runs` | Optimization run metadata + constraints |
| `builder_lineups` | Individual lineup with explanation |
| `builder_portfolios` | Multi-lineup portfolio aggregates |
| `builder_exposure_rules` | Per-run exposure constraints |

## 3. Strategy Profiles (12)

| Strategy | Projection | Ceiling | Edge | Ownership | Levee | Risk | Uniqueness |
|----------|-----------|---------|------|-----------|-------|------|------------|
| Cash | 1.0 | 0.0 | 0.3 | 0.1 | 0.0 | 0.15 | 1 |
| Single Entry | 0.8 | 0.2 | 0.5 | 0.1 | 0.1 | 0.10 | 2 |
| Small GPP | 0.6 | 0.4 | 0.5 | 0.2 | 0.2 | 0.05 | 3 |
| Large GPP | 0.4 | 0.6 | 0.6 | 0.3 | 0.4 | 0.00 | 4 |
| 20-Max | 0.7 | 0.3 | 0.5 | 0.15 | 0.15 | 0.08 | 2 |
| 150-Max | 0.6 | 0.4 | 0.5 | 0.25 | 0.25 | 0.03 | 3 |
| Conservative | 1.0 | 0.0 | 0.3 | 0.0 | 0.0 | 0.25 | 1 |
| Balanced | 0.7 | 0.3 | 0.5 | 0.1 | 0.1 | 0.10 | 2 |
| Aggressive | 0.3 | 0.7 | 0.6 | 0.2 | 0.3 | 0.00 | 4 |
| Stars & Scrubs | 0.5 | 0.5 | 0.5 | 0.15 | 0.2 | 0.05 | 2 |
| Contrarian | 0.4 | 0.6 | 0.6 | 0.4 | 0.5 | 0.00 | 4 |
| High Correlation | 0.5 | 0.5 | 0.5 | 0.1 | 0.2 | 0.05 | 2 |

## 4. Objective Formula

```
Score = 0.30 × proj + 0.20 × ceil + 0.15 × edge + 0.10 × ownership_inverse
      + 0.10 × leverage + 0.05 × confidence − 0.10 × risk
      + randomness (optional)
```

Weights vary by strategy profile. Contrarian bonus: leverage boosted when ownership is low. Stars bonus: 10% boost when salary > $9,000.

## 5. DraftKings NBA Rules

- Salary cap: $50,000
- Roster: 8 players (PG, SG, SF, PF, C, G, F, UTIL)
- Max 4 players per team
- No duplicate players
- Lock/exclude validation

## 6. Exposure Engine

| Metric | Calculation |
|--------|------------|
| Player exposure | % of lineups containing player |
| Team exposure | % of lineups containing team |
| Rule checking | Min/max exposure violation detection |

## 7. API Endpoints

| Method | Endpoint | Auth | Tier |
|--------|----------|------|------|
| POST | `/builder/validate` | JWT | All |
| POST | `/builder/lineups` | JWT | Gated |
| POST | `/builder/portfolios` | JWT | Pro+ |
| GET | `/builder/strategies` | JWT | All |
| GET | `/builder/runs/{id}` | JWT | All |
| GET | `/builder/portfolios/{id}` | JWT | All |
| POST | `/builder/rebuild/{id}` | JWT | All |

## 8. Entitlement

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Max lineups | 1 | 20 | 150 |
| Strategies | 3 | 12 | 12 |
| Portfolios | ✗ | ✓ | ✓ |
| Exposure | ✗ | ✓ | ✓ |

## 9. Tests

| Suite | Count | Result |
|-------|-------|--------|
| Strategy profiles | 5 | Pass |
| Validation | 7 | Pass |
| Exposure | 3 | Pass |
| Portfolio | 2 | Pass |
| Explanation | 1 | Pass |
| Builder API | 10 | Pass |
| **Total** | **28** | **All pass** |

Cumulative: **182** (24+28+10+9+10+18+26+29+28)

## 10. Known Limitations

- FanDuel uses DraftKings rules in validation (separate optimizer not wired)
- Greedy algorithm prioritizes cheap-fill over strategy-weighted optimization
- No OR-Tools optimizer integration (standalone greedy for Phase 7D)

## 11. Phase 7E Recommendations

- Wire OR-Tools optimizer for optimal strategy-weighted lineups
- Separate FanDuel optimizer with FD roster rules
- NFL + MLB adapters