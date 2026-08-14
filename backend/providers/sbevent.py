"""
Shared normalized event model — ONE shape consumed by all pages.

Built from the official SportsGameOdds SDK types (sports-odds-api).
No custom field guessing. All field names match frontend expectations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


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


def from_sdk_event(sdk_event) -> SBEvent:
    """
    Convert an official SportsGameOdds SDK Event to SBEvent.

    Uses the official SDK models — no raw dict field guessing.
    """
    from sports_odds_api.types.event import Event as SdkEvent

    event: SdkEvent = sdk_event
    event_id = event.event_id or ""

    # Teams — from official SDK Teams model
    home = SBTeam(name="", abbreviation="")
    away = SBTeam(name="", abbreviation="")
    if event.teams:
        if event.teams.home:
            home = SBTeam(
                name=event.teams.home.names.long if event.teams.home.names else "",
                abbreviation=event.teams.home.names.short if event.teams.home.names else "",
                team_id=event.teams.home.team_id or "",
                score=event.teams.home.score,
            )
        if event.teams.away:
            away = SBTeam(
                name=event.teams.away.names.long if event.teams.away.names else "",
                abbreviation=event.teams.away.names.short if event.teams.away.names else "",
                team_id=event.teams.away.team_id or "",
                score=event.teams.away.score,
            )

    # Status — from official SDK Status model
    status = "SCHEDULED"
    status_display = ""
    start_time = None
    period = None
    if event.status:
        if event.status.live:
            status = "LIVE"
        elif event.status.completed or event.status.finalized:
            status = "FINAL"
        status_display = event.status.display_long or ""
        if event.status.starts_at:
            start_time = event.status.starts_at
        if event.status.current_period_id:
            period = event.status.current_period_id

    # Players — from official SDK Players model
    players = []
    if event.players:
        for pid, psdk in event.players.items():
            player_name = psdk.name or f"{psdk.first_name or ''} {psdk.last_name or ''}".strip()
            players.append(SBPlayer(
                player_id=psdk.player_id or pid,
                name=player_name or pid,
                team_id=psdk.team_id or "",
            ))

    # Markets — from official SDK Odds model
    markets = []
    bookmaker_set: set[str] = set()
    if event.odds:
        for odd_id, o in event.odds.items():
            # Determine bet type
            bet_type = "other"
            side = ""
            mid = (o.market_name or odd_id).lower()
            seid = o.stat_entity_id or ""
            pid = o.player_id or ""
            if "moneyline" in mid or "ml" in mid.split("-"):
                bet_type = "moneyline"
            elif "spread" in mid or "handicap" in mid:
                bet_type = "spread"
            elif "over" in mid or "under" in mid or "total" in mid:
                bet_type = "total"

            # Player prop detection via stat_entity_id / player_id
            player_name = ""
            if pid or (seid and seid not in ("home", "away", "all", "")):
                bet_type = "player_prop"
                sid = pid or seid
                if sid and event.players:
                    p_sdk = event.players.get(sid)
                    if p_sdk:
                        player_name = p_sdk.name or f"{p_sdk.first_name or ''} {p_sdk.last_name or ''}".strip()

            # Side — authoritative from stat_entity_id (home/away), otherwise the
            # odd_id's final segment (over/under/draw/not_draw/yes/no/even/odd).
            if seid == "home":
                side = "home"
            elif seid == "away":
                side = "away"
            else:
                parts = (odd_id or "").split("-")
                side = parts[-1] if parts else ""

            # Parse books
            books = []
            if o.by_bookmaker:
                for bk_id, bk in o.by_bookmaker.items():
                    bookmaker_set.add(bk.bookmaker_id or bk_id)
                    books.append(SBBookLine(
                        bookmaker=bk.bookmaker_id or bk_id,
                        available=bk.available if bk.available is not None else True,
                        moneyline=int(bk.odds) if bk.odds is not None else None,
                        spread=float(bk.spread) if bk.spread is not None else None,
                        over_under=float(bk.over_under) if bk.over_under is not None else None,
                        is_main_line=bk.is_main_line if bk.is_main_line is not None else False,
                        last_updated=bk.last_updated_at,
                    ))

            markets.append(SBMarket(
                odd_id=odd_id,
                market_name=o.market_name or odd_id,
                bet_type=bet_type,
                side=side,
                stat_entity_id=seid,
                stat_id=o.stat_id or "",
                period_id=o.period_id or "",
                player_id=pid,
                player_name=player_name,
                fair_odds=int(o.fair_odds) if o.fair_odds is not None else None,
                fair_spread=float(o.fair_spread) if o.fair_spread is not None else None,
                fair_over_under=float(o.fair_over_under) if o.fair_over_under is not None else None,
                books=books,
            ))

    # Scores
    home_score = None
    away_score = None
    if event.results:
        game = event.results.get("game", {})
        if game:
            home_score = game.get("home")
            away_score = game.get("away")

    return SBEvent(
        id=event_id,
        sport=event.sport_id or "",
        league=event.league_id or "",
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
    )