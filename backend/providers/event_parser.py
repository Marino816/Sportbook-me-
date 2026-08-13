"""V2 Event Odds Parser — extracts all markets from embedded event.odds structure."""

from __future__ import annotations

import re
from typing import Optional
from dataclasses import dataclass, field


def _parse_odds(val) -> Optional[int]:
    """Parse American odds from string or int: '+100' → 100, '-150' → -150."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        return int(str(val))
    except (ValueError, TypeError):
        return None


def _parse_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


@dataclass
class ParsedBookLine:
    bookmaker_id: str
    available: bool
    odds: Optional[int] = None
    spread: Optional[float] = None
    over_under: Optional[float] = None
    deeplink: str = ""


@dataclass
class ParsedMarket:
    odd_id: str
    market_name: str
    stat_id: str = ""
    stat_entity_id: str = ""
    period_id: str = ""
    bet_type_id: str = ""
    side_id: str = ""
    fair_odds: Optional[dict] = None
    books: list[ParsedBookLine] = field(default_factory=list)
    
    @property
    def best_odds(self) -> Optional[int]:
        """Highest available American odds across all books."""
        best = None
        for b in self.books:
            if b.available and b.odds is not None:
                if best is None or b.odds > best:
                    best = b.odds
        return best


@dataclass
class ParsedEventMarkets:
    event_id: str
    moneylines: list[ParsedMarket] = field(default_factory=list)
    spreads: list[ParsedMarket] = field(default_factory=list)
    totals: list[ParsedMarket] = field(default_factory=list)
    player_props: list[ParsedMarket] = field(default_factory=list)
    team_props: list[ParsedMarket] = field(default_factory=list)
    other: list[ParsedMarket] = field(default_factory=list)
    bookmakers: list[str] = field(default_factory=list)


def _classify_market(odd_id: str, stat_entity_id: str) -> str:
    """Classify a market into: moneyline, spread, total, player_prop, team_prop, other."""
    oid = odd_id.lower()
    
    # Player props: statEntityID references a specific player (not home/away/all)
    if stat_entity_id and stat_entity_id not in ("home", "away", "all", ""):
        return "player_prop"
    
    # Team-level markets
    if "ml" in oid or "moneyline" in oid:
        return "moneyline"
    if "sp" in oid or "spread" in oid or "handicap" in oid:
        return "spread"
    if "ou" in oid or "total" in oid or "over" in oid or "under" in oid:
        return "total"
    if "prop" in oid and stat_entity_id in ("home", "away"):
        return "team_prop"
    
    return "other"


def parse_event_odds(event_id: str, raw_odds: dict, raw_players: dict | None = None) -> ParsedEventMarkets:
    """
    Parse the embedded event.odds structure from a v2 /events response.
    
    Args:
        event_id: The SGO event ID
        raw_odds: The event["odds"] dict (oddID → market data)
        raw_players: Optional event["players"] dict for statEntityID → player resolution
    
    Returns:
        ParsedEventMarkets with classified markets and bookmaker list.
    """
    result = ParsedEventMarkets(event_id=event_id)
    bookmaker_set: set[str] = set()
    
    for odd_id, odd_data in raw_odds.items():
        if not isinstance(odd_data, dict):
            continue
            
        market = ParsedMarket(
            odd_id=odd_id,
            market_name=odd_data.get("marketName", odd_id),
            stat_id=odd_data.get("statID", ""),
            stat_entity_id=odd_data.get("statEntityID", ""),
            period_id=odd_data.get("periodID", ""),
            bet_type_id=odd_data.get("betTypeID", ""),
            side_id=odd_data.get("sideID", ""),
            fair_odds=odd_data.get("fairOdds"),
        )
        
        # Parse byBookmaker
        by_bookmaker = odd_data.get("byBookmaker", {})
        for book_id, book_data in by_bookmaker.items():
            if not isinstance(book_data, dict):
                continue
            bookmaker_set.add(book_id)
            
            available = book_data.get("available", False)
            line = ParsedBookLine(
                bookmaker_id=book_id,
                available=available,
                odds=_parse_odds(book_data.get("odds")),
                spread=_parse_float(book_data.get("spread")),
                over_under=_parse_float(book_data.get("overUnder")),
                deeplink=book_data.get("deeplink", ""),
            )
            market.books.append(line)
        
        # Sort books: available first, then by odds descending
        market.books.sort(key=lambda b: (not b.available, -(b.odds if b.odds is not None else -99999)))
        
        # Classify
        category = _classify_market(odd_id, market.stat_entity_id)
        if category == "moneyline":
            result.moneylines.append(market)
        elif category == "spread":
            result.spreads.append(market)
        elif category == "total":
            result.totals.append(market)
        elif category == "player_prop":
            result.player_props.append(market)
        elif category == "team_prop":
            result.team_props.append(market)
        else:
            result.other.append(market)
    
    result.bookmakers = sorted(bookmaker_set)
    return result


def extract_bookmaker_odds_table(parsed: ParsedEventMarkets) -> dict:
    """
    Build a table: bookmaker → {moneyline_home, moneyline_away, spread_home, spread_away, total_over, total_under}
    
    Uses best available odds per bookmaker for each market type.
    """
    table: dict[str, dict] = {}
    
    for book_id in parsed.bookmakers:
        table[book_id] = {
            "bookmaker": book_id,
            "moneyline_home": None,
            "moneyline_away": None,
            "spread_home": None,
            "spread_away": None,
            "total_over": None,
            "total_under": None,
        }
    
    # Process moneylines
    for m in parsed.moneylines:
        for b in m.books:
            if not b.available or b.odds is None:
                continue
            entry = table.get(b.bookmaker_id)
            if entry is None:
                continue
            if "home" in m.odd_id.lower():
                if entry["moneyline_home"] is None or b.odds > (entry["moneyline_home"] or -9999):
                    entry["moneyline_home"] = b.odds
            elif "away" in m.odd_id.lower():
                if entry["moneyline_away"] is None or b.odds > (entry["moneyline_away"] or -9999):
                    entry["moneyline_away"] = b.odds
    
    # Process spreads
    for m in parsed.spreads:
        for b in m.books:
            if not b.available or b.spread is None:
                continue
            entry = table.get(b.bookmaker_id)
            if entry is None:
                continue
            if "home" in m.odd_id.lower():
                entry["spread_home"] = b.spread
            elif "away" in m.odd_id.lower():
                entry["spread_away"] = b.spread
    
    # Process totals
    for m in parsed.totals:
        for b in m.books:
            if not b.available or b.over_under is None:
                continue
            entry = table.get(b.bookmaker_id)
            if entry is None:
                continue
            if "over" in m.odd_id.lower():
                entry["total_over"] = b.over_under
            elif "under" in m.odd_id.lower():
                entry["total_under"] = b.over_under
    
    return table


def build_player_props_list(parsed: ParsedEventMarkets, raw_players: dict) -> list[dict]:
    """
    Build player props list from parsed markets, resolving statEntityID to player info.
    
    Returns list of {player_id, player_name, team, markets: [{market_name, lines: [{bookmaker, line, over_price, under_price}]}]}
    """
    player_map: dict[str, dict] = {}
    
    for prop in parsed.player_props:
        pid = prop.stat_entity_id
        if not pid:
            continue
            
        if pid not in player_map:
            player_info = raw_players.get(pid, {}) if isinstance(raw_players, dict) else {}
            player_map[pid] = {
                "player_id": pid,
                "player_name": player_info.get("name", player_info.get("names", {}).get("long", pid)),
                "team": player_info.get("team", ""),
                "position": player_info.get("position", ""),
                "markets": {},
            }
        
        entry = player_map[pid]
        market_name = prop.market_name or prop.odd_id
        
        if market_name not in entry["markets"]:
            entry["markets"][market_name] = {
                "market": market_name,
                "lines": [],
            }
        
        for b in prop.books:
            if not b.available:
                continue
            entry["markets"][market_name]["lines"].append({
                "bookmaker": b.bookmaker_id,
                "line": b.spread or b.over_under or 0,
                "over_price": b.odds,
                "under_price": None,
            })
    
    result = list(player_map.values())
    # Sort by number of markets descending
    result.sort(key=lambda p: len(p["markets"]), reverse=True)
    return result