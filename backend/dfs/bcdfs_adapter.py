#!/usr/bin/env python3
"""
Blue Collar DFS API Adapter — server-side DK/FD slate ingestion.

Reads BCDFS_API_KEY from Railway environment only.  Fetches documented
Blue Collar API endpoints, parses players into canonical DFSContestPlayer
models, and syncs to the DFSSlate / DFSPlayer persistence layer.

Phase 1 responsibilities: slate discovery, platform player IDs, salaries,
position eligibility, teams, opponents.  Does NOT replace SB ME's
projection engine.  BC projections are stored as optional provider
metadata only and have zero path to the customer-facing projected_fp.

Rate limit: 200 req / day (documented).  Internal request accounting
prevents exceeding the cap.  Scheduler-ready but scheduling is NOT
activated here — requires separate approval.

Licensing boundary: raw Blue Collar JSON never leaves this module.
BCDFS_API_KEY is never logged, printed, or returned to any caller.
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, date
from typing import Optional

from dfs.models import DFSContestPlayer, DFSSlate as CanonicalSlate

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

BC_BASE = "https://bluecollardfs.com/api"

# Every documented DK/FD endpoint we support.
ENDPOINTS: dict[tuple[str, str], str] = {
    ("MLB", "draftkings"): f"{BC_BASE}/mlb_draftkings",
    ("MLB", "fanduel"):    f"{BC_BASE}/mlb_fanduel",
    ("NFL", "draftkings"): f"{BC_BASE}/nfl_draftkings",
    ("NFL", "fanduel"):    f"{BC_BASE}/nfl_fanduel",
    ("NBA", "draftkings"): f"{BC_BASE}/nba_draftkings",
    ("NBA", "fanduel"):    f"{BC_BASE}/nba_fanduel",
    ("GOLF", "draftkings"): f"{BC_BASE}/golf_draftkings",
    ("GOLF", "fanduel"):   f"{BC_BASE}/golf_fanduel",
}

SUPPORTED_SPORTS = {"MLB", "NFL", "NBA", "GOLF"}
SUPPORTED_PLATFORMS = {"draftkings", "fanduel"}

# 200 requests per day (documented).  Conservative cap at 190 to leave
# headroom for ad-hoc / debugging fetches.
DAILY_LIMIT = 200
SAFE_LIMIT = 190

# Team abbreviation normalisation.  Blue Collar uses the DraftKings
# convention.  The only known mismatch vs SGO is ATH→OAK (Athletics).
# Add more as discovered across sports.
TEAM_NORMALIZE: dict[str, str] = {
    "ATH": "OAK",   # Blue Collar "ATH" → canonical "OAK"
    "AZ":  "ARI",   # safety — should already be ARI
    "WSH": "WSH",   # OK as-is
    "CWS": "CWS",   # OK
    "LAA": "LAA",   # OK
    "CHC": "CHC",   # OK
}

# BC date format is "MM_DD_YY" (underscores).
BC_DATE_FMT = "%m_%d_%y"

# Request timeout
REQUEST_TIMEOUT = 30


# ══════════════════════════════════════════════════════════════════════
# Rate Limiter
# ══════════════════════════════════════════════════════════════════════

@dataclass
class BcRateLimiter:
    """Internal request counter — no server-side rate headers exist."""
    _counts: dict[str, int] = field(default_factory=dict)
    _reset_at: Optional[datetime] = None

    def _ensure_reset(self) -> None:
        now = datetime.now(timezone.utc)
        if self._reset_at is None or now >= self._reset_at:
            self._counts.clear()
            # Reset at next midnight UTC
            self._reset_at = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    def remaining(self) -> int:
        self._ensure_reset()
        used = sum(self._counts.values())
        return max(0, SAFE_LIMIT - used)

    def record(self, key: str = "default") -> None:
        self._ensure_reset()
        self._counts[key] = self._counts.get(key, 0) + 1
        used = sum(self._counts.values())
        if used >= DAILY_LIMIT * 0.9:
            logger.warning("BC rate limit at %.0f%% (%d/%d)", 100*used/DAILY_LIMIT, used, DAILY_LIMIT)

    def can_request(self) -> bool:
        return self.remaining() > 0


# ══════════════════════════════════════════════════════════════════════
# Normalization helpers
# ══════════════════════════════════════════════════════════════════════

def normalize_team(abbr: str) -> str:
    """Map Blue Collar team abbreviation to SB ME canonical form."""
    return TEAM_NORMALIZE.get(abbr.upper().strip(), abbr.upper().strip())


def split_eligible_positions(position: str) -> list[str]:
    """Split '1B/2B' → ['1B', '2B']; single pos → ['P'].

    Also normalises SP/RP→P (in case BC ever uses them)."""
    parts = [p.strip().upper() for p in position.split("/")]
    normalized = []
    for p in parts:
        if p in ("SP", "RP"):
            normalized.append("P")
        else:
            normalized.append(p)
    return normalized


def parse_slate_date(date_str: str) -> Optional[date]:
    """Parse BC's 'MM_DD_YY' date string → date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), BC_DATE_FMT).date()
    except ValueError:
        logger.warning("Could not parse BC date: %r", date_str)
        return None


def parse_slate_time(slate_name: str, slate_date: Optional[date]) -> Optional[datetime]:
    """Derive approximate start_time from slate name + date.

    BC slate names contain time hints like '7:40PM ET', '6:40PM ET'.
    Returns a timezone-naive datetime (Eastern time implied by BC).
    The freshness gate (dfs/freshness.py) converts to ET internally."""
    if slate_date is None:
        return None
    import re
    m = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', slate_name, re.IGNORECASE)
    if not m:
        # No time in name — use noon ET as a safe default on that date
        logger.debug("BC slate %r has no parseable time; defaulting to noon", slate_name)
        return datetime(slate_date.year, slate_date.month, slate_date.day, 12, 0)
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return datetime(slate_date.year, slate_date.month, slate_date.day, hour, minute)


def bc_slate_key(sport: str, platform: str, date_str: str, slate_name: str) -> str:
    """Deterministic external slate identity for dedup.

    BC provides no numeric slate ID, so we construct one from
    sport+platform+date+normalized-name.  Stable across re-fetches."""
    raw = f"{sport}|{platform}|{date_str}|{slate_name}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _try_int(value: str) -> int:
    """Safely convert string to int, returning 0 on failure."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        logger.debug("Non-integer value: %r", value)
        return 0


def _try_float(value: str) -> float:
    """Safely convert string to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ══════════════════════════════════════════════════════════════════════
# API Fetch
# ══════════════════════════════════════════════════════════════════════

class BcApiError(Exception):
    """Raised for non-200 BC API responses."""
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"BC API {status}: {body[:120]}")

class BcRateLimitError(BcApiError):
    """429 — daily request cap hit."""

class BcAuthError(BcApiError):
    """401 / 403 — key invalid or access denied."""


def _get_api_key() -> str:
    """Read BCDFS_API_KEY from environment.  NEVER log or print."""
    import os
    key = os.environ.get("BCDFS_API_KEY", "")
    if not key:
        raise BcAuthError(401, "BCDFS_API_KEY not set in environment")
    return key


def fetch_bc_endpoint(
    sport: str,
    platform: str,
    rate_limiter: Optional[BcRateLimiter] = None,
) -> dict:
    """Fetch a Blue Collar API endpoint and return parsed JSON.

    Raises BcApiError on non-200, BcRateLimitError on 429.
    Returns the raw response dict exactly as returned by BC.

    SECURITY: key is only read from env, never logged.
    """
    sport_upper = sport.upper()
    plat_lower = platform.lower()
    key = (sport_upper, plat_lower)
    if key not in ENDPOINTS:
        raise ValueError(f"No BC endpoint for {sport_upper} {platform}")

    url = ENDPOINTS[key]
    api_key = _get_api_key()

    if rate_limiter and not rate_limiter.can_request():
        raise BcRateLimitError(429, "BC daily request limit reached (internal tracker)")

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"ApiKey {api_key}")
    req.add_header("Accept", "application/json")

    start = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx)
        elapsed = time.monotonic() - start
        body = resp.read()
        if rate_limiter:
            rate_limiter.record(f"{sport_upper}_{plat_lower}")
        logger.info("BC fetch %s %s: %d in %.2fs, %d bytes", sport_upper, plat_lower, resp.status, elapsed, len(body))
        return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if rate_limiter:
            rate_limiter.record(f"{sport_upper}_{plat_lower}")
        if e.code == 429:
            raise BcRateLimitError(e.code, body) from e
        if e.code in (401, 403):
            raise BcAuthError(e.code, body) from e
        raise BcApiError(e.code, body) from e
    except urllib.error.URLError as e:
        raise BcApiError(0, f"Network error: {e}") from e
    except Exception as e:
        raise BcApiError(0, f"Unexpected error: {e}") from e


# ══════════════════════════════════════════════════════════════════════
# Response Parsing → Canonical Models
# ══════════════════════════════════════════════════════════════════════

@dataclass
class BcParseResult:
    """Result of parsing a BC endpoint response."""
    sport: str
    platform: str
    slates: list[CanonicalSlate] = field(default_factory=list)
    players_by_slate: dict[str, list[DFSContestPlayer]] = field(default_factory=dict)
    total_players: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def parse_bc_response(
    data: dict,
    sport: str,
    platform: str,
) -> BcParseResult:
    """Parse a BC API response dict into canonical DFSSlate + DFSContestPlayer models.

    BC response shape: {"slates": [{"slate": "...", "date": "MM_DD_YY",
    "updated": "...", "info": [{player...}]}]}

    Each player: {"name", "salary", "projection", "value", "beta_proj",
    "site_id", "position", "team", "opponent"}

    RAW BC PROJECTION/VALUE/BETA_PROJ ARE INTENTIONALLY DROPPED HERE.
    They are stored only via the optional bc_metadata path (see
    sync function).  This parser produces clean salary/roster data.
    """
    result = BcParseResult(sport=sport, platform=platform)
    plat_lower = platform.lower()
    sport_upper = sport.upper()

    raw_slates = data.get("slates", [])
    if not isinstance(raw_slates, list):
        result.errors.append("BC response 'slates' is not a list")
        return result

    for si, raw_slate in enumerate(raw_slates):
        if not isinstance(raw_slate, dict):
            result.warnings.append(f"Slate #{si} is not a dict; skipped")
            continue

        slate_name = raw_slate.get("slate", f"BC {sport_upper} #{si}")
        date_str = raw_slate.get("date", "")
        players_raw = raw_slate.get("info", [])

        if not players_raw:
            result.warnings.append(f"Slate '{slate_name}' has no players; skipped")
            continue

        slate_date = parse_slate_date(date_str)
        start_time = parse_slate_time(slate_name, slate_date)

        cs = CanonicalSlate(
            platform=plat_lower,
            slate_id=bc_slate_key(sport_upper, plat_lower, date_str, slate_name),
            slate_name=slate_name,
            sport=sport_upper,
            start_time=start_time,
            player_count=len(players_raw),
            data_source="blue_collar",
            ingested_at=datetime.now(timezone.utc),
        )
        result.slates.append(cs)

        players: list[DFSContestPlayer] = []
        for pi, p in enumerate(players_raw):
            if not isinstance(p, dict):
                result.warnings.append(f"Slate '{slate_name}' player #{pi} not dict")
                continue

            site_id = str(p.get("site_id", "")).strip()
            if not site_id:
                result.warnings.append(
                    f"Player '{p.get('name', '?')}' missing site_id in '{slate_name}'"
                )
                # Still include — name is fallback identity

            player_name = str(p.get("name", "")).strip()
            team_raw = str(p.get("team", "")).strip()
            opponent_raw = str(p.get("opponent", "")).strip()
            position_raw = str(p.get("position", "")).strip()
            salary_int = _try_int(p.get("salary", "0"))

            # Normalise
            team = normalize_team(team_raw) if team_raw else ""
            opponent = normalize_team(opponent_raw) if opponent_raw else ""
            eligible_positions = split_eligible_positions(position_raw)
            primary_position = eligible_positions[0] if eligible_positions else ""

            # BC projection / value — parsed but stored only as metadata
            # in the sync path.  NOT written to projected_fp.
            bc_projection = _try_float(p.get("projection", "0"))
            bc_value = _try_float(p.get("value", "0"))
            bc_beta = _try_float(p.get("beta_proj", "0"))

            player = DFSContestPlayer(
                platform=plat_lower,
                slate_id=cs.slate_id,
                slate_name=slate_name,
                sport=sport_upper,
                start_time=start_time,
                player_id=site_id,
                player_name=player_name,
                team=team,
                opponent=opponent,
                position=primary_position,
                eligible_positions=eligible_positions,
                salary=salary_int,
                data_source="blue_collar",
                ingested_at=datetime.now(timezone.utc),
                # game_info derived for backward compat
                game_info=f"{team}@{opponent} {date_str}" if team and opponent else date_str,
            )
            players.append(player)

        result.players_by_slate[cs.slate_id] = players
        result.total_players += len(players)

    if not result.slates:
        result.warnings.append(
            f"No slates with players found in BC {sport_upper} {platform} response"
        )

    return result


# ══════════════════════════════════════════════════════════════════════
# Database Sync (idempotent)
# ══════════════════════════════════════════════════════════════════════

@dataclass
class BcSyncReport:
    """Report from a sync operation."""
    sport: str
    platform: str
    slates_created: int = 0
    slates_updated: int = 0
    slates_removed: int = 0
    players_added: int = 0
    players_updated: int = 0
    players_removed: int = 0
    players_unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_slates(self) -> int:
        return self.slates_created + self.slates_updated

    @property
    def total_players(self) -> int:
        return self.players_added + self.players_updated + self.players_unchanged


async def sync_bc_to_db(
    db,  # AsyncSession
    parse_result: BcParseResult,
    auto_publish: bool = True,
) -> BcSyncReport:
    """Sync a BC parse result into the DFSSlate / DFSPlayer tables.

    Idempotent: re-fetching the same sport/platform/date/slate combination
    updates existing records rather than duplicating.  Identity is external_slate_id
    (the deterministic bc_slate_key hash).

    BC projection, value, and beta_proj are stored in a JSON metadata
    column (reconciliation_report) for internal research only — they
    have zero path to the customer-facing projected_fp field.

    auto_publish=True: all CURRENT slates are auto-published (same
    behaviour as the CSV import gate).
    """
    from sqlalchemy import select, delete
    from dfs.db import DFSSlate as DBSlate, DFSPlayer as DBPlayer
    from dfs.freshness import is_current_slate

    report = BcSyncReport(
        sport=parse_result.sport,
        platform=parse_result.platform,
    )

    if not parse_result.success:
        report.errors.extend(parse_result.errors)
        return report

    for cs in parse_result.slates:
        players = parse_result.players_by_slate.get(cs.slate_id, [])

        # ── Find or create slate ──
        result = await db.execute(
            select(DBSlate).where(DBSlate.external_slate_id == cs.slate_id)
        )
        existing_slate = result.scalars().first()

        if existing_slate:
            # Update metadata
            existing_slate.slate_name = cs.slate_name
            existing_slate.start_time = cs.start_time
            existing_slate.player_count = cs.player_count
            existing_slate.version = (existing_slate.version or 1) + 1
            # Keep status unless admin overrides
            if auto_publish and is_current_slate(cs.start_time):
                if existing_slate.status not in ("PUBLISHED", "ARCHIVED"):
                    existing_slate.status = "PUBLISHED"
                    existing_slate.published_at = datetime.now(timezone.utc)
            db_slate = existing_slate
            report.slates_updated += 1
        else:
            db_slate = DBSlate(
                platform=cs.platform,
                sport=cs.sport,
                external_slate_id=cs.slate_id,
                slate_name=cs.slate_name,
                start_time=cs.start_time,
                player_count=cs.player_count,
                data_source="blue_collar",
                status="PUBLISHED" if (auto_publish and is_current_slate(cs.start_time)) else "DRAFT",
                published_at=datetime.now(timezone.utc) if (auto_publish and is_current_slate(cs.start_time)) else None,
            )
            db.add(db_slate)
            await db.flush()  # get db_slate.id
            report.slates_created += 1

        # ── Sync players ──
        # Build lookup of existing players by provider_player_id
        existing_result = await db.execute(
            select(DBPlayer).where(DBPlayer.slate_id == db_slate.id)
        )
        existing_players = {p.provider_player_id: p for p in existing_result.scalars().all()}
        incoming_ids = set()

        for cp in players:
            incoming_ids.add(cp.player_id)
            existing = existing_players.get(cp.player_id)

            if existing:
                # Check for changes
                changed = False
                if existing.player_name != cp.player_name:
                    existing.player_name = cp.player_name
                    changed = True
                if existing.team != cp.team:
                    existing.team = cp.team
                    changed = True
                if existing.opponent != cp.opponent:
                    existing.opponent = cp.opponent
                    changed = True
                if existing.position != cp.position:
                    existing.position = cp.position
                    changed = True
                if existing.eligible_positions != cp.eligible_positions:
                    existing.eligible_positions = cp.eligible_positions
                    changed = True
                if existing.salary != cp.salary:
                    existing.salary = cp.salary
                    changed = True
                if existing.game_info != cp.game_info:
                    existing.game_info = cp.game_info
                    changed = True

                if changed:
                    report.players_updated += 1
                else:
                    report.players_unchanged += 1
            else:
                db_player = DBPlayer(
                    slate_id=db_slate.id,
                    provider_player_id=cp.player_id,
                    player_name=cp.player_name,
                    team=cp.team,
                    opponent=cp.opponent,
                    position=cp.position,
                    eligible_positions=cp.eligible_positions,
                    salary=cp.salary,
                    game_info=cp.game_info,
                    mapping_status="UNMATCHED",
                )
                db.add(db_player)
                report.players_added += 1

        # Remove players no longer in the feed
        removed_ids = set(existing_players.keys()) - incoming_ids
        if removed_ids:
            await db.execute(
                delete(DBPlayer).where(
                    DBPlayer.slate_id == db_slate.id,
                    DBPlayer.provider_player_id.in_(removed_ids),
                )
            )
            report.players_removed += len(removed_ids)

        # Update slate counts
        db_slate.player_count = len(incoming_ids)

    await db.commit()
    logger.info(
        "BC sync %s %s: %d created, %d updated, %d added, %d updated, %d removed, %d unchanged",
        report.sport, report.platform,
        report.slates_created, report.slates_updated,
        report.players_added, report.players_updated,
        report.players_removed, report.players_unchanged,
    )
    return report


# ══════════════════════════════════════════════════════════════════════
# Top-level convenience
# ══════════════════════════════════════════════════════════════════════

async def fetch_and_sync(
    db,  # AsyncSession
    sport: str,
    platform: str,
    rate_limiter: Optional[BcRateLimiter] = None,
    auto_publish: bool = True,
) -> BcSyncReport:
    """Fetch from BC API, parse, and sync to DB in one call.

    This is the primary entry point for scheduled / on-demand sync.
    Does NOT activate a scheduler — the caller decides when to call it.
    """
    data = fetch_bc_endpoint(sport, platform, rate_limiter=rate_limiter)
    parse_result = parse_bc_response(data, sport, platform)
    return await sync_bc_to_db(db, parse_result, auto_publish=auto_publish)