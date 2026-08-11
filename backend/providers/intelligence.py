"""
SGO DFS Intelligence Layer — converts SGO market data into SB ME intelligence.

Normalizes game markets (moneyline, spread, total) and player markets
(fantasyScore, hits, HR, RBI, strikeouts, etc.) into DFS-ready signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DFSIntelligencePlayer:
    """Per-player DFS intelligence from SportsGameOdds markets."""
    player_id: str = ""
    player_name: str = ""
    team: str = ""
    opponent: str = ""
    position: str = ""
    # Fantasy score from SGO fantasyScore market
    fantasy_market_line: Optional[float] = None     # e.g., 8.5 fantasy points
    fantasy_market_edge: Optional[float] = None     # Over edge vs fair
    fantasy_market_book: str = ""                    # Which book provided it
    # Prop signals (selected markets)
    prop_signals: dict[str, "PropSignal"] = field(default_factory=dict)
    sportsbook_count: int = 0
    consensus_signal: Optional[str] = None           # "STRONG_OVER" / "MIXED" / etc.
    market_updated_at: Optional[datetime] = None


@dataclass
class PropSignal:
    """A single player prop market signal."""
    market: str              # "fantasyScore", "hits", "homeRuns", etc.
    bookmaker: str
    line: float
    over_price: Optional[int] = None   # American odds
    under_price: Optional[int] = None
    fair_line: Optional[float] = None
    edge_pct: Optional[float] = None   # Over edge vs fair as percentage


@dataclass
class DFSIntelligenceGame:
    """Per-game DFS intelligence."""
    event_id: str
    home_team: str
    away_team: str
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None
    spread_line: Optional[float] = None
    spread_home_price: Optional[int] = None
    total_line: Optional[float] = None
    total_over_price: Optional[int] = None
    implied_total_home: Optional[float] = None
    implied_total_away: Optional[float] = None
    bookmakers_available: list[str] = field(default_factory=list)
    weather: Optional[dict] = None


# ── Market Parser ──

KNOWN_PROP_MARKETS = {
    "fantasyScore": ["fantasyScore", "fantasy_score", "fantasy score", "dfs points"],
    "hits": ["hits", "total hits", "player hits"],
    "homeRuns": ["homeRuns", "home_runs", "home runs", "homeruns", "hr"],
    "rbi": ["rbi", "runs batted in", "rbis"],
    "totalBases": ["totalBases", "total_bases", "total bases"],
    "stolenBases": ["stolenBases", "stolen_bases", "stolen bases", "sb"],
    "battingStrikeouts": ["battingStrikeouts", "batting_strikeouts", "batter strikeouts", "hitter strikeouts"],
    "pitchingStrikeouts": ["pitchingStrikeouts", "pitching_strikeouts", "pitcher strikeouts", "strikeouts"],
    "pitchingOuts": ["pitchingOuts", "pitching_outs", "outs recorded", "pitching outs"],
    "pitchingHits": ["pitchingHits", "pitching_hits", "hits allowed", "pitcher hits"],
    "pitchingEarnedRuns": ["pitchingEarnedRuns", "pitching_earned_runs", "earned runs", "er"],
    "pitchingWalks": ["pitchingWalks", "pitching_walks", "walks allowed", "bb"],
}


def _normalize_market_name(raw: str) -> Optional[str]:
    """Map raw SGO market name to internal prop market key."""
    r = str(raw).lower().strip()
    for key, aliases in KNOWN_PROP_MARKETS.items():
        for alias in aliases:
            if alias.lower() in r:
                return key
    return None


def _detect_bookmaker(raw: dict) -> str:
    """Extract bookmaker name from SGO odds entry."""
    return (
        raw.get("bookmaker")
        or raw.get("book")
        or raw.get("sportsbook")
        or raw.get("sportsbookName")
        or raw.get("bookName")
        or ""
    )


# ── Intelligence Builder ──

class SGOIntelligenceBuilder:
    """Build DFS intelligence from raw SGO event + odds data."""

    def __init__(self, log: logging.Logger = logger):
        self.log = log

    def build_game_intelligence(self, event: dict, odds: dict) -> DFSIntelligenceGame:
        """Extract game-level DFS intelligence from SGO odds."""
        gi = DFSIntelligenceGame(
            event_id=event.get("eventID") or event.get("id") or "",
            home_team=event.get("homeTeamName") or event.get("homeTeam") or "",
            away_team=event.get("awayTeamName") or event.get("awayTeam") or "",
        )

        books = odds.get("books") or odds.get("bookmakers") or []
        gi.bookmakers_available = [_detect_bookmaker(b) for b in books if _detect_bookmaker(b)]

        for b in books:
            book = _detect_bookmaker(b)
            if not book:
                continue
            # Moneyline
            if b.get("moneylineHome") and gi.moneyline_home is None:
                gi.moneyline_home = int(b["moneylineHome"])
            if b.get("moneylineAway") and gi.moneyline_away is None:
                gi.moneyline_away = int(b["moneylineAway"])
            # Spread
            if b.get("spread") is not None and gi.spread_line is None:
                gi.spread_line = float(b["spread"])
            # Total
            if (b.get("total") or b.get("totalOver")) and gi.total_line is None:
                gi.total_line = float(b.get("total") or b["totalOver"])

        # Consensus
        consensus = odds.get("consensus", {}) if isinstance(odds, dict) else {}
        if consensus:
            if gi.total_line is None and consensus.get("total"):
                gi.total_line = float(consensus["total"])

        return gi

    def build_player_intelligence(
        self, player_data: dict, player_props: list[dict], event: dict
    ) -> DFSIntelligencePlayer:
        """Build per-player DFS intelligence from SGO player markets."""
        dp = DFSIntelligencePlayer(
            player_id=str(player_data.get("id") or player_data.get("playerID") or ""),
            player_name=player_data.get("name") or player_data.get("fullName") or "",
            team=player_data.get("team") or player_data.get("teamID") or "",
            position=player_data.get("position") or "",
        )

        bookmakers_seen = set()
        for prop in player_props:
            book = _detect_bookmaker(prop)
            market_raw = prop.get("market") or prop.get("name") or prop.get("type") or ""
            market_key = _normalize_market_name(market_raw)
            if not market_key:
                continue

            line = float(prop.get("line", 0)) if prop.get("line") is not None else None
            if line is None:
                continue
            over_price = prop.get("overPrice") or prop.get("over")
            under_price = prop.get("underPrice") or prop.get("under")
            fair = prop.get("fairPrice") or prop.get("fair")

            signal = PropSignal(
                market=market_key,
                bookmaker=book,
                line=line,
                over_price=int(over_price) if over_price else None,
                under_price=int(under_price) if under_price else None,
                fair_line=float(fair) if fair else None,
            )

            # Calculate edge: (fair_line - market_line)
            if signal.fair_line is not None:
                signal.edge_pct = round((signal.fair_line - signal.line) / max(abs(signal.line), 0.01) * 100, 1)

            dp.prop_signals[market_key] = signal

            if market_key == "fantasyScore":
                dp.fantasy_market_line = signal.line
                dp.fantasy_market_edge = signal.edge_pct
                dp.fantasy_market_book = book

            if book:
                bookmakers_seen.add(book)

        dp.sportsbook_count = len(bookmakers_seen)

        # Determine consensus signal
        if dp.fantasy_market_edge is not None:
            if dp.fantasy_market_edge > 10:
                dp.consensus_signal = "STRONG_OVER"
            elif dp.fantasy_market_edge > 3:
                dp.consensus_signal = "OVER"
            elif dp.fantasy_market_edge < -10:
                dp.consensus_signal = "STRONG_UNDER"
            elif dp.fantasy_market_edge < -3:
                dp.consensus_signal = "UNDER"
            else:
                dp.consensus_signal = "FAIR"

        return dp