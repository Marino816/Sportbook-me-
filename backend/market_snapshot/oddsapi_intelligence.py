"""Odds API player-prop enrichment for DFS. No provider HTTP. No invented markets."""

from __future__ import annotations

from typing import Optional

# Odds API market key → existing DFS intelligence prop keys used by native.py.
# Only keys with a real Odds API market and a real consumer. No fantasyScore:
# The Odds API does not document a player fantasy-points market in this integration.
ODDSAPI_MARKET_TO_PROP = {
    "batter_hits": "hits",
    "batter_home_runs": "homeRuns",
    "batter_rbis": "rbi",
    "batter_total_bases": "totalBases",
    "batter_stolen_bases": "stolenBases",
    "batter_walks": "walks",
    "batter_strikeouts": "battingStrikeouts",
    "pitcher_strikeouts": "pitchingStrikeouts",
    "pitcher_earned_runs": "pitchingEarnedRuns",
    "pitcher_hits_allowed": "pitchingHits",
    "pitcher_walks": "pitchingWalks",
    "pitcher_outs": "pitchingOuts",
    "player_pass_yds": "passingYards",
    "player_pass_tds": "passingTouchdowns",
    "player_rush_yds": "rushingYards",
    "player_receptions": "receptions",
    "player_reception_yds": "receivingYards",
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
}

UNSUPPORTED_FOR_DFS = (
    "player_fantasy_score",
    "sgo_nested_team_props",
    "sbme_game_environment",
)


def _commence_date_et(iso: str | None) -> str | None:
    if not iso:
        return None
    from datetime import datetime
    from zoneinfo import ZoneInfo
    text = iso.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo("UTC"))
    return stamp.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def _over_line(row: dict) -> float | None:
    if str(row.get("selection") or "").lower() != "over":
        return None
    line = row.get("line")
    if line is None:
        return None
    try:
        return float(line)
    except (TypeError, ValueError):
        return None


def intelligence_from_prop_rows(
    rows: list[dict],
    dfs_players: list[dict],
    *,
    event_date: Optional[str] = None,
) -> dict[str, dict]:
    """Name-match DFS players to Odds API over lines. Uses the listed O/U line, not a fabricated EV."""
    from dfs.name_normalize import fold_player_name

    by_name: dict[str, dict] = {}
    for row in rows or []:
        if event_date:
            commence = _commence_date_et(row.get("commence_time"))
            if commence and commence != event_date:
                continue
        prop_key = ODDSAPI_MARKET_TO_PROP.get(str(row.get("market") or ""))
        if not prop_key:
            continue
        line = _over_line(row)
        if line is None:
            continue
        pname = fold_player_name(row.get("player") or "")
        if not pname:
            continue
        entry = by_name.setdefault(pname, {"props": {}, "fantasyScore": None})
        existing = entry["props"].get(prop_key)
        if existing is None or abs(line) > abs(existing):
            entry["props"][prop_key] = line

    result: dict[str, dict] = {}
    for player in dfs_players:
        pid = str(player.get("id") or "")
        name = fold_player_name(player.get("name") or "")
        if not pid or not name:
            continue
        hit = by_name.get(name)
        if hit and hit.get("props"):
            result[pid] = {
                "props": dict(hit["props"]),
                "fantasyMarketLine": None,
                "fantasyScore": None,
                "source": "oddsapi_player_props",
            }
    return result


def build_oddsapi_intelligence(
    sport: str,
    dfs_players: list[dict],
    event_date: Optional[str] = None,
) -> dict[str, dict]:
    from market_snapshot.cache import public_preview

    preview = public_preview()
    if preview.get("unavailable"):
        return {}
    return intelligence_from_prop_rows(
        list(preview.get("player_props") or []),
        dfs_players,
        event_date=event_date,
    )
