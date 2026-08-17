"""
Canonical DFS slate import service — shared DK/FD ingestion with validation.

One import path for every platform. Both DraftKings and FanDuel CSV files flow
through identical validation gates before they can become optimizer-eligible.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from dfs.parsers import parse_draftkings_csv, parse_fanduel_csv
from dfs.models import DFSContestPlayer, DFSSlate

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = {"draftkings", "fanduel"}
SUPPORTED_SPORTS = {"MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"}

# Position validation sets per sport
MLB_POS = {"P", "C", "1B", "2B", "3B", "SS", "OF", "DH"}
NFL_POS = {"QB", "RB", "WR", "TE", "DST", "FLEX"}
NBA_NCAA_POS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
NHL_POS = {"G", "D", "W"}
SPORT_POS = {
    "MLB": MLB_POS, "NFL": NFL_POS,
    "NBA": NBA_NCAA_POS, "NHL": NHL_POS,
    "NCAAF": {"QB", "RB", "WR", "TE", "DST", "FLEX"},
    "NCAAB": NBA_NCAA_POS,
}


@dataclass
class ImportValidation:
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.passed = False
        self.errors.append(msg)

    @property
    def status(self) -> str:
        if self.errors:
            return "INVALID"
        if self.warnings:
            return "VALID_WARNINGS"
        return "VALID"


@dataclass
class ImportResult:
    platform: str
    sport: str
    slate_name: str = ""
    slate_date: Optional[str] = None
    player_count: int = 0
    game_count: int = 0
    source_filename: str = ""
    validation: ImportValidation = field(default_factory=ImportValidation)
    slate_obj: Optional[DFSSlate] = None
    players: list[DFSContestPlayer] = field(default_factory=list)

    @property
    def fresh_status(self) -> str:
        """CURRENT / UPCOMING / STALE based on slate_date vs today (ET)."""
        if not self.slate_date:
            return "STALE"
        try:
            sd = datetime.strptime(self.slate_date, "%Y-%m-%d").date()
        except ValueError:
            return "STALE"
        try:
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/New_York")).date()
        except Exception:
            today = datetime.now(timezone.utc).date()
        delta = (sd - today).days
        if delta == 0:
            return "CURRENT"
        elif delta > 0:
            return "UPCOMING"
        else:
            return "STALE"

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "sport": self.sport,
            "slate_name": self.slate_name,
            "slate_date": self.slate_date,
            "player_count": self.player_count,
            "game_count": self.game_count,
            "source_filename": self.source_filename,
            "validation_status": self.validation.status,
            "validation_warnings": self.validation.warnings,
            "validation_errors": self.validation.errors,
            "freshness_status": self.fresh_status,
        }


async def import_slate_file(
    csv_content: str,
    platform: str,
    filename: str,
    forced_slate_name: Optional[str] = None,
) -> ImportResult:
    """Canonical DFS slate import with full validation.

    Accepts raw CSV content, detects platform if not provided, runs the
    appropriate parser, validates the output, and returns a canonical
    ImportResult.
    """
    result = ImportResult(
        platform=platform.lower(),
        sport="",
        source_filename=filename,
    )

    # ── Platform validation ──
    if result.platform not in SUPPORTED_PLATFORMS:
        result.validation.fail(f"Unsupported platform: {result.platform}")
        return result

    # ── Parse ──
    try:
        slate_name = forced_slate_name or filename.replace(".csv", "")
        if result.platform == "fanduel":
            slate_obj, players = parse_fanduel_csv(csv_content, slate_name=slate_name)
        else:
            slate_obj, players = parse_draftkings_csv(csv_content, slate_name=slate_name)
    except Exception as e:
        result.validation.fail(f"CSV parse error: {e}")
        return result

    result.slate_obj = slate_obj
    result.players = players
    result.sport = slate_obj.sport
    result.slate_name = slate_obj.slate_name
    result.player_count = len(players)

    # ── Validation ──
    v = result.validation

    # Sport supported?
    if result.sport not in SUPPORTED_SPORTS:
        v.fail(f"Unsupported sport: {result.sport}")

    # Players populated?
    if not players:
        v.fail("Slate contains zero players")
        return result

    # Slate date
    if slate_obj.start_time:
        result.slate_date = slate_obj.start_time.strftime("%Y-%m-%d")
    if not result.slate_date:
        v.add_warn("Could not determine slate date from game info")
    else:
        # Date freshness: daily sports (MLB/NBA/NHL) reject > 2 days old,
        # weekly sports (NFL/NCAAF) accept future up to 30 days ahead.
        sd_str = result.slate_date
        try:
            sd = datetime.strptime(sd_str, "%Y-%m-%d").date()
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("America/New_York")).date()
            delta = (sd - today).days
            daily_sports = {"MLB", "NBA", "NHL", "NCAAB"}
            if result.sport in daily_sports:
                if delta < -2:
                    v.fail(f"Slate date {sd_str} is stale ({delta} days old)")
                elif delta < 0:
                    v.add_warn(f"Slate date {sd_str} is from {abs(delta)} day(s) ago")
        except Exception:
            pass

    # Salaries must be positive
    zero_sal = sum(1 for p in players if p.salary <= 0)
    if zero_sal > len(players) * 0.1:
        v.fail(f"{zero_sal}/{len(players)} players have zero or negative salary")
    elif zero_sal > 0:
        v.add_warn(f"{zero_sal} players have zero salary")

    # Positions
    if result.sport in SPORT_POS:
        valid_pos = SPORT_POS[result.sport]
        unknown = {p.position for p in players if p.position not in valid_pos}
        if unknown:
            v.add_warn(f"Unknown positions: {unknown}")

    # Teams
    no_team = sum(1 for p in players if not p.team)
    if no_team > len(players) * 0.1:
        v.fail(f"{no_team}/{len(players)} players missing team")

    # Game count
    games = set()
    for p in players:
        gi = p.game_info or ""
        if "@" in gi:
            games.add(gi.split()[0] if " " in gi else gi)
    result.game_count = len(games)

    if result.game_count == 0:
        v.add_warn("No games detected from game_info")
    elif result.game_count == 1:
        v.add_warn("Only 1 game detected — possible show-down/single-game slate")

    logger.info(
        "Import %s: %s %s %s, %d players, %d games, valid=%s, status=%s",
        filename, result.platform, result.sport, result.slate_date,
        result.player_count, result.game_count, v.passed, result.fresh_status,
    )
    for warn in v.warnings:
        logger.warning("Import %s: %s", filename, warn)
    for err in v.errors:
        logger.error("Import %s: %s", filename, err)

    return result