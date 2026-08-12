"""
SB ME Market Engine — Shared foundation for all five market tools.

Provides:
- Market identity normalization (oddID-based deduplication)
- Odds math utilities (American ↔ Decimal, implied probability, edge)
- Bookmaker priority ranking
- Line movement detection
- Shared cache coordination
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


# ══════════════════════════════════════════════════════════════
#  Bookmaker Priority
# ══════════════════════════════════════════════════════════════

BOOKMAKER_PRIORITY = [
    "DraftKings",
    "FanDuel",
    "BetMGM",
    "Caesars",
    "ESPN BET",
    "Bovada",
    "Unibet",
    "PointsBet",
    "William Hill",
    "Bet365",
    "Barstool",
    "BetRivers",
    "SugarHouse",
    "TwinSpires",
    "Circa",
    "Pinnacle",
    "Betfred",
    "Betway",
]


def bookmaker_rank(book: str) -> int:
    """Return priority rank for a bookmaker (lower = higher priority)."""
    bk = book.strip()
    for i, b in enumerate(BOOKMAKER_PRIORITY):
        if b.lower() == bk.lower() or b.lower() in bk.lower():
            return i
    return len(BOOKMAKER_PRIORITY)  # unknown books last


def normalize_bookmaker(raw: str) -> str:
    """Normalize bookmaker name to canonical form."""
    bk = raw.strip()
    for b in BOOKMAKER_PRIORITY:
        if b.lower() == bk.lower():
            return b
        if bk.lower().startswith(b.lower()[:4]):
            return b
    return bk


# ══════════════════════════════════════════════════════════════
#  Odds Math
# ══════════════════════════════════════════════════════════════


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal."""
    if american > 0:
        return 1.0 + american / 100.0
    elif american < 0:
        return 1.0 + 100.0 / abs(american)
    return 1.0


def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds to American."""
    if decimal >= 2.0:
        return round((decimal - 1.0) * 100)
    elif decimal > 1.0:
        return round(-100.0 / (decimal - 1.0))
    return 0


def implied_probability(american: int) -> float:
    """Calculate implied win probability from American odds."""
    if american > 0:
        return 100.0 / (american + 100.0)
    elif american < 0:
        return abs(american) / (abs(american) + 100.0)
    return 0.5


def overround(probs: list[float]) -> float:
    """Calculate the overround (vig) from a list of implied probabilities."""
    return sum(probs) - 1.0


def fair_probability(probs: list[float]) -> list[float]:
    """Remove vig from implied probabilities (proportional method)."""
    total = sum(probs)
    if total == 0:
        return probs
    return [p / total for p in probs]


def edge_pct(market_line: float, fair_line: float) -> float:
    """Calculate edge percentage: (fair - market) / abs(market)."""
    if market_line == 0:
        return 0.0
    return round((fair_line - market_line) / abs(market_line) * 100, 1)


# ══════════════════════════════════════════════════════════════
#  Market Identity
# ══════════════════════════════════════════════════════════════


class MarketType(str, Enum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"
    TEAM_PROP = "team_prop"
    FANTASY_SCORE = "fantasy_score"
    ALTERNATE_LINE = "alternate_line"


@dataclass
class MarketIdentity:
    """Uniquely identifies a market across bookmakers."""
    odd_id: str = ""  # SGO oddID
    event_id: str = ""
    market_type: MarketType = MarketType.MONEYLINE
    period: str = "FULL_GAME"  # FULL_GAME, 1H, 2H, Q1, etc.
    player_id: Optional[str] = None
    stat_id: Optional[str] = None  # e.g., "hits", "homeRuns", "fantasyScore"
    selection: str = ""  # "over", "under", "home", "away", "draw"
    line: Optional[float] = None  # e.g., 228.5, -6.5, 1.5 (for props)


@dataclass
class BookmakerLine:
    """A single line from one bookmaker."""
    bookmaker: str
    line: Optional[float] = None
    price: Optional[int] = None  # American odds
    opening_line: Optional[float] = None
    opening_price: Optional[int] = None
    fair_odds: Optional[float] = None
    updated_at: Optional[datetime] = None


@dataclass
class MarketSnapshot:
    """Snapshot of a market across all bookmakers at a point in time."""
    identity: MarketIdentity
    books: list[BookmakerLine] = field(default_factory=list)
    consensus_line: Optional[float] = None
    fair_odds_line: Optional[float] = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    best_over_price: Optional[int] = None
    best_over_book: str = ""
    best_under_price: Optional[int] = None
    best_under_book: str = ""
    book_count: int = 0

    def compute_bests(self):
        """Compute best over/under prices from available books."""
        best_over = None
        best_under = None
        for b in self.books:
            if b.price is not None:
                # For over markets, higher American price = better (more +)
                # For under markets, higher American price = better
                if best_over is None or b.price > best_over[0]:
                    best_over = (b.price, b.bookmaker)
                if best_under is None or b.price > best_under[0]:
                    best_under = (b.price, b.bookmaker)
        if best_over:
            self.best_over_price = best_over[0]
            self.best_over_book = best_over[1]
        if best_under:
            self.best_under_price = best_under[0]
            self.best_under_book = best_under[1]
        self.book_count = len(self.books)


# ══════════════════════════════════════════════════════════════
#  Line Movement
# ══════════════════════════════════════════════════════════════


class MovementType(str, Enum):
    LINE_MOVE = "LINE_MOVE"
    PRICE_MOVE = "PRICE_MOVE"
    STEAM_MOVE = "STEAM_MOVE"  # multiple books moving same direction
    REVERSAL = "REVERSAL"  # line moved then reversed
    NO_CHANGE = "NO_CHANGE"


@dataclass
class LineMovement:
    """Detected line movement between two snapshots."""
    event_id: str
    market_identity: MarketIdentity
    bookmaker: str
    movement_type: MovementType = MovementType.NO_CHANGE
    previous_line: Optional[float] = None
    current_line: Optional[float] = None
    previous_price: Optional[int] = None
    current_price: Optional[int] = None
    movement_amount: float = 0.0
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def detect_movement(prev: BookmakerLine, curr: BookmakerLine) -> MovementType:
    """Detect type of line movement."""
    line_changed = (
        prev.line is not None and curr.line is not None
        and abs(prev.line - curr.line) > 0.01
    )
    price_changed = prev.price != curr.price

    if line_changed and price_changed:
        return MovementType.STEAM_MOVE
    elif line_changed:
        return MovementType.LINE_MOVE
    elif price_changed:
        return MovementType.PRICE_MOVE
    return MovementType.NO_CHANGE


# ══════════════════════════════════════════════════════════════
#  Arbitrage
# ══════════════════════════════════════════════════════════════


@dataclass
class ArbitrageOpportunity:
    """Mathematically identified pricing discrepancy."""
    event_id: str
    market: str  # "moneyline", "total", etc.
    outcome_a: str
    book_a: str
    odds_a: int  # American
    outcome_b: str
    book_b: str
    odds_b: int  # American
    outcome_c: Optional[str] = None  # for 3-way
    book_c: Optional[str] = None
    odds_c: Optional[int] = None
    implied_total: float = 0.0  # combined implied probability sum
    arb_percent: float = 0.0  # estimated edge %

    def stakes(self, bankroll: float = 1000.0) -> dict[str, float]:
        """Calculate optimal stakes for given bankroll."""
        odds = [american_to_decimal(self.odds_a), american_to_decimal(self.odds_b)]
        outcomes = [self.outcome_a, self.outcome_b]
        if self.outcome_c and self.odds_c:
            odds.append(american_to_decimal(self.odds_c))
            outcomes.append(self.outcome_c)

        # Proportional staking: stake_i = bankroll / (sum(1/odds_j) * odds_i)
        inv_sum = sum(1.0 / o for o in odds)
        stakes = {}
        for i, outcome in enumerate(outcomes):
            stakes[outcome] = round(bankroll / (inv_sum * odds[i]), 2)
        return stakes

    def gross_payout(self, bankroll: float = 1000.0) -> float:
        """Calculate gross payout."""
        s = self.stakes(bankroll)
        odds = {
            self.outcome_a: american_to_decimal(self.odds_a),
            self.outcome_b: american_to_decimal(self.odds_b),
        }
        if self.outcome_c and self.odds_c:
            odds[self.outcome_c] = american_to_decimal(self.odds_c)
        # Return the minimum payout (arb guarantees this is > bankroll)
        payouts = [s[outcome] * odds[outcome] for outcome in s]
        return round(min(payouts), 2)


def check_arbitrage(odds_a: int, odds_b: int, odds_c: Optional[int] = None) -> Optional[ArbitrageOpportunity]:
    """Check if a set of odds presents a mathematical arbitrage opportunity."""
    dec_a = american_to_decimal(odds_a)
    dec_b = american_to_decimal(odds_b)
    imp_sum = 1.0 / dec_a + 1.0 / dec_b

    if odds_c:
        dec_c = american_to_decimal(odds_c)
        imp_sum += 1.0 / dec_c

    if imp_sum < 1.0:
        # Arbitrage exists
        arb_pct = round((1.0 - imp_sum) * 100, 2)
        return ArbitrageOpportunity(
            event_id="",
            market="",
            outcome_a="",
            book_a="",
            odds_a=odds_a,
            outcome_b="",
            book_b="",
            odds_b=odds_b,
            odds_c=odds_c,
            implied_total=round(imp_sum, 4),
            arb_percent=arb_pct,
        )
    return None


# ══════════════════════════════════════════════════════════════
#  Parlay
# ══════════════════════════════════════════════════════════════


@dataclass
class ParlayLeg:
    """One leg of a parlay."""
    event_id: str
    market: str
    selection: str
    bookmaker: str
    odds: int  # American


@dataclass
class ParlayResult:
    """Calculated parlay outcome."""
    legs: list[ParlayLeg]
    leg_count: int
    combined_decimal: float
    combined_american: int
    implied_probability: float
    stake: float = 0.0
    potential_payout: float = 0.0
    potential_profit: float = 0.0
    is_same_game: bool = False
    sgp_available: bool = False


def calculate_parlay(legs: list[ParlayLeg], stake: float = 100.0) -> ParlayResult:
    """Calculate parlay odds and payout."""
    decimals = [american_to_decimal(leg.odds) for leg in legs]
    combined_dec = 1.0
    for d in decimals:
        combined_dec *= d

    combined_dec = round(combined_dec, 4)
    combined_am = decimal_to_american(combined_dec)
    imp_prob = round(1.0 / combined_dec * 100, 1)

    event_ids = {leg.event_id for leg in legs}
    is_sgp = len(event_ids) < len(legs)

    return ParlayResult(
        legs=legs,
        leg_count=len(legs),
        combined_decimal=combined_dec,
        combined_american=combined_am,
        implied_probability=imp_prob,
        stake=stake,
        potential_payout=round(stake * combined_dec, 2),
        potential_profit=round(stake * combined_dec - stake, 2),
        is_same_game=is_sgp,
        sgp_available=False,  # SGP pricing must come from SGO
    )