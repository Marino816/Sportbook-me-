# Phase 7G — SB-Me AI Assistant Results — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Commit**: `49c20ef`
**Branch**: `feature/phase7-ai-engine`
**Migration**: `3652a3cd5d8d` (head, 11th revision)

---

## 1. Tool Architecture

| Component | Function |
|-----------|----------|
| IntentClassifier | Maps user text to 10 intents via keyword matching |
| ToolRouter | Intents → Scout/Analyst/Builder/Coach/Mission Control modules |
| StrategyModeEngine | 5 strategy modes with weight shifts |
| ResponseComposer | Structured output: task, evidence, recommendation, confidence |

The assistant never generates sports intelligence independently.
All analysis routes through existing intelligence modules.

## 2. Intent Catalog

| Intent | Keywords | Modules |
|--------|----------|---------|
| build_lineups | build, lineup, generate, optimize, portfolio | builder, coach |
| explain_projections | explain, why projected, projection explanation | analyst, ai_engine |
| injury_news | injury, hurt, out, questionable, status | scout, analyst |
| matchup_analysis | matchup, vs, against, opponent, pace | analyst, scout |
| contest_performance | performance, roi, cash rate, results, profit | coach |
| portfolio_review | portfolio, exposure, diversification | builder, coach |
| mission_control | dashboard, briefing, summary, overview | mission_control |
| system_health | health, status, providers, freshness | mission_control, scout |
| strategy_advice | strategy, recommend, advice, suggest | coach, builder |
| general | fallback | mission_control, analyst |

## 3. Strategy Modes

| Mode | Description | Proj Shift | Ceil Shift | Risk Shift |
|------|------------|------------|------------|------------|
| Cash | Safety-first, 60%+ cash rate target | +0.2 | −0.2 | +0.15 |
| Tournament | High-ceiling, leverage-heavy | −0.2 | +0.3 | −0.1 |
| Single Entry | Balanced single-entry | 0.0 | 0.0 | +0.05 |
| Nuclear | Maximum ceiling, high variance | −0.3 | +0.4 | −0.2 |
| Bankroll | Bankroll-preserving | +0.15 | −0.3 | +0.2 |

Underlying projections are never modified. Weight shifts apply only to recommendations.

## 4. Database Tables

| Table | Purpose |
|-------|---------|
| `assistant_conversations` | Per-user conversation sessions |
| `assistant_messages` | Individual messages with intent, modules, evidence |
| `assistant_preferences` | User default sport, platform, strategy, favorites |

## 5. API Endpoints

| Method | Endpoint | Auth | Notes |
|--------|----------|------|-------|
| POST | `/assistant/chat` | JWT | Intent routing + response |
| GET | `/assistant/strategy-modes` | JWT | Tier-filtered |
| POST | `/assistant/strategy-mode` | JWT | Set active mode |
| GET | `/assistant/war-room` | JWT | Pro+ only |
| GET | `/assistant/conversations` | JWT | List conversations |
| GET | `/assistant/conversations/{id}` | JWT | Message history |
| POST | `/assistant/preferences` | JWT | Save preferences |
| GET | `/assistant/preferences` | JWT | Get preferences |

## 6. Entitlement

| Feature | Free | Pro Arena | Elite Stack |
|---------|------|-----------|-------------|
| Daily requests | 20 | 200 | 2000 |
| Strategy modes | 2 | 5 | 5 |
| War Room | ✗ | ✓ | ✓ |

## 7. Security

- No prompt or secret logging
- No arbitrary code execution from user text
- Input validation on all endpoints
- Rate limiting per user per day
- Audit logging via existing ai_audit_logs

## 8. Tests

| Suite | Count | Result |
|-------|-------|--------|
| Intent classifier | 6 | Pass |
| Tool router | 4 | Pass |
| Strategy modes | 3 | Pass |
| Response composer | 2 | Pass |
| Assistant API | 9 | Pass |
| **Total** | **24** | **All pass** |

Cumulative: **263** across 12 suites

## 9. Complete Phase 7 Stack

| Phase | Module | Tests | Tables | Migration |
|-------|--------|-------|--------|-----------|
| 7A | AI Engine | 28 | 6 | d5835ac224eb |
| 7B | Scout | 26 | 3 | f7f78e663688 |
| 7C | Analyst | 29 | 3 | 605191c0ba9c |
| 7D | Builder | 38 | 4 | 8402689d001b |
| 7E | Coach | 29 | 6 | 703b0229f207 |
| 7F | Mission Control | 18 | 3 | 6da32956dfb8 |
| 7G | AI Assistant | 24 | 3 | 3652a3cd5d8d |
| **Total** | | **263** | **43** | **11** |

## 10. Known Limitations

- Intent classification is keyword-based (no NLP/LLM)
- Strategy modes shift weights but don't dynamically re-select from Coach data
- War Room is snapshot-based (no real-time push)
- No multi-turn conversation persistence in demo data

## 11. Phase 7X Recommendations

- NLP-based intent classifier
- LLM-powered explanation generation
- Real-time WebSocket War Room
- Cross-module recommendation synthesis