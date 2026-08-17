"""
Build SGO intelligence dicts for the native projection engine from cached
SBEvent data. Extracts player prop values (expected hits, home runs, RBI,
strikeouts, etc.) from SGO market over/under lines via fair_over_under.

Used by router.py before compute_projections to replace the 0.01 placeholder
with real, SGO-derived projection data.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Market-to-prop key mapping (same as populate_sgo_intelligence.py).
# Order matters: more specific patterns must come before generic substrings.
PROP_KEY_MAP = {
    "hits": "hits",
    "totalhits": "hits",
    "homeruns": "homeRuns",
    "home_run": "homeRuns",
    "home_runs": "homeRuns",
    "rbi": "rbi",
    "runsbattedin": "rbi",
    "runs_batted_in": "rbi",
    "totalbases": "totalBases",
    "total_bases": "totalBases",
    "stolenbases": "stolenBases",
    "stolen_base": "stolenBases",
    "basesonballs": "walks",
    "bases_on_balls": "walks",
    "pitchingstrikeouts": "pitchingStrikeouts",
    "pitcherstrikeouts": "pitchingStrikeouts",
    "pitcher_strikeouts": "pitchingStrikeouts",
    "battingstrikeouts": "battingStrikeouts",
    "strikeouts": "battingStrikeouts",
    "pitchingouts": "pitchingOuts",
    "pitcherouts": "pitchingOuts",
    "pitching_outs": "pitchingOuts",
    "earnedruns": "pitchingEarnedRuns",
    "pitchingearnedruns": "pitchingEarnedRuns",
    "earned_runs": "pitchingEarnedRuns",
    "hitsallowed": "pitchingHits",
    "pitchinghits": "pitchingHits",
    "pitching_hits": "pitchingHits",
    "pitchingwalks": "pitchingWalks",
    "walksallowed": "pitchingWalks",
    "walks_allowed": "pitchingWalks",
    "walks": "walks",
}


def _norm_name(n: str) -> str:
    """Normalize a player name for case-insensitive matching."""
    return (n or "").strip().lower()


def _market_to_prop_key(market_name: str, stat_id: str) -> Optional[str]:
    """Map an SGO market name or stat_id to our internal prop key."""
    candidates = [
        (market_name or "").lower(),
        (stat_id or "").lower(),
    ]
    for raw in candidates:
        clean = raw.replace(" ", "").replace("_", "").replace("-", "")
        for pattern, key in PROP_KEY_MAP.items():
            if pattern in clean:
                return key
    return None


async def build_sgo_intelligence(sport: str, dfs_players: list[dict], event_date: Optional[str] = None) -> dict[str, dict]:
    """
    Build a sgo_intelligence dict keyed by DFS player ID.

    Reads cached SGO SBEvent dicts from Redis for the given sport, then
    name-matches DFS players to SGO market data and extracts prop values
    from fair_over_under lines. Falls back to a live SDK fetch on cache miss
    so /optimize never silently degrades to the 0.01 placeholder.

    Returns {dfs_player_id: {"props": {"hits": 1.2, ...}, "fantasyScore": ...}}
    """
    sport_upper = sport.upper()

    # Read cached SBEvent data
    from api.sgo_data import _rget
    cache_key = f"sgo:v2:sbevents:{sport_upper}"
    events = _rget(cache_key)

    if not events or not isinstance(events, list):
        logger.info("No cached SGO events for %s — fetching live SDK events.", sport_upper)
        try:
            from api.sgo_data import _canonical_event_provider, _sb_event_to_dict
            sb_events = await _canonical_event_provider().get_sb_events(sport_upper)
            events = [_sb_event_to_dict(e) for e in (sb_events or [])]
        except Exception as exc:
            logger.warning("Live SGO fetch failed for %s: %s", sport_upper, exc)
            return {}

    if not events or not isinstance(events, list):
        return {}

    # DATE-SAFE enrichment: when a slate date is supplied, restrict to events
    # whose start_time falls on that date so a stale DFS salary slate is never
    # enriched with current/upcoming SGO market data from a different game day.
    if event_date:
        before = len(events)
        events = [
            e for e in events
            if isinstance(e, dict) and (e.get("start_time") or "").startswith(event_date)
        ]
        logger.info(
            "SGO intelligence date filter %s: %d -> %d events",
            event_date, before, len(events),
        )
        if not events:
            logger.warning(
                "SGO intelligence: no events match slate date %s — enrichment skipped (date-safe).",
                event_date,
            )
            return {}

    # Build SGO player_name → {props, fantasyScore}
    sgo_by_name: dict[str, dict] = {}

    for evt in events:
        try:
            markets = evt.get("markets", [])
            if not isinstance(markets, list):
                continue

            for m in markets:
                pname = m.get("player_name", "").strip()
                if not pname:
                    continue

                key = _norm_name(pname)
                if key not in sgo_by_name:
                    sgo_by_name[key] = {"props": {}, "fantasyScore": None}

                entry = sgo_by_name[key]

                # Check for fantasyScore market
                mkt_name = (m.get("market_name") or "").lower()
                if "fantasy" in mkt_name:
                    fu = m.get("fair_over_under")
                    if fu is not None:
                        try:
                            entry["fantasyScore"] = float(fu)
                            entry["fantasyMarketLine"] = float(fu)
                        except (ValueError, TypeError):
                            pass
                    continue

                # Extract prop value from fair_over_under
                fu = m.get("fair_over_under")
                if fu is None:
                    # Also try fair_spread for some markets
                    fu = m.get("fair_spread")
                if fu is None:
                    continue

                try:
                    val = float(fu)
                except (ValueError, TypeError):
                    continue

                # Map to prop key
                prop_key = _market_to_prop_key(
                    m.get("market_name", ""),
                    m.get("stat_id", ""),
                )
                if not prop_key:
                    continue

                # For over/under props, the line IS the expected value
                # (market median ≈ expected value for symmetric distributions).
                # Store the best (highest absolute) value across books.
                existing = entry["props"].get(prop_key)
                if existing is None or abs(val) > abs(existing):
                    entry["props"][prop_key] = val

        except Exception:
            continue

    logger.info(
        "SGO intelligence: %d name-matched players from %d events for %s",
        len(sgo_by_name), len(events), sport_upper,
    )

    if not sgo_by_name:
        return {}

    # Match DFS players to SGO by name, key by DFS player ID
    result: dict[str, dict] = {}
    for p in dfs_players:
        pid = str(p.get("id") or "")
        name = _norm_name(p.get("name") or "")
        if not pid or not name:
            continue
        sgo = sgo_by_name.get(name)
        if sgo and (sgo.get("props") or sgo.get("fantasyScore")):
            result[pid] = {
                "props": sgo["props"],
                "fantasyMarketLine": sgo.get("fantasyScore"),
                "fantasyScore": sgo.get("fantasyScore"),
            }

    logger.info(
        "SGO intelligence matched: %d/%d DFS players enriched",
        len(result), len(dfs_players),
    )
    return result