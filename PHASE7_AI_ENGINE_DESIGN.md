# Phase 7 — AI Engine Design — Sportsbook Me DFS AI

**Date**: August 4, 2026
**Branch**: `feature/phase7-ai-engine`
**Status**: DESIGN — no code written yet

---

## 1. Existing System Audit

### What Exists

| Component | Current State | File |
|-----------|--------------|------|
| Sports models | Slate, Player, GameLog, Projection, Lineup, Matchup | `backend/models/domain.py` |
| Optimizer | NBA DraftKings only, single-sport, hardcoded constraints | `backend/optimizer/core.py` |
| Projections | projected_fp, ceiling, floor, ownership, leverage, value | `backend/models/domain.py:48` |
| Odds data | Unstructured odds_json on Matchup table | `backend/models/domain.py:106` |
| Sports API | POST /api/sports/lobby, demo fallback | `backend/api/sports.py` |
| Game logs | Fantasy points, minutes, raw stats_json | `backend/models/domain.py:38` |
| Backtesting | None — GameLog data unused for validation | — |
| AI providers | None — no LLM, ML, or inference integration | — |
| AI chat | None | — |
| Explanation | None | — |
| Personalization | None | — |
| Model versioning | None | — |

### What Is Missing

- Multi-sport support (NFL, MLB, MMA, golf, soccer, NHL)
- FanDuel optimizer constraints
- Model versioning and metadata
- Boom/bust probability
- Median projections (only floor/ceiling exist)
- Injury data and adjustment logic
- Line-movement tracking
- AI explanation generation
- Backtesting framework
- User preferences and personalization
- Alert system
- Audit logging
- Prompt injection defenses
- Rate limiting
- Cost monitoring

---

## 2. Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA INGESTION LAYER                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Sports    │ │ Odds      │ │ DFS Slate │ │ Injury    │       │
│  │ Data API  │ │ Data API  │ │ Provider  │ │ Data      │       │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        │             │             │             │               │
│  ┌─────┴─────────────┴─────────────┴─────────────┴─────┐       │
│  │               Data Normalization                    │       │
│  └─────────────────────────┬───────────────────────────┘       │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                     FEATURE ENGINEERING LAYER                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Sport     │ │ Position  │ │ Injury    │ │ Market    │       │
│  │ Features  │ │ Features  │ │ Adjust    │ │ Adjust    │       │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        └──────────────┴─────────────┴─────────────┘             │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                     PROJEC▶TION LAYER                            │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ NBA       │ │ NFL       │ │ MLB       │ │ MMA       │       │
│  │ Adapter   │ │ Adapter   │ │ Adapter   │ │ Adapter   │    ...│
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        │             │             │             │               │
│  ┌─────┴─────────────┴─────────────┴─────────────┴─────┐       │
│  │   Ownership  │ Correlation │ Confidence │ Model Ver │       │
│  └──────────────────────────────────────────────────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                     AI ENGINE LAYER                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Chat      │ │ Explain   │ │ Recommend │ │ Compare   │       │
│  │ Assistant │ │ Generator │ │ Engine    │ │ Engine    │       │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        └──────────────┴─────────────┴─────────────┘             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │             Security & Governance                         │   │
│  │  Prompt Injection │ Rate Limit │ Audit Log │ Model Ver    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Sports and League Inventory

Based on the existing repository structure and DFS market requirements:

| Sport | Leagues | DFS Platforms | Supported in Optimizer |
|-------|---------|---------------|----------------------|
| Basketball | NBA, WNBA, NCAA | DraftKings, FanDuel | NBA (DK only) |
| Football | NFL, NCAAF | DraftKings, FanDuel | No |
| Baseball | MLB | DraftKings, FanDuel | No |
| MMA | UFC | DraftKings, FanDuel | No |
| Golf | PGA | DraftKings, FanDuel | No |
| Hockey | NHL | DraftKings, FanDuel | No |
| Soccer | EPL, MLS, UCL | DraftKings, FanDuel | No |

**Phase 7 Priority**: NBA (already partially built) → NFL → MLB → MMA

---

## 4. Sport Adapter Architecture

Each sport adapter implements a common interface:

```python
class SportAdapter:
    sport: str                     # "nba", "nfl", "mlb", "mma"
    
    # Roster rules
    roster_slots: List[RosterSlot] # position requirements per platform
    salary_cap: int                # $50,000 for DK NBA
    
    # Feature engineering
    def build_features(game_logs, matchups, injuries) -> pd.DataFrame
    
    # Projection methodology
    def generate_projections(features, model_version) -> ProjectionOutput
    
    # Injury logic
    def apply_injury_adjustment(projection, injury_data) -> float
    
    # DFS scoring
    def calculate_fantasy_points(stats) -> float
    
    # Correlation logic
    def compute_correlation(player_a, player_b) -> float
    
    # Backtesting metrics
    def backtest_metrics(predictions, actuals) -> Dict
```

### NBA Adapter (existing → extended)
- Roster: PG, SG, SF, PF, C, G, F, UTIL (8 players, $50,000 cap)
- Scoring: PTS, 3PM, REB, AST, STL, BLK, TO
- Features: usage rate, pace, DvP, rest days, home/away

### NFL Adapter (new)
- Roster: QB, RB, RB, WR, WR, WR, TE, FLEX, DST (9 players, $50,000 cap)
- Scoring: passing/rushing/receiving yards, TDs, receptions, turnovers
- Features: target share, snap %, red zone touches, weather, defense rank

### MLB Adapter (new)
- Roster: P, P, C, 1B, 2B, 3B, SS, OF, OF, OF (10 players, $50,000 cap)
- Scoring: hits, runs, RBIs, HRs, SBs, IP, Ks, ER, wins, saves
- Features: platoon splits, park factor, pitch mix, bullpen usage

### MMA Adapter (new)
- Roster: 6 fighters, salary-based
- Scoring: significant strikes, takedowns, knockdowns, submission attempts, finish
- Features: striking differential, takedown accuracy, fight history, reach

---

## 5. Canonical Projection Output Schema

```python
class ProjectionOutput:
    # Identity
    entity_id: int                 # player_id or fighter_id
    entity_type: str               # "player" | "fighter" | "team"
    sport: str                     # "nba" | "nfl" | "mlb" | "mma"
    league: str                    # "NBA" | "NFL" | "MLB" | "UFC"
    
    # Event context
    event_id: Optional[int]        # matchup/game ID
    slate_id: Optional[int]        # DFS slate ID
    platform: str                  # "draftkings" | "fanduel"
    
    # Timestamps
    projection_date: datetime      # when projection was generated
    model_version: str             # "v1.2.3"
    data_timestamp: datetime       # when source data was retrieved
    
    # Core projections
    median_projection: float
    floor_projection: float
    ceiling_projection: float
    
    # Risk/reward
    boom_probability: float        # 0-1
    bust_probability: float        # 0-1
    
    # DFS metrics
    salary: int
    value_score: float             # projected_fp / (salary / 1000)
    matchup_score: float           # 0-100 matchup favorability
    ownership_projection: float    # estimated % ownership
    leverage_score: float          # ownership value
    
    # Adjustments
    injury_adjustment: float       # multiplier applied (-1 to 0)
    market_adjustment: float       # vegas-implied adjustment
    
    # Confidence
    confidence_score: float        # 0-1 model confidence
    
    # Explanation
    explanation: str               # human-readable rationale
    input_sources: List[str]       # ["game_logs", "odds_api", "injury_report"]
    
    # Data quality flags
    missing_data_flags: List[str]  # ["no_injury_data"]
    stale_data_flag: bool          # data older than threshold
```

---

## 6. AI Assistant Design

### Architecture

```
User message → Input Validation → Prompt Injection Check
    → Tool Selection (which data to fetch)
    → Data Retrieval (sports DB, projections, odds)
    → Context Assembly (sport, slate, user prefs)
    → LLM Call (provider-agnostic)
    → Response Validation (no injected code, data-only responses)
    → Audit Logging → Response
```

### Tool Allowlist

The assistant may ONLY call these internal tool types:
- `get_slate_data(slate_id)` — current slate players and projections
- `get_player_stats(player_id, days=30)` — recent game logs
- `get_matchup(matchup_id)` — current odds and status
- `get_user_preferences(user_id)` — personalized settings
- `get_model_status()` — active model versions
- `get_team_stats(team, sport, days=30)` — team-level data
- `get_injury_report(slate_id)` — current injuries

### Prompt Injection Defenses

- System prompt pinned at top of context, cannot be overwritten
- User input wrapped with `<user_message>` tags, separated from tool data
- Tool output wrapped with `<tool_output source="...">` tags
- No user input directly interpolated into system instructions
- Regex-based detection of: SQL injection, shell commands, URL injection, role-override patterns
- Max input length: 4000 characters
- Reject messages containing: `</system>`, `<|im_start|>`, `[INST]`, `system:`, `### Instruction`

### Response Quality Requirements

Every AI response MUST include at minimum:
- Data timestamp: when was the source data retrieved
- Model version: which projection model produced the numbers
- Confidence: 0-100 score where applicable
- Data warnings: missing or stale data flags
- Clear separation: "Projection" vs "Fact" vs "Market data"

---

## 7. Database Design

### New Tables

```
ai_models
├── id, name, sport, model_type, is_active, created_at

ai_model_versions
├── id, model_id, version, parameters_json, training_data_range,
│   metrics_json, deployed_at, is_active

ai_predictions
├── id, model_version_id, entity_id, entity_type, sport, slate_id,
│   projection_json, confidence, created_at

ai_prediction_inputs
├── id, prediction_id, input_type, input_value, source, timestamp

ai_explanations
├── id, prediction_id, explanation_text, factors_json,
│   model_version, created_at

ai_user_preferences
├── id, user_id (unique), favorite_sports, favorite_teams,
│   favorite_players, preferred_platform, contest_type,
│   strategy, num_lineups, preferred_stacks, max_salary_pct,
│   locked_players, excluded_players, max_exposure, updated_at

ai_conversations
├── id, user_id, session_id, role, content, tool_calls_json,
│   data_sources_json, model_version, tokens_used, cost,
│   feedback, created_at

ai_recommendations
├── id, user_id, slate_id, recommendation_type, lineup_json,
│   reasoning, strategy, model_version, created_at

ai_feedback
├── id, prediction_id, user_id, rating, comment, created_at

ai_backtests
├── id, model_version_id, sport, league, date_range_start,
│   date_range_end, metrics_json, status, created_at

ai_model_metrics
├── id, model_version_id, metric_name, metric_value, sport,
│   position, salary_tier, confidence_bucket, calculated_at

ai_alerts
├── id, user_id, alert_type, sport, entity_id, condition,
│   is_active, last_triggered_at, created_at

ai_audit_logs
├── id, user_id, action, endpoint, input_hash, response_hash,
│   tokens_used, cost, latency_ms, success, error, created_at
```

---

## 8. API Design

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/ai/chat` | All tiers | AI assistant conversation |
| GET | `/api/ai/slates/{id}/summary` | All | Daily slate AI summary |
| GET | `/api/ai/matchups/{id}` | Pro+ | AI matchup analysis |
| GET | `/api/ai/projections/{slate_id}` | Pro+ | AI-enhanced projections |
| GET | `/api/ai/players/{id}/explanation` | Pro+ | Why this projection |
| POST | `/api/ai/compare` | Pro+ | Player/team comparison |
| POST | `/api/ai/lineups` | Pro+ | AI lineup generation |
| POST | `/api/ai/recommendations` | Elite | AI recommendations |
| GET | `/api/ai/model-status` | Admin | Active model versions |
| POST | `/api/ai/feedback` | All | Rate a prediction |
| GET | `/api/ai/backtests` | Elite | View backtest results |
| GET | `/api/ai/alerts` | All | View/create alerts |

### Feature Gating

```python
AI_FEATURE_GATING = {
    "free": {
        "chat_messages_per_day": 10,
        "slate_summary": True,
        "matchup_basic": True,
        "projections": 5,
        "lineups_per_day": 1,
    },
    "pro_arena": {
        "chat_messages_per_day": 100,
        "slate_summary": True,
        "matchup_full": True,
        "projections": "unlimited",
        "lineups_per_day": 20,
        "ai_explanations": True,
        "ai_recommendations": True,
        "injury_impact": True,
        "saved_preferences": True,
    },
    "elite_stack": {
        "chat_messages_per_day": "unlimited",
        "lineups_per_day": 150,
        "ownership_leverage": True,
        "boom_bust_analysis": True,
        "multi_lineup_generation": True,
        "exposure_controls": True,
        "advanced_backtesting": True,
        "personalized_alerts": True,
        "tournament_strategy": True,
        "full_assistant_access": True,
    },
}
```

---

## 9. Security Design

| Layer | Mechanism |
|-------|-----------|
| Authentication | JWT Bearer required for personalized AI |
| Subscription | Backend check on every AI endpoint |
| Input validation | Pydantic models, max 4000 chars chat input |
| Prompt injection | Regex filter, structured context wrapping |
| Tool allowlist | AI can only call approved internal functions |
| Data-source allowlist | Only internal DB, approved APIs |
| Rate limiting | Per-user: 10/min free, 100/min pro, 500/min elite |
| Cost monitoring | Track tokens per request, alert on overage |
| Model timeout | 30s timeout on LLM calls, 60s on lineups |
| Audit logging | Every AI request logged with hash, tokens, cost |
| No secrets | Never include API keys in prompts or responses |
| No code exec | AI output never executed as code or SQL |
| No external URLs | AI cannot generate or follow external links |

---

## 10. Testing Plan

### Unit Tests
- Sport adapter contract tests (one per sport)
- Projection schema validation
- Feature engineering output shape
- Injury adjustment calculation
- Confidence score bounds (0-1)
- Prompt injection filter tests (20+ patterns)
- Rate limiter behavior
- Subscription gating logic

### API Tests
- All 12 endpoints return correct schemas
- Free tier gets rate-limited at thresholds
- Pro tier gets full access
- Unauthenticated requests return 401
- Non-subscribed users blocked from premium endpoints

### Projection Tests
- Schema has all 25+ required fields
- timestamp fields are timezone-aware
- model_version matches active deployment
- missing_data_flags populated when inputs unavailable
- stale_data_flag true when data older than threshold

### Integration Tests
- AI chat → tool call → data retrieval → response
- Projection generation → optimizer → lineup validation
- User preference → personalized recommendation
- Backtest run → metrics calculation → audit log

---

## 11. Implementation Phases

### Phase 7A — Foundation (this branch)
- Database tables and migrations
- Projection output schema
- Sport adapter interface + NBA adapter
- Model versioning
- Backtesting framework
- Unit tests

### Phase 7B — AI Engine
- AI provider abstraction (OpenAI/Claude/Deepseek)
- Chat assistant with tool calling
- Explanation generator
- Comparison engine
- Prompt injection defenses
- Rate limiting
- Audit logging

### Phase 7C — Personalization + Gating
- User preferences CRUD
- Subscription gating on all AI endpoints
- Saved lineups and recommendations
- Alerts system
- Feedback collection

### Phase 7D — Expansion
- NFL adapter
- MLB adapter
- MMA adapter
- FanDuel optimizer constraints
- Backtesting dashboards

---

## 12. Deployment Plan

1. Create feature/phase7-ai-engine from hermes-production-build
2. Implement Phase 7A → merge to hermes-production-build
3. Implement Phase 7B → merge to hermes-production-build
4. Implement Phase 7C → merge to hermes-production-build
5. Railway migration at each merge
6. Smoke tests against staging
7. v1.2-beta tag after Phase 7C complete

---

## 13. Cost-Control Plan

- Track tokens per request in ai_audit_logs
- Daily budget: $50 (alert at $40)
- Provider fallback: Deepseek (cheapest) → Claude Haiku → GPT-4o-mini
- Cache repeated explanations (same player/slate/model_version)
- Rate limit by subscription tier
- Admin dashboard shows daily spend

---

## 14. Risks and Blockers

| Risk | Mitigation |
|------|-----------|
| No live sports data | Demo fallback already exists in get_slate_projections |
| LLM costs unpredictable | Token tracking + daily budget + cached explanations |
| Multi-sport complexity | Start NBA-only, add sports one at a time |
| Prompt injection | Structured context wrapping + regex guard |
| User data privacy | Hash inputs in audit log, no PII in prompts |

---

## 15. Manual Owner Actions

1. Choose primary AI provider (OpenRouter recommended for multi-model access)
2. Set AI provider API key in Railway env vars
3. Provision live sports data API (BallDontLie, The Odds API, or similar)
4. Create initial admin user with AI model management access

---

## 16. Acceptance Criteria

- [ ] NBA adapter generates valid projection output schema
- [ ] AI assistant answers "Who should I play at PG tonight?" using real slate data
- [ ] Free user blocked at 10 chat messages
- [ ] Pro user gets full projection access
- [ ] Prompt injection attacks rejected
- [ ] All 12 API endpoints return typed responses
- [ ] Audit log records every AI request
- [ ] Backtest generates MAE, RMSE, calibration metrics
- [ ] Model version tracked in every response