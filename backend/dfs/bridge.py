"""
SB ME DFS Provider Bridge — connects native DK/FD data to the optimizer.

Feature-flagged: uses native DFS data when available, falls back to SportsDataIO.
SportsGameOdds always supplies intelligence context (odds, props, consensus).
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from datetime import datetime, timezone

from dfs.models import DFSContestPlayer, DFSSlate
from dfs.reconciliation import reconcile_all

logger = logging.getLogger(__name__)

# Feature flags
USE_NATIVE_DFS = os.getenv("SBME_NATIVE_DFS", "false").lower() in ("true", "1")
SPORTSDATAIO_FALLBACK = True  # Keep SDIO as fallback until native proven


class DFSProviderBridge:
    """
    Unified DFS data access layer.

    Priority:
      1. Native DK/FD CSV ingestion (when USE_NATIVE_DFS=true)
      2. SportsDataIO (fallback)
    """

    def __init__(self):
        self._dk_slate: Optional[DFSSlate] = None
        self._dk_players: list[DFSContestPlayer] = []
        self._fd_slate: Optional[DFSSlate] = None
        self._fd_players: list[DFSContestPlayer] = []
        self._sgo_players: list[dict] = []  # cached SGO player pool
        self._reconciled = False

    def ingest_dk_csv(self, csv_content: str, slate_name: str = "DK Main") -> DFSSlate:
        """Parse and store DraftKings contest CSV."""
        from dfs.parsers import parse_draftkings_csv
        self._dk_slate, self._dk_players = parse_draftkings_csv(csv_content, slate_name)
        self._reconciled = False
        logger.info(f"DK ingested: {self._dk_slate.player_count} players, sport={self._dk_slate.sport}")
        return self._dk_slate

    def ingest_fd_csv(self, csv_content: str, slate_name: str = "FD Main") -> DFSSlate:
        """Parse and store FanDuel contest CSV."""
        from dfs.parsers import parse_fanduel_csv
        self._fd_slate, self._fd_players = parse_fanduel_csv(csv_content, slate_name)
        self._reconciled = False
        logger.info(f"FD ingested: {self._fd_slate.player_count} players, sport={self._fd_slate.sport}")
        return self._fd_slate

    def set_sgo_players(self, players: list[dict]):
        """Cache SGO player pool for reconciliation."""
        self._sgo_players = players
        self._reconciled = False

    def reconcile(self) -> dict:
        """Reconcile all ingested DFS players against SGO player pool."""
        stats = {"dk": {}, "fd": {}}
        if self._sgo_players:
            if self._dk_players:
                stats["dk"] = reconcile_all(self._dk_players, self._sgo_players)
            if self._fd_players:
                stats["fd"] = reconcile_all(self._fd_players, self._sgo_players)
        self._reconciled = True
        return stats

    def get_pool(self, platform: str) -> list[DFSContestPlayer]:
        """Get reconciled player pool for optimizer consumption."""
        if platform == "draftkings":
            return self._dk_players
        return self._fd_players

    def get_pool_as_dicts(self, platform: str, only_reconciled: bool = True) -> list[dict]:
        """
        Return player pool in optimizer-compatible dict format.
        Only includes players with valid sbme_player_id if only_reconciled=True.
        """
        pool = self.get_pool(platform)
        if only_reconciled:
            pool = [p for p in pool if p.sbme_player_id]
            if not pool:
                logger.warning(f"No reconciled players for {platform} — all unmatched")
                pool = self.get_pool(platform)
        return DFSContestPlayer.list_to_pool(pool)

    def needs_fallback(self, platform: str) -> bool:
        """Return True if native data is insufficient and SportsDataIO should be used."""
        if not USE_NATIVE_DFS:
            return True
        pool = self.get_pool(platform)
        if not pool:
            return True
        if self._reconciled:
            reconciled = [p for p in pool if p.sbme_player_id]
            if len(reconciled) < 10:  # need at least a viable pool
                return True
        return False


# Global instance
dfs_bridge = DFSProviderBridge()