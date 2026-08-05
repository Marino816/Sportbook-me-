# Phase 7A — AI Engine Foundation Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `1a67504`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `d5835ac224eb` (head, 5th revision)

---

## 1. Sports Inventory

| Sport | Status | Evidence |
|-------|--------|----------|
| NBA | **Partial** | Optimizer exists. NBA adapter implemented in Phase 7A. |
| NFL | Placeholder | Frontend UI only. No backend adapter. |
| MLB | Placeholder | Frontend UI only. No backend adapter. |
| NHL | Placeholder | Frontend UI only. No backend adapter. |
| PGA | Placeholder | Frontend UI only. No backend adapter. |
| UFC | Placeholder | Frontend UI only. No backend adapter. |
| Soccer | Placeholder | Frontend UI only. No backend adapter. |
| NCAA Basketball | Unsupported | Not in repository. |
| NCAA Football | Unsupported | Not in repository. |

---

## 2. Tables Created

| Table | Purpose |
|-------|---------|
| `ai_models` | Model registry (name, sport, type) |
| `ai_model_versions` | Versioned model metadata |
| `ai_predictions` | Canonical projection output (25 columns) |
| `ai_prediction_inputs` | Input provenance for each prediction |
| `ai_explanations` | Structured explanation text + factors |
| `ai_audit_logs` | Hashed request/response audit trail |

All DateTime columns use `timezone=True`.

---

## 3. Migration

| Field | Value |
|-------|-------|
| Revision | `d5835ac224eb` |
| Down revision | `df12511b7d71` |
| Tables created | 6 |
| Upgrade tested | SQL generation passes |
| Downgrade tested | SQL generation passes |

---

## 4. Projection Schema

The canonical `ProjectionResponse` contains 28 fields:

- 10 identity/context fields (entity_id, entity_type, sport, league, etc.)
- 12 projection/metrics fields (median, floor, ceiling, boom, bust, value, etc.)
- 6 metadata fields (confidence, explanation, sources, missing_data, stale)

All nullable fields return `None` when data is unavailable (never fabricated).

---

## 5. NBA Adapter Methodology

The NBA adapter uses deterministic formulas:

| Method | Formula |
|--------|---------|
| Projection | Base from projected_fp or 5-game average |
| Floor | median - 0.5 * |median - avg| |
| Ceiling | median + 0.5 * |median - avg| |
| Value | projected_fp / (salary / 1000) |
| Matchup | 100 - opponent_def_rating (if available) |
| Boom/Bust | None (requires historical variance — Phase 7B+) |
| Confidence | 1.0 − deductions for missing data, staleness, unknown status |

---

## 6. Confidence Methodology

Deterministic rules:

| Factor | Deduction |
|--------|-----------|
| Base | 1.00 |
| Per missing optional field | −0.05 |
| Missing salary | −0.15 |
| Missing position | −0.15 |
| Stale data | −0.20 |
| Unknown injury status | −0.05 |
| Unknown starting status | −0.05 |
| No game logs (insufficient sample) | −0.10 |
| **Minimum** | **0.10** |

---

## 7. Freshness Methodology

- `stale_data_flag` set when input data timestamp exceeds `STALE_THRESHOLD_HOURS` (4 hours)
- `missing_data_flags` lists every optional field that is absent or NaN
- `input_sources` tracks which data providers contributed

---

## 8. API Endpoints

| Method | Endpoint | Auth | Tier | Status |
|--------|----------|------|------|--------|
| GET | `/ai/model-status` | JWT | All | Implemented |
| GET | `/ai/projections?slate_id=&sport=&platform=` | JWT | Gated | Implemented |
| GET | `/ai/players/{id}/explanation?slate_id=` | JWT | Pro+ | Implemented |

---

## 9. Entitlement Rules

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Projections/day | 5 | 500 | 10000 |
| Full explanations | ✗ | ✓ | ✓ |
| Advanced metrics | ✗ | ✓ | ✓ |
| Rate limit code | 429 | n/a | n/a |

Backend enforced via `FEATURE_GATING` dict + `_check_rate()` with in-memory counter.

---

## 10. Tests

| Suite | Tests | Result |
|-------|-------|--------|
| test_ai_engine.py | 28 | All pass |
| test_auth.py | 24 | All pass |
| test_billing.py | 10 | All pass |
| test_optimizer.py | 9 | All pass |
| test_rbac.py | 10 | All pass |
| test_smoke.py | 18 | All pass |
| **Total** | **99** | **All pass** |

TypeScript: Clean
Next.js build: Passes

---

## 11. Known Limitations

1. Boom/bust probability returns None — requires historical variance data not yet available
2. Ownership projection returns None — requires ownership model (Phase 7B+)
3. Leverage score returns None — requires ownership data
4. Injury/market adjustments return None — requires injury and odds data feeds
5. Rate limit counter is in-memory (per-process) — production needs Redis
6. Deterministic-only explanation layer — no LLM chat yet
7. NBA adapter only — other sports raise UnsupportedSportError

---

## 12. Phase 7B Recommendations

1. Add AI provider integration (OpenRouter/Claude/Deepseek)
2. Implement chat endpoint with tool calling
3. Add NFL, MLB adapters
4. Add boom/bust calculation with historical variance
5. Add ownership projection model
6. Add Redis-backed rate limiting
7. Implement ai_conversations, ai_user_preferences, ai_recommendations tables