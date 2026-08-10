"""SportsDataIO integration for SPORTBOOK ME DFS AI.

Provides live (trial/scrambled) MLB data: players, slates, salaries, projections.
Upgrade to paid key for unscrambled production data.

Usage:
  from integrations.sportsdataio import mlb
  await mlb.ingest_all(db, "2026-AUG-07")
"""

from integrations.sportsdataio.client import fetch, IngestionMetrics
from integrations.sportsdataio.mlb import ingest_all, ingest_players, ingest_dfs_projections
from integrations.sportsdataio.normalizer import upsert_player, upsert_slate, upsert_projection
from integrations.sportsdataio.exceptions import (
    SportsDataIOError, TrialDataWarning, RateLimitError, AuthenticationError,
)