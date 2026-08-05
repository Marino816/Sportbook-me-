# Phase 7C — SB-Me Analyst Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `e7dd959`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `605191c0ba9c` (head, 7th revision)

---

## 1. Tables Created

| Table | Rows/Insight | Purpose |
|-------|-------------|---------|
| `analyst_insights` | 1 | Structured analysis output (25+ fields) |
| `analyst_factors` | N | Decomposed factor instances per insight |
| `analyst_risks` | N | Identified risk factors per insight |

## 2. Insight Schemas

| Schema | Fields | Nullable Fields |
|--------|--------|-----------------|
| `PlayerInsightResponse` | 27 | edge_score, event_id, slate_id |
| `GameInsightResponse` | 31 | home_team, away_team, spread, total |
| `SlateInsightResponse` | 11 | — |
| `ProjectionChangeResponse` | 12 | previous_projection, absolute_change, percentage_change |
| `TopEdgesResponse` | 5 | — |

## 3. Matchup Methodology

16 NBA factors supported:

| Factor | Source | Nullable |
|--------|--------|----------|
| pace | Team data | ✓ |
| offensive_efficiency | Team data | ✓ |
| defensive_efficiency | Team data | ✓ |
| position_defense | Matchup data | ✓ |
| rebounding | Team data | ✓ |
| turnover_rate | Team data | ✓ |
| usage | Player data | ✓ |
| minutes | Player data | ✓ |
| recent_form | Game logs | ✓ |
| home_away_split | Schedule | ✓ |
| rest_days | Schedule | ✓ |
| injury_status | Injury feed | ✓ |
| vegas_total | Odds API | ✓ |
| spread | Odds API | ✓ |
| line_movement | Odds API | ✓ |
| starting_confirmed | Lineups | ✓ |

Missing factors are tracked in `missing_data_flags`. No factor is fabricated.

## 4. Projection-Change Methodology

| Metric | Formula |
|--------|---------|
| Absolute change | current − previous |
| Percentage change | (absolute / max(|previous|, 0.1)) × 100 |
| Optimizer refresh | Triggered when |Δ| > 3.0 or |%| > 10 |
| Previous unavailable | All change fields set to None |

## 5. Risk Methodology

10 risk types with deterministic weights:

| Risk | Weight | Trigger |
|------|--------|---------|
| blowout_risk | 0.10 | (not triggered in demo) |
| minutes_uncertainty | 0.12 | avg minutes < 20 |
| injury_uncertainty | 0.15 | injury ≠ Healthy/Probable |
| starting_uncertainty | 0.10 | starter ≠ Confirmed/Probable |
| ownership_risk | 0.08 | (not triggered in demo) |
| small_sample | 0.10 | games < 5 |
| stale_data | 0.10 | is_stale flag |
| missing_market_data | 0.08 | salary/odds missing |
| high_volatility | 0.12 | recent vs avg FP > 30% diff |
| role_instability | 0.05 | (not triggered in demo) |

Aggregate score: weighted sum of severities, capped at 1.0.

## 6. SB-Me Edge Formula

```
Edge = 30 × projection_strength
     + 20 × matchup_quality
     + 15 × market_alignment
     + 10 × ownership_leverage
     + 15 × data_quality
     +  5 × confidence
     −  5 × risk_penalty (0.05 per risk, max 0.25)
```

Score capped at 0–100.

Tiers:
- 85–100: Elite Edge
- 70–84: Strong Edge
- 55–69: Solid Edge
- 40–54: Neutral
- < 40: Low Confidence

## 7. API Endpoints

| Method | Endpoint | Auth | Tier |
|--------|----------|------|------|
| GET | `/analyst/player/{id}` | JWT | All (gated) |
| GET | `/analyst/game/{id}` | JWT | All |
| GET | `/analyst/slate/{id}` | JWT | All |
| GET | `/analyst/projection-change/{entity_id}` | JWT | All |
| GET | `/analyst/top-edges` | JWT | Pro+ |
| GET | `/analyst/risks` | JWT | Pro+ |

## 8. Scout Integration

- Analyst endpoints accept Scout event IDs as source_event_ids
- ProjectionChangeAnalyzer includes triggering_events list
- Future: auto-trigger on Scout event detection

## 9. Entitlement Rules

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Daily insights | 10 | 200 | 2000 |
| Full analysis | ✗ | ✓ | ✓ |
| Edge scores | ✗ | ✓ | ✓ |
| Risk details | ✗ | ✓ | ✓ |

## 10. Tests

| Suite | Count | Result |
|-------|-------|--------|
| Matchup engine | 3 | Pass |
| Risk engine | 7 | Pass |
| Edge engine | 4 | Pass |
| Projection change | 3 | Pass |
| Confidence | 3 | Pass |
| Analyst API | 9 | Pass |
| **Total** | **29** | **All pass** |

Cumulative: **154** (24+28+10+9+10+18+26+29)

## 11. Known Limitations

- All analysis uses demo/placeholder data
- No historical backtesting of Edge scores yet
- Scout event auto-trigger is not yet wired

## 12. Phase 7D Recommendations

- Wire Scout event detection → auto Analyst insight generation
- Add backtesting validation for Edge scores
- NFL + MLB adapters
- Mission Control frontend dashboard