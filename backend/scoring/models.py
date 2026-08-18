"""
Historical fantasy-scoring models — pure dataclasses, zero side effects.

Separate from projection/native.py.  Scoring is read-only: stat dict in,
ScoringResult out.  Missing data is explicit — never silently zeroed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ScoringPlatform(str, Enum):
    DRAFTKINGS = "draftkings"
    FANDUEL = "fanduel"


class Sport(str, Enum):
    MLB = "MLB"
    NFL = "NFL"
    NBA = "NBA"
    NHL = "NHL"


class PlayerRole(str, Enum):
    HITTER = "HITTER"
    PITCHER = "PITCHER"


class ScoringMode(str, Enum):
    """Label for how the fantasy score was produced.

    historical_partial  — at least one required scoring category is missing
                          from the underlying data; the fp value is the best
                          available total from categories that ARE present.
    historical_exact    — every required category is present; the fp value
                          is the full official score.

    We never return "historical_exact" when is_exact=False.
    """

    HISTORICAL_PARTIAL = "historical_partial"
    HISTORICAL_EXACT = "historical_exact"


@dataclass
class ScoringCategory:
    """One official scoring category mapped to its SGO data field."""

    name: str               # "single", "run", "strikeout"
    points: float           # points per unit (3.0, 2.0, −0.5)
    sgo_field: str           # "batting_singles", "batting_runsScored"
    required: bool = True   # missing → is_exact=False
    description: str = ""


@dataclass
class ScoringResult:
    """Per-game fantasy score with full audit trail.

    calculated_from contains every category that was present in the data,
    whether required or not.  missing_fields lists categories defined as
    required but absent from the stat dict.  is_exact is True ONLY when
    missing_fields is empty.

    The raw_stats dict is an exact (optional) copy of the SGO stat dict
    passed in, so every value in calculated_from can be verified against
    the upstream data.
    """

    fantasy_points: float
    is_exact: bool
    scoring_mode: ScoringMode
    platform: ScoringPlatform
    sport: Sport
    player_role: PlayerRole
    calculated_from: dict[str, float]      # category_name → contribution
    missing_fields: list[str]              # required but absent
    raw_stats: dict[str, int | None] = field(default_factory=dict)


@dataclass
class GameScore:
    """One game in a player's historical log."""

    date: str
    event_id: str
    opponent: str
    home_away: str           # "home" | "away"
    result: ScoringResult


@dataclass
class PlayerGameLog:
    """Aggregated last-N game log for one player."""

    player_id: str
    player_name: str
    platform: str
    sport: str
    player_role: str
    scoring_mode: str
    n: int
    games: list[GameScore]
    average_fp: float
    min_fp: float
    max_fp: float
    average_is_exact: bool
    global_missing_fields: list[str]