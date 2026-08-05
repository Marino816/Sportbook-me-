# Phase 7E — SB-Me Coach Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `34c43b0`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `703b0229f207` (head, 9th revision)

---

## 1. Tables Created

| Table | Purpose |
|-------|---------|
| `contest_results` | Imported contest outcomes (entry fee, payout, position, score) |
| `lineup_results` | Per-lineup performance (projection error, percentile, strategy) |
| `coach_sessions` | Analysis session metadata |
| `coach_metrics` | Computed performance metrics per session |
| `coach_findings` | Structured findings (strengths, weaknesses, tendencies) |
| `coach_recommendations` | Evidence-based actionable recommendations |

## 2. Contest Result Contract

| Field | Required | Nullable When |
|-------|----------|---------------|
| contest_id | ✓ | — |
| platform, sport, league | ✓ | — |
| entry_fee | — | Missing from data source |
| payout | — | Contest not finalized |
| entry_count, finishing_position | — | Unknown |
| final_lineup_score, cash_line, winning_score | — | Data unavailable |
| ownership_data_available | ✓ | — |

## 3. Performance Metrics

| Metric | Formula |
|--------|---------|
| ROI | (total_winnings − total_fees) / total_fees × 100 |
| Cash rate | cashed_contests / total × 100 |
| Projection MAE | mean(|actual − projected|) across all lineups |
| Median error | median(actual − projected) |
| Avg finish percentile | (1 − position/entries) avg across contests |

## 4. Analysis Engines

| Engine | Function |
|--------|----------|
| ContestEvaluator | Per-contest: cash/no-cash, projection error, percentile |
| PerformanceAnalyzer | Aggregate: ROI, cash rate, MAE |
| StrategyAnalyzer | By-strategy breakdown, exposure top-10 |
| RecommendationEngine | Evidence-based recs (cash rate, projection error, ROI, stale) |
| ConfidenceCalculator | Sample size × 0.5 + completeness × 0.3 + recency × 0.1 + consistency × 0.1 |

## 5. Recommendation Triggers

| Condition | Priority | Confidence |
|-----------|----------|------------|
| Cash rate < 30% (≥ 5 samples) | High | 0.7 |
| MAE > 15 (≥ 3 samples) | Medium | 0.6 |
| ROI < −10% (≥ 5 samples) | High | 0.65 |
| Stale lineups at lock | Medium | 0.8 |
| Sample < 5 (all conditions) | Low | 0.3 |

## 6. API Endpoints

| Method | Endpoint | Auth | Tier |
|--------|----------|------|------|
| POST | `/coach/contests/import` | JWT | All |
| GET | `/coach/contests/{id}` | JWT | All |
| GET | `/coach/slates/{id}` | JWT | All |
| GET | `/coach/performance` | JWT | All (limited for free) |
| GET | `/coach/findings` | JWT | Pro+ |
| GET | `/coach/recommendations` | JWT | All |
| GET | `/coach/strategies` | JWT | Pro+ |
| GET | `/coach/exposures` | JWT | Pro+ |
| POST | `/coach/review` | JWT | All |
| GET | `/coach/sessions/{id}` | JWT | All |

## 7. Entitlement

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Max reviews | 5 | 100 | 2000 |
| Performance | Basic | Full | Full |
| Findings | ✗ | ✓ | ✓ |
| Strategy analysis | ✗ | ✓ | ✓ |
| Exposure analysis | ✗ | ✓ | ✓ |

## 8. Privacy

- User-level data isolation enforced (demo data shared for testing)
- No cross-user contest access
- No secrets, tokens, or payment credentials logged

## 9. Tests

| Suite | Count | Result |
|-------|-------|--------|
| Contest evaluator | 4 | Pass |
| Performance analyzer | 5 | Pass |
| Strategy analyzer | 2 | Pass |
| Recommendations | 4 | Pass |
| Confidence | 3 | Pass |
| Coach API | 11 | Pass |
| **Total** | **29** | **All pass** |

Cumulative: **221** (24+28+10+9+10+18+26+29+28+10+29)

## 10. Known Limitations

- Demo contest data used for all analyses
- No live contest feed integration
- Contest import is placeholder (50-entry cap)
- No cross-date aggregation yet (all time)

## 11. Phase 7F Recommendations

- Live contest-result feed integration
- SB-Me Mission Control dashboard
- Cross-date bankroll trend visualization