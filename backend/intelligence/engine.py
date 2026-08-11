"""
SB ME Intelligence Engine v1 — Primary signal layer over SportsGameOdds.

Produces normalized player intelligence, game intelligence, market signals,
and context for SB ME AI without modifying DFS projections.

All signals are transparent, testable, and documented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from providers.normalizer import (
    SportsGameOddsNormalizer,
    NormalizedEvent,
    NormalizedGameOdds,
    NormalizedPlayerProp,
    NormalizedBookmakerLine,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  Sport-Aware Environment Thresholds
# ══════════════════════════════════════════════════════════════

SPORT_ENV_THRESHOLDS = {
    "MLB": {
        "high": 9.0,
        "above_avg": 8.0,
        "neutral_low": 7.5,
        "below_avg": 6.5,
    },
    "NFL": {},
    "NBA": {},
    "NHL": {},
    "NCAAF": {},
    "NCAAB": {},
}


# ══════════════════════════════════════════════════════════════
#  Signal Enums
# ══════════════════════════════════════════════════════════════

class PlayerSignal(str, Enum):
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"


class GameEnvironmentSignal(str, Enum):
    HIGH = "HIGH"
    ABOVE_AVERAGE = "ABOVE_AVERAGE"
    NEUTRAL = "NEUTRAL"
    BELOW_AVERAGE = "BELOW_AVERAGE"
    LOW = "LOW"


class DataSourceStatus(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DFSDataMode(str, Enum):
    """SportsDataIO DFS data quality — separate from market context."""
    TRIAL_SCRAMBLED = "TRIAL_SCRAMBLED"
    LIVE_PRODUCTION = "LIVE_PRODUCTION"
    UNAVAILABLE = "UNAVAILABLE"


# ══════════════════════════════════════════════════════════════
#  Odds Math Helpers
# ══════════════════════════════════════════════════════════════

def american_to_implied_probability(odds: int) -> float | None:
    """
    Convert American odds to implied probability.
    +150 → 0.400 (40%)
    -200 → 0.667 (66.7%)
    """
    if odds == 0:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def implied_probability_to_american(prob: float) -> int:
    """Convert implied probability to closest American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return round(-100.0 * prob / (1 - prob))
    return round(100.0 * (1 - prob) / prob)


def probability_edge(market_odds: int, fair_odds: int) -> float | None:
    """
    Edge as probability difference.
    fair_implied - market_implied
    Returns percentage points (0.05 = 5pp edge).
    """
    m = american_to_implied_probability(market_odds)
    f = american_to_implied_probability(fair_odds)
    if m is None or f is None:
        return None
    return round(f - m, 4)


# ══════════════════════════════════════════════════════════════
#  Intelligence Objects
# ══════════════════════════════════════════════════════════════

@dataclass
class PlayerIntelligence:
    """DFS intelligence for one player, assembled from SGO + SDIO data."""

    player_id: str = ""
    player_name: str = ""
    team_id: str = ""
    opponent_id: str = ""
    position: str = ""

    # DFS inputs (from SportsDataIO fallback)
    dfs_salary: int = 0
    base_projection: float = 0.0

    # SGO market signals
    fantasy_market_line: Optional[float] = None
    fantasy_market_edge: Optional[float] = None  # projection - market line
    fantasy_market_book: str = ""

    # Prop signals (selected markets)
    prop_signals: dict[str, "PropIntelligence"] = field(default_factory=dict)

    # Book consensus
    sportsbook_count: int = 0
    prop_book_count: int = 0

    # Derived signals
    player_signal: PlayerSignal = PlayerSignal.NEUTRAL
    conviction_score: float = 0.0  # 0.0 – 1.0 from multi-book agreement

    # Context
    game_total: Optional[float] = None
    game_environment: GameEnvironmentSignal = GameEnvironmentSignal.NEUTRAL
    team_implied_score: Optional[float] = None

    # Freshness
    data_freshness_seconds: Optional[float] = None
    last_updated: Optional[datetime] = None
    # Separate provider statuses (not conflated)
    dfs_data_mode: DFSDataMode = DFSDataMode.TRIAL_SCRAMBLED      # SportsDataIO
    market_context_status: DataSourceStatus = DataSourceStatus.UNAVAILABLE  # SGO
    # Explainability
    reasons: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "team_id": self.team_id,
            "opponent_id": self.opponent_id,
            "position": self.position,
            "dfs_salary": self.dfs_salary,
            "base_projection": self.base_projection,
            "fantasy_market_line": self.fantasy_market_line,
            "fantasy_market_edge": self.fantasy_market_edge,
            "fantasy_market_book": self.fantasy_market_book,
            "prop_signals": {k: v.to_dict() for k, v in self.prop_signals.items()},
            "sportsbook_count": self.sportsbook_count,
            "prop_book_count": self.prop_book_count,
            "player_signal": self.player_signal.value,
            "conviction_score": round(self.conviction_score, 2),
            "game_total": self.game_total,
            "game_environment": self.game_environment.value,
            "team_implied_score": self.team_implied_score,
            "data_freshness_seconds": (
                round(self.data_freshness_seconds) if self.data_freshness_seconds else None
            ),
            "last_updated": str(self.last_updated) if self.last_updated else None,
            "dfs_data_mode": self.dfs_data_mode.value,
            "market_context_status": self.market_context_status.value,
            "reasons": self.reasons,
            "missing_signals": self.missing_signals,
        }


@dataclass
class PropIntelligence:
    """A single SGO player prop normalized into SB ME signal."""
    market: str           # "fantasyScore", "hits", "homeRuns", etc.
    bookmaker: str
    line: float
    over_price: Optional[int] = None
    under_price: Optional[int] = None
    fair_line: Optional[float] = None
    edge_pct: Optional[float] = None   # (fair - market) / market * 100
    opening_line: Optional[float] = None
    current_line: Optional[float] = None
    line_movement: Optional[float] = None  # current - opening

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "bookmaker": self.bookmaker,
            "line": self.line,
            "over_price": self.over_price,
            "under_price": self.under_price,
            "fair_line": self.fair_line,
            "edge_pct": self.edge_pct,
            "opening_line": self.opening_line,
            "current_line": self.current_line,
            "line_movement": self.line_movement,
        }


@dataclass
class GameIntelligence:
    """DFS intelligence for one game."""
    event_id: str
    home_team_id: str = ""
    away_team_id: str = ""
    home_team_name: str = ""
    away_team_name: str = ""

    # Market data
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None
    spread_line: Optional[float] = None
    total_line: Optional[float] = None
    opening_total: Optional[float] = None
    total_movement: Optional[float] = None   # current - opening
    opening_spread: Optional[float] = None
    spread_movement: Optional[float] = None

    # Book consensus
    book_count: int = 0
    total_book_count: int = 0

    # Environment
    game_environment: GameEnvironmentSignal = GameEnvironmentSignal.NEUTRAL

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "home_team_name": self.home_team_name,
            "away_team_name": self.away_team_name,
            "moneyline_home": self.moneyline_home,
            "moneyline_away": self.moneyline_away,
            "spread_line": self.spread_line,
            "total_line": self.total_line,
            "opening_total": self.opening_total,
            "total_movement": self.total_movement,
            "book_count": self.book_count,
            "game_environment": self.game_environment.value,
        }


# ══════════════════════════════════════════════════════════════
#  Signal Computer
# ══════════════════════════════════════════════════════════════

class SignalComputer:
    """
    Computes SB ME signals from normalized SGO data.

    All formulas are transparent and configurable.
    """

    @staticmethod
    def player_signal(pi: PlayerIntelligence) -> PlayerSignal:
        """
        Player signal from fantasy market edge.

        Formula:
          edge = base_projection - fantasy_market_line
          VERY_BULLISH: edge > 3.0
          BULLISH:      edge > 1.0
          NEUTRAL:     -1.0 <= edge <= 1.0
          BEARISH:      edge < -1.0
          VERY_BEARISH: edge < -3.0
        """
        edge = pi.fantasy_market_edge
        if edge is None:
            return PlayerSignal.NEUTRAL
        if edge > 3.0:
            return PlayerSignal.VERY_BULLISH
        if edge > 1.0:
            return PlayerSignal.BULLISH
        if edge < -3.0:
            return PlayerSignal.VERY_BEARISH
        if edge < -1.0:
            return PlayerSignal.BEARISH
        return PlayerSignal.NEUTRAL

    @staticmethod
    def game_environment(total_line: Optional[float]) -> GameEnvironmentSignal:
        """
        Game environment from total line.

        Formula (MLB):
          HIGH:        total > 9.0
          ABOVE_AVG:   total > 8.0
          NEUTRAL:     7.0 <= total <= 8.0
          BELOW_AVG:   total > 6.0
          LOW:         total <= 6.0
          UNKNOWN:     total is None → NEUTRAL
        """
        if total_line is None:
            return GameEnvironmentSignal.NEUTRAL
        if total_line > 9.0:
            return GameEnvironmentSignal.HIGH
        if total_line > 8.0:
            return GameEnvironmentSignal.ABOVE_AVERAGE
        if total_line < 6.5:
            return GameEnvironmentSignal.LOW
        if total_line < 7.5:
            return GameEnvironmentSignal.BELOW_AVERAGE
        return GameEnvironmentSignal.NEUTRAL

    @staticmethod
    def conviction_score(pi: PlayerIntelligence) -> float:
        """
        Multi-book conviction: proportion of books with same direction.

        Formula:
          conviction = bullish_books / total_books
          (0.0 if no books available)
        """
        if pi.prop_book_count == 0:
            return 0.0
        bullish = sum(
            1 for p in pi.prop_signals.values()
            if p.edge_pct is not None and p.edge_pct > 0
        )
        return bullish / max(pi.prop_book_count, 1)

    @staticmethod
    def compute_all(pi: PlayerIntelligence):
        """Compute all derived signals for a player intelligence record."""
        pi.player_signal = SignalComputer.player_signal(pi)
        pi.game_environment = SignalComputer.game_environment(pi.game_total)
        pi.conviction_score = SignalComputer.conviction_score(pi)
        pi.market_context_status = (
            DataSourceStatus.LIVE
            if pi.fantasy_market_line is not None
            else DataSourceStatus.UNAVAILABLE
        )
        pi.dfs_data_mode = DFSDataMode.TRIAL_SCRAMBLED
        # Build reasons
        pi.reasons = []
        if pi.fantasy_market_edge is not None:
            pi.reasons.append(
                f"Fantasy projection edge {pi.fantasy_market_edge:+.1f} vs market line {pi.fantasy_market_line}"
            )
        if pi.prop_book_count > 0:
            pi.reasons.append(f"{pi.prop_book_count} sportsbooks reporting props")
        if pi.game_total is not None:
            pi.reasons.append(f"Game total {pi.game_total} ({pi.game_environment.value})")
        pi.missing_signals = [
            m for m in ["hits", "homeRuns", "rbi", "stolenBases",
                          "battingStrikeouts", "pitchingStrikeouts"]
            if m not in pi.prop_signals
        ]