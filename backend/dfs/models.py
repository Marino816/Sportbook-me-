"""
SB ME Native DFS Contest Data Models.

Normalized contest player pool representation consumed by the optimizer.
Platform-agnostic — DraftKings and FanDuel both produce these objects.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class DFSContestPlayer:
    """Normalized DFS contest player — platform-independent."""
    platform: str                                # "draftkings" | "fanduel"
    slate_id: str = ""                           # provider slate identifier
    slate_name: str = ""
    sport: str = ""                              # "MLB" | "NFL" | "NBA" | "NHL"
    start_time: Optional[datetime] = None

    # Player
    player_id: str = ""                          # provider player ID
    player_name: str = ""
    team: str = ""                               # team abbreviation
    opponent: str = ""                           # opponent abbreviation
    position: str = ""                           # primary rostered position
    eligible_positions: list[str] = field(default_factory=list)

    # DFS
    salary: int = 0
    game_info: str = ""                          # "TEAM @ TEAM MM/DD HH:MM ET"

    # SB ME internal
    sbme_player_id: Optional[str] = None         # reconciled SGO player ID
    sbme_team_id: Optional[str] = None
    sbme_confidence: float = 1.0                 # 0.0–1.0 reconciliation confidence

    # Metadata
    data_source: str = "native"                  # "native" | "sportsdataio"
    ingested_at: Optional[datetime] = None

    def to_optimizer_pool(self) -> dict:
        """Convert to the dict format the optimizer expects."""
        return {
            "id": self.sbme_player_id or self.player_id,
            "name": self.player_name,
            "team": self.team,
            "salary": self.salary,
            "roster_position": self.position,
            "projected_fp": 0.0,  # filled later by SGO/SB ME projection engine
        }

    @classmethod
    def list_to_pool(cls, players: list[DFSContestPlayer]) -> list[dict]:
        return [p.to_optimizer_pool() for p in players]


@dataclass
class DFSSlate:
    """DFS contest slate metadata."""
    platform: str
    slate_id: str
    slate_name: str
    sport: str
    start_time: Optional[datetime] = None
    player_count: int = 0
    salary_cap: int = 50000
    data_source: str = "native"
    ingested_at: Optional[datetime] = None