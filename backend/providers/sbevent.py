"""
Shared normalized event model — ONE shape consumed by all pages.

Built from the official SportsGameOdds SDK types (sports-odds-api).
No custom field guessing. All field names match frontend expectations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from providers.sgo_rookie import classify_sgo_market, parse_american, parse_float


@dataclass
class SBTeam:
    name: str
    abbreviation: str
    team_id: str = ""
    score: Optional[float] = None


@dataclass
class SBPlayer:
    player_id: str
    name: str
    team_id: str = ""
    position: str = ""


@dataclass
class SBBookLine:
    bookmaker: str
    available: bool = True
    moneyline: Optional[int] = None
    spread: Optional[float] = None
    over_under: Optional[float] = None
    is_main_line: bool = False
    last_updated: Optional[str] = None
    opening_odds: Optional[int] = None
    opening_spread: Optional[float] = None
    opening_over_under: Optional[float] = None
    close_odds: Optional[int] = None
    close_spread: Optional[float] = None
    close_over_under: Optional[float] = None


@dataclass
class SBMarket:
    odd_id: str
    market_name: str
    bet_type: str = ""        # moneyline, spread, over_under, player_prop, team_prop, other
    side: str = ""            # home, away, over, under
    stat_entity_id: str = ""  # player_id or team identifier
    stat_id: str = ""
    period_id: str = ""
    player_id: str = ""
    player_name: str = ""
    fair_odds: Optional[int] = None
    fair_spread: Optional[float] = None
    fair_over_under: Optional[float] = None
    book_odds: Optional[int] = None
    book_spread: Optional[float] = None
    book_over_under: Optional[float] = None
    books: list[SBBookLine] = field(default_factory=list)


@dataclass
class SBEvent:
    id: str
    sport: str
    league: str
    start_time: Optional[str] = None
    status: str = "SCHEDULED"   # SCHEDULED, LIVE, FINAL
    status_display: str = ""
    home_team: SBTeam = field(default_factory=lambda: SBTeam(name="", abbreviation=""))
    away_team: SBTeam = field(default_factory=lambda: SBTeam(name="", abbreviation=""))
    players: list[SBPlayer] = field(default_factory=list)
    markets: list[SBMarket] = field(default_factory=list)
    bookmakers: list[str] = field(default_factory=list)
    home_score: Optional[float] = None
    away_score: Optional[float] = None
    period: Optional[str] = None
    venue: str = ""
    results: Optional[dict] = None


def _attr(obj, *names, default=None):
    for name in names:
        if obj is None:
            continue
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            val = getattr(obj, name)
            if val is not None:
                return val
    return default


def _results_dict(raw) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        try:
            data = dump(mode="json")
        except TypeError:
            data = dump()
        return data if isinstance(data, dict) else None
    return None


def from_sdk_event(sdk_event) -> SBEvent:
    """Convert an official SportsGameOdds SDK Event (or duck-typed stand-in) to SBEvent."""
    event = sdk_event
    event_id = _attr(event, "event_id", "eventID") or ""

    # Teams — from official SDK Teams model
    home = SBTeam(name="", abbreviation="")
    away = SBTeam(name="", abbreviation="")
    teams_obj = _attr(event, "teams")
    if teams_obj:
        home_sdk = _attr(teams_obj, "home")
        away_sdk = _attr(teams_obj, "away")
        if home_sdk:
            names = _attr(home_sdk, "names")
            home = SBTeam(
                name=_attr(names, "long") or "" if names else "",
                abbreviation=_attr(names, "short") or "" if names else "",
                team_id=_attr(home_sdk, "team_id", "teamID") or "",
                score=_attr(home_sdk, "score"),
            )
        if away_sdk:
            names = _attr(away_sdk, "names")
            away = SBTeam(
                name=_attr(names, "long") or "" if names else "",
                abbreviation=_attr(names, "short") or "" if names else "",
                team_id=_attr(away_sdk, "team_id", "teamID") or "",
                score=_attr(away_sdk, "score"),
            )

    # Status — from official SDK Status model
    status = "SCHEDULED"
    status_display = ""
    start_time = None
    period = None
    status_obj = _attr(event, "status")
    if status_obj:
        if _attr(status_obj, "live"):
            status = "LIVE"
        elif _attr(status_obj, "completed") or _attr(status_obj, "finalized"):
            status = "FINAL"
        status_display = _attr(status_obj, "display_long", "displayLong") or ""
        if _attr(status_obj, "starts_at", "startsAt"):
            start_time = _attr(status_obj, "starts_at", "startsAt")
            if hasattr(start_time, "isoformat"):
                start_time = start_time.isoformat()
            else:
                start_time = str(start_time)
        if _attr(status_obj, "current_period_id", "currentPeriodID"):
            period = _attr(status_obj, "current_period_id", "currentPeriodID")

    # Players — from official SDK Players model
    players = []
    players_map = _attr(event, "players") or {}
    if players_map and hasattr(players_map, "items"):
        for pid, psdk in players_map.items():
            player_name = _attr(psdk, "name") or f"{_attr(psdk, 'first_name', 'firstName') or ''} {_attr(psdk, 'last_name', 'lastName') or ''}".strip()
            players.append(SBPlayer(
                player_id=_attr(psdk, "player_id", "playerID") or pid,
                name=player_name or pid,
                team_id=_attr(psdk, "team_id", "teamID") or "",
            ))

    # Markets — from official SDK Odds model
    markets = []
    bookmaker_set: set[str] = set()
    odds_map = _attr(event, "odds") or {}
    players_map = _attr(event, "players") or {}
    if odds_map:
        for odd_id, o in odds_map.items():
            seid = _attr(o, "stat_entity_id", "statEntityID") or ""
            pid = _attr(o, "player_id", "playerID") or ""
            period_id = _attr(o, "period_id", "periodID") or ""
            stat_id = _attr(o, "stat_id", "statID") or ""
            bet_type_id = _attr(o, "bet_type_id", "betTypeID") or ""
            bet_type = classify_sgo_market(
                odd_id=odd_id or "",
                stat_entity_id=seid,
                player_id=pid,
                bet_type_id=bet_type_id,
                stat_id=stat_id,
                period_id=period_id,
            )
            player_name = ""
            if bet_type == "player_prop":
                sid = pid or seid
                p_sdk = players_map.get(sid) if hasattr(players_map, "get") else None
                if p_sdk:
                    player_name = (
                        _attr(p_sdk, "name")
                        or f"{_attr(p_sdk, 'first_name', 'firstName') or ''} {_attr(p_sdk, 'last_name', 'lastName') or ''}".strip()
                    )

            if seid == "home":
                side = "home"
            elif seid == "away":
                side = "away"
            else:
                parts = (odd_id or "").split("-")
                side = parts[-1] if parts else ""

            books = []
            by_book = _attr(o, "by_bookmaker", "byBookmaker") or {}
            if by_book:
                for bk_id, bk in by_book.items():
                    bookmaker_set.add(_attr(bk, "bookmaker_id", "bookmakerID") or bk_id)
                    books.append(SBBookLine(
                        bookmaker=_attr(bk, "bookmaker_id", "bookmakerID") or bk_id,
                        available=_attr(bk, "available") if _attr(bk, "available") is not None else True,
                        moneyline=parse_american(_attr(bk, "odds")),
                        spread=parse_float(_attr(bk, "spread")),
                        over_under=parse_float(_attr(bk, "over_under", "overUnder")),
                        is_main_line=bool(_attr(bk, "is_main_line", "isMainLine")),
                        last_updated=str(_attr(bk, "last_updated_at", "lastUpdatedAt")) if _attr(bk, "last_updated_at", "lastUpdatedAt") else None,
                        opening_odds=parse_american(_attr(bk, "opening_odds", "openOdds", "openingOdds")),
                        opening_spread=parse_float(_attr(bk, "opening_spread", "openSpread", "openingSpread")),
                        opening_over_under=parse_float(_attr(bk, "opening_over_under", "openOverUnder", "openingOverUnder")),
                        close_odds=parse_american(_attr(bk, "close_odds", "closeOdds")),
                        close_spread=parse_float(_attr(bk, "close_spread", "closeSpread")),
                        close_over_under=parse_float(_attr(bk, "close_over_under", "closeOverUnder")),
                    ))

            markets.append(SBMarket(
                odd_id=odd_id,
                market_name=_attr(o, "market_name", "marketName") or odd_id,
                bet_type=bet_type,
                side=side,
                stat_entity_id=seid,
                stat_id=stat_id,
                period_id=period_id,
                player_id=pid,
                player_name=player_name,
                fair_odds=parse_american(_attr(o, "fair_odds", "fairOdds")),
                fair_spread=parse_float(_attr(o, "fair_spread", "fairSpread")),
                fair_over_under=parse_float(_attr(o, "fair_over_under", "fairOverUnder")),
                book_odds=parse_american(_attr(o, "book_odds", "bookOdds")),
                book_spread=parse_float(_attr(o, "book_spread", "bookSpread")),
                book_over_under=parse_float(_attr(o, "book_over_under", "bookOverUnder")),
                books=books,
            ))

    results = _results_dict(_attr(event, "results"))
    home_score = None
    away_score = None
    if results:
        game = results.get("game", {})
        if isinstance(game, dict):

            def _extract_score(val):
                if isinstance(val, dict):
                    pts = val.get("points")
                    if pts is not None:
                        return float(pts)
                if isinstance(val, (int, float)):
                    return float(val)
                return None

            home_score = _extract_score(game.get("home"))
            away_score = _extract_score(game.get("away"))
        if home_score is None:
            home_score = home.score
        if away_score is None:
            away_score = away.score

    return SBEvent(
        id=event_id,
        sport=_attr(event, "sport_id", "sportID") or "",
        league=_attr(event, "league_id", "leagueID") or "",
        start_time=start_time,
        status=status,
        status_display=status_display,
        home_team=home,
        away_team=away,
        players=players,
        markets=markets,
        bookmakers=sorted(bookmaker_set),
        home_score=home_score,
        away_score=away_score,
        period=period,
        results=results,
    )