"""
SB ME Normalization Layer — SportsGameOdds → Internal Models.

Normalizes SGO provider responses into typed SB ME data objects
used by the intelligence layer, AI, and optimizer context.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NormalizedEvent:
    id: str
    provider_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: Optional[datetime] = None
    status: str = "SCHEDULED"  # SCHEDULED / LIVE / FINAL / POSTPONED
    home_score: Optional[int] = None
    away_score: Optional[int] = None


@dataclass
class NormalizedTeam:
    id: str
    provider_id: str
    name: str
    abbreviation: str = ""
    league: str = ""
    sport: str = ""


@dataclass
class NormalizedPlayer:
    id: str
    provider_id: str
    name: str
    team: str = ""
    position: str = ""
    league: str = ""
    sport: str = ""


@dataclass
class NormalizedPlayerStat:
    player_id: str
    season: str = ""
    stat_name: str = ""
    stat_value: float = 0.0
    games_played: int = 0


@dataclass
class NormalizedBookmakerLine:
    bookmaker: str  # DraftKings, FanDuel, BetMGM, etc.
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None
    spread_home: Optional[float] = None
    spread_away: Optional[float] = None
    total_over: Optional[float] = None
    total_under: Optional[float] = None
    updated_at: Optional[datetime] = None


@dataclass
class NormalizedGameOdds:
    event_id: str
    books: list[NormalizedBookmakerLine] = field(default_factory=list)
    consensus: Optional[NormalizedBookmakerLine] = None
    fair_moneyline_home: Optional[int] = None
    fair_moneyline_away: Optional[int] = None
    fair_total: Optional[float] = None


@dataclass
class NormalizedPlayerProp:
    player_id: str
    bookmaker: str
    market: str  # e.g. "hits", "strikeouts", "points"
    line: float
    over_price: Optional[int] = None
    under_price: Optional[int] = None


@dataclass
class GameEnvironment:
    """Aggregated game context for DFS intelligence."""
    event_id: str
    home_team: str
    away_team: str
    implied_total_home: Optional[float] = None
    implied_total_away: Optional[float] = None
    game_total: Optional[float] = None
    bookmakers_available: int = 0
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    ballpark_factor: Optional[float] = None


# ── Normalizer ──

def _field(obj: dict, *names: str):
    """Get value by trying multiple field names (snake_case + camelCase + SGO caps)."""
    for n in names:
        if n in obj:
            return obj[n]
    # Try camelCase (event_id → eventId)
    for n in names:
        cc = _camel(n)
        if cc in obj:
            return obj[cc]
    # Try ALL-CAPS initialisms (event_id → eventID, id → ID)
    for n in names:
        cc2 = _camel_caps(n)
        if cc2 in obj:
            return obj[cc2]
    return None


def _camel(snake: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _camel_caps(snake: str) -> str:
    """Convert snake_case to camelCase with common initialisms (ID, URL, etc.)."""
    parts = snake.split("_")
    caps_map = {"id": "ID", "url": "URL", "dfs": "DFS"}
    result = parts[0]
    for p in parts[1:]:
        result += caps_map.get(p, p.capitalize())
    return result


def _resolve_team_name(obj: dict) -> str:
    """Extract team name from nested team object."""
    names = obj.get("names", {})
    if isinstance(names, dict):
        return names.get("display") or names.get("full") or names.get("name") or ""
    return obj.get("name") or obj.get("displayName") or ""


class SportsGameOddsNormalizer:
    """Convert raw SGO API responses into normalized SB ME models."""

    @staticmethod
    def normalize_event(raw: dict) -> NormalizedEvent:
        eid = _field(raw, "eventID", "id", "eventId", "event_id") or ""

        # Team resolution — try flat fields first, then nested teams.home/away
        home_name = _field(raw, "homeTeamName", "homeTeam", "home_team_name") or ""
        away_name = _field(raw, "awayTeamName", "awayTeam", "away_team_name") or ""
        home_id = ""
        away_id = ""

        teams = raw.get("teams")
        if isinstance(teams, dict):
            home_obj = teams.get("home") or teams.get("homeTeam")
            away_obj = teams.get("away") or teams.get("awayTeam")
            if isinstance(home_obj, dict):
                home_id = _field(home_obj, "teamID", "id", "teamId") or ""
                if not home_name:
                    home_name = _resolve_team_name(home_obj)
            if isinstance(away_obj, dict):
                away_id = _field(away_obj, "teamID", "id", "teamId") or ""
                if not away_name:
                    away_name = _resolve_team_name(away_obj)

        return NormalizedEvent(
            id=eid,
            provider_id=eid,
            sport=_field(raw, "sportID", "sport", "sportId", "league") or "",
            league=_field(raw, "leagueID", "league", "leagueId") or "",
            home_team=home_name or home_id,
            away_team=away_name or away_id,
            start_time=_parse_datetime(_field(raw, "startTime", "start_time", "dateTime", "gameTime")),
            status=_field(raw, "status", "gameStatus", "eventStatus") or "SCHEDULED",
            home_score=_field(raw, "homeScore", "home_score"),
            away_score=_field(raw, "awayScore", "away_score"),
        )

    @staticmethod
    def normalize_player(raw: dict) -> NormalizedPlayer:
        pid = _field(raw, "playerID", "id", "playerId", "player_id") or ""
        tid = _field(raw, "teamID", "teamId", "team_id") or ""
        names = raw.get("names", {})
        if isinstance(names, dict):
            name = names.get("display") or names.get("full") or names.get("name") or ""
        else:
            name = str(names) if names else ""
        return NormalizedPlayer(
            id=pid,
            provider_id=pid,
            name=name or _field(raw, "name", "fullName", "playerName") or "",
            team=tid,
            position=_field(raw, "position", "pos") or "",
            league=_field(raw, "leagueID", "league", "leagueId") or "",
            sport=_field(raw, "sportID", "sport", "sportId") or "",
        )

    @staticmethod
    def normalize_team(raw: dict) -> NormalizedTeam:
        tid = _field(raw, "teamID", "id", "teamId", "team_id") or ""
        names = raw.get("names", {})
        if isinstance(names, dict):
            name = names.get("display") or names.get("full") or names.get("name") or ""
        else:
            name = str(names) if names else ""
        return NormalizedTeam(
            id=tid,
            provider_id=tid,
            name=name or raw.get("name", ""),
            abbreviation=_field(raw, "abbreviation", "abbr", "code") or "",
            league=_field(raw, "leagueID", "league", "leagueId") or "",
            sport=_field(raw, "sportID", "sport", "sportId") or "",
        )

    @staticmethod
    def normalize_bookmaker_line(raw: dict) -> NormalizedBookmakerLine:
        return NormalizedBookmakerLine(
            bookmaker=raw.get("bookmaker", raw.get("book", "")),
            moneyline_home=raw.get("moneyline_home"),
            moneyline_away=raw.get("moneyline_away"),
            spread_home=raw.get("spread_home"),
            spread_away=raw.get("spread_away"),
            total_over=raw.get("total_over", raw.get("over")),
            total_under=raw.get("total_under", raw.get("under")),
            updated_at=_parse_datetime(raw.get("updated_at")),
        )

    @staticmethod
    def normalize_game_odds(raw: dict, event_id: str) -> NormalizedGameOdds:
        books_raw = raw.get("books", raw.get("bookmakers", []))
        consensus_raw = raw.get("consensus")
        return NormalizedGameOdds(
            event_id=event_id,
            books=[SportsGameOddsNormalizer.normalize_bookmaker_line(b) for b in books_raw],
            consensus=(SportsGameOddsNormalizer.normalize_bookmaker_line(consensus_raw)
                        if consensus_raw else None),
            fair_moneyline_home=raw.get("fair_moneyline_home"),
            fair_moneyline_away=raw.get("fair_moneyline_away"),
            fair_total=raw.get("fair_total"),
        )

    @staticmethod
    def normalize_player_prop(raw: dict) -> NormalizedPlayerProp:
        return NormalizedPlayerProp(
            player_id=raw.get("player_id", ""),
            bookmaker=raw.get("bookmaker", raw.get("book", "")),
            market=raw.get("market", ""),
            line=float(raw.get("line", 0)),
            over_price=raw.get("over_price"),
            under_price=raw.get("under_price"),
        )


def _parse_datetime(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None