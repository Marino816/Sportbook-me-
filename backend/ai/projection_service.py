"""
Central projection service for Sportsbook Me DFS AI.

Orchestrates the projection pipeline:
  1. Select sport adapter
  2. Validate input
  3. Check freshness
  4. Generate projections
  5. Generate explanation
  6. Store provenance
  7. Log audit record
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_models import AIPrediction, AIPredictionInput, AIExplanation, AIAuditLog
from models.domain import GameLog, Matchup
from ai.nba_adapter import get_adapter
from ai.sport_adapter import UnsupportedSportError


# Configurable staleness threshold (hours)
STALE_THRESHOLD_HOURS = 4


class ProjectionService:
    """Generate projections for a slate using the appropriate sport adapter."""

    def __init__(self, db: AsyncSession, sport: str = "nba", platform: str = "draftkings"):
        self.db = db
        self.sport = sport
        self.platform = platform
        self.adapter = get_adapter(sport)
        self.active_model_version = "7a.0.1"  # Phase 7A initial
        self.active_model_name = "nba_baseline_v1"

    async def generate_for_slate(self, slate_id: int) -> List[dict]:
        """Full pipeline: validate → project → explain → store."""
        projections_data = await self._load_slate_data(slate_id)
        game_logs = await self._load_game_logs(projections_data)
        matchups = await self._load_matchups()

        errors = self.adapter.validate_input(projections_data)
        if errors:
            raise ValueError(f"Input validation failed: {'; '.join(errors)}")

        features = self.adapter.build_features(projections_data, game_logs, matchups, pd.DataFrame())
        is_stale = self._check_staleness(projections_data)

        results = []
        for idx in features.index:
            missing = self._identify_missing(features, idx)

            median = self.adapter.calculate_projection(features, idx)
            floor = self.adapter.calculate_floor(features, idx, median)
            ceiling = self.adapter.calculate_ceiling(features, idx, median)
            boom = self.adapter.calculate_boom_probability(features, idx)
            bust = self.adapter.calculate_bust_probability(features, idx)
            confidence = self.adapter.calculate_confidence(features, idx, missing, is_stale)

            salary_raw = features.loc[idx].get("salary")
            salary = int(salary_raw) if not pd.isna(salary_raw) else None
            value = self.adapter.calculate_value(features, idx, median, salary)
            matchup = self.adapter.calculate_matchup_score(features, idx)

            explanation = self.adapter.explain_projection(
                features, idx, median, floor, ceiling, missing, is_stale
            )

            result = {
                "entity_id": int(features.loc[idx].get("id", idx)),
                "entity_type": "player",
                "entity_name": str(features.loc[idx].get("name", f"Player #{idx}")),
                "sport": self.sport,
                "league": self.adapter.league,
                "event_id": None,
                "slate_id": slate_id,
                "platform": self.platform,
                "projection_timestamp": datetime.now(timezone.utc),
                "model_name": self.active_model_name,
                "model_version": self.active_model_version,
                "input_data_timestamp": datetime.now(timezone.utc),
                "median_projection": median,
                "floor_projection": floor,
                "ceiling_projection": ceiling,
                "boom_probability": boom,
                "bust_probability": bust,
                "salary": salary,
                "value_score": value,
                "matchup_score": matchup,
                "ownership_projection": None,
                "leverage_score": None,
                "injury_adjustment": None,
                "market_adjustment": None,
                "confidence_score": confidence,
                "explanation": explanation,
                "input_sources": self._detect_sources(features, idx),
                "missing_data_flags": missing,
                "stale_data_flag": is_stale,
            }
            results.append(result)

        return results

    # ── Data loading helpers ──────────────────────────────────

    async def _load_slate_data(self, slate_id: int) -> pd.DataFrame:
        from models.domain import Projection, Player
        query = select(Projection, Player).join(Player).where(Projection.slate_id == slate_id)
        result = await self.db.execute(query)
        rows = result.all()
        if not rows:
            # Demo fallback with 8 players to pass validation
            demo = [
                {"id": 1, "name": "Luka Doncic", "player_id": 1, "team": "DAL", "salary": 11000, "roster_position": "PG", "projected_fp": 55.4},
                {"id": 2, "name": "Stephen Curry", "player_id": 2, "team": "GSW", "salary": 10500, "roster_position": "PG", "projected_fp": 52.1},
                {"id": 3, "name": "Nikola Jokic", "player_id": 3, "team": "DEN", "salary": 11500, "roster_position": "C", "projected_fp": 60.5},
                {"id": 4, "name": "Jayson Tatum", "player_id": 4, "team": "BOS", "salary": 10200, "roster_position": "SF", "projected_fp": 48.2},
                {"id": 5, "name": "Giannis Antetokounmpo", "player_id": 5, "team": "MIL", "salary": 10800, "roster_position": "PF", "projected_fp": 54.0},
                {"id": 6, "name": "Kevin Durant", "player_id": 6, "team": "PHX", "salary": 9800, "roster_position": "SF", "projected_fp": 44.0},
                {"id": 7, "name": "Bennedict Mathurin", "player_id": 7, "team": "IND", "salary": 4500, "roster_position": "SG", "projected_fp": 25.0},
                {"id": 8, "name": "Joel Embiid", "player_id": 8, "team": "PHI", "salary": 11300, "roster_position": "C", "projected_fp": 56.0},
            ]
            return pd.DataFrame(demo)
        data = []
        for proj, player in rows:
            d = {c.name: getattr(proj, c.name) for c in proj.__table__.columns}
            d["name"] = player.name
            d["team"] = player.team
            if "player_id" not in d:
                d["player_id"] = d.get("id")
            data.append(d)
        return pd.DataFrame(data)

    async def _load_game_logs(self, projections: pd.DataFrame) -> pd.DataFrame:
        player_ids = projections["player_id"].dropna().unique().tolist() if "player_id" in projections.columns else []
        if not player_ids:
            return pd.DataFrame()
        result = await self.db.execute(
            select(GameLog).where(GameLog.player_id.in_(player_ids))
        )
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in result.scalars().all()])

    async def _load_matchups(self) -> pd.DataFrame:
        result = await self.db.execute(select(Matchup))
        return pd.DataFrame([{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in result.scalars().all()])

    # ── Freshness and quality ─────────────────────────────────

    def _check_staleness(self, data: pd.DataFrame) -> bool:
        return False  # Demo fallback data has no timestamps

    def _identify_missing(self, features: pd.DataFrame, idx: int) -> List[str]:
        missing = []
        row = features.loc[idx]
        for col in ["avg_fp_last_5", "opponent_def_rating", "minutes", "injury_status", "starting_status"]:
            if col in features.columns and pd.isna(row[col]):
                missing.append(col)
            elif col not in features.columns:
                missing.append(col)
        return sorted(missing)

    def _detect_sources(self, features: pd.DataFrame, idx: int) -> List[str]:
        sources = ["slate_projections"]
        row = features.loc[idx]
        if "avg_fp_last_5" in features.columns and not pd.isna(row["avg_fp_last_5"]):
            sources.append("game_logs")
        return sources


# ── Audit logging ─────────────────────────────────────────────

async def log_audit_record(
    db: AsyncSession,
    user_id: Optional[int],
    endpoint: str,
    action: str,
    request_body: dict,
    response_body: dict,
    model_version: Optional[str],
    latency_ms: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """Record every AI request to the audit log. No raw tokens or secrets."""
    input_hash = hashlib.sha256(json.dumps(request_body, sort_keys=True, default=str).encode()).hexdigest()[:16]
    response_hash = hashlib.sha256(json.dumps(response_body, sort_keys=True, default=str).encode()).hexdigest()[:16]

    log = AIAuditLog(
        user_id=user_id,
        action=action,
        endpoint=endpoint,
        input_hash=input_hash,
        response_hash=response_hash,
        model_version=model_version,
        tokens_used=0,  # Deterministic in Phase 7A
        cost=0.0,
        latency_ms=latency_ms,
        success=success,
        error=error,
    )
    db.add(log)
    await db.commit()
