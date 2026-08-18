"""
Historical fantasy-scoring service — public API.

  MLBScorekeeper      — stat dict → ScoringResult (per-game)
  build_game_log      — SGO events → PlayerGameLog (last-N aggregate)
  ScoringPlatform     — DRAFTKINGS | FANDUEL
  ScoringResult       — per-game FP + audit trail
  PlayerGameLog       — aggregated N-game log
"""

from scoring.models import (
    GameScore,
    PlayerGameLog,
    ScoringMode,
    ScoringPlatform,
    ScoringResult,
    Sport,
    PlayerRole,
)

from scoring.mlb import MLBScorekeeper
from scoring.historical import build_game_log

__all__ = [
    "MLBScorekeeper",
    "build_game_log",
    "GameScore",
    "PlayerGameLog",
    "ScoringMode",
    "ScoringPlatform",
    "ScoringResult",
    "Sport",
    "PlayerRole",
]