"""
Sport-specific market adapters for SB ME Intelligence Engine.

Each adapter maps SGO prop markets to SB ME normalized signals.
Unsupported sports return UNCONFIGURED gracefully.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════
#  Sport Market Definitions
# ══════════════════════════════════════════════════════════════

SPORT_MARKETS = {
    "MLB": {
        "hitting": [
            "fantasyScore", "hits", "homeRuns", "rbi", "totalBases",
            "stolenBases", "battingStrikeouts", "walks",
        ],
        "pitching": [
            "pitchingStrikeouts", "pitchingOuts", "pitchingHits",
            "pitchingEarnedRuns", "pitchingWalks",
        ],
        "game_totals": ["total", "spread", "moneyline"],
        "player_count": 10,  # DK roster size reference
    },
    "NFL": {
        "offense": [
            "fantasyScore", "passingYards", "rushingYards", "receivingYards",
            "passingTouchdowns", "rushingTouchdowns", "receivingTouchdowns",
            "receptions", "completions", "interceptions",
            "rushingAttempts", "totalYards",
        ],
        "defense": [
            "tackles", "sacks", "interceptionsDefense",
            "forcedFumbles", "defensiveTouchdowns",
        ],
        "special_teams": [
            "fieldGoals", "extraPoints",
        ],
        "game_totals": ["total", "spread", "moneyline"],
        "player_count": 9,
    },
    "NBA": {
        "offense": [
            "fantasyScore", "points", "rebounds", "assists",
            "threePointersMade", "pointsReboundsAssists",
            "blocks", "steals",
        ],
        "game_totals": ["total", "spread", "moneyline"],
        "player_count": 8,
    },
    "NHL": {
        "offense": [
            "fantasyScore", "goals", "assists", "points",
            "shotsOnGoal", "blocks",
        ],
        "goalie": [
            "goalieSaves", "goalieGoalsAgainst",
        ],
        "game_totals": ["total", "puckline", "moneyline"],
        "player_count": 8,
    },
    "NCAAF": {
        "offense": [
            "fantasyScore", "passingYards", "rushingYards", "receivingYards",
            "passingTouchdowns", "rushingTouchdowns", "receivingTouchdowns",
            "totalYards",
        ],
        "game_totals": ["total", "spread", "moneyline"],
        "player_count": 8,
    },
    "NCAAB": {
        "offense": [
            "fantasyScore", "points", "rebounds", "assists",
            "threePointersMade", "pointsReboundsAssists",
        ],
        "game_totals": ["total", "spread", "moneyline"],
        "player_count": 8,
    },
    "UFC": {
        "offense": ["fantasyScore", "significantStrikes", "takedowns",
                     "submissionAttempts", "knockdowns"],
        "fight_totals": ["totalRounds", "fightGoesDistance"],
        "player_count": 5,
    },
}


# ══════════════════════════════════════════════════════════════
#  SGO Market Name Aliases (SGO → SB ME normalized)
# ══════════════════════════════════════════════════════════════

SGO_MARKET_ALIASES = {
    # MLB
    "fantasyScore": "fantasyScore",
    "fantasy_points": "fantasyScore",
    "dfsPoints": "fantasyScore",
    "hits": "hits",
    "totalHits": "hits",
    "homeRuns": "homeRuns",
    "home_runs": "homeRuns",
    "hr": "homeRuns",
    "rbi": "rbi",
    "runsBattedIn": "rbi",
    "totalBases": "totalBases",
    "stolenBases": "stolenBases",
    "stolen_bases": "stolenBases",
    "sb": "stolenBases",
    "battingStrikeouts": "battingStrikeouts",
    "batter strikeouts": "battingStrikeouts",
    "hitter strikeouts": "battingStrikeouts",
    "walks": "walks",
    "basesOnBalls": "walks",
    "pitchingStrikeouts": "pitchingStrikeouts",
    "pitcherStrikeouts": "pitchingStrikeouts",
    "strikeouts": "pitchingStrikeouts",
    "pitchingOuts": "pitchingOuts",
    "outs": "pitchingOuts",
    "pitchingHits": "pitchingHits",
    "pitchingEarnedRuns": "pitchingEarnedRuns",
    "earnedRuns": "pitchingEarnedRuns",
    "er": "pitchingEarnedRuns",
    "pitchingWalks": "pitchingWalks",
    # NFL
    "passingYards": "passingYards",
    "passing_yards": "passingYards",
    "receivingYards": "receivingYards",
    "receiving_yards": "receivingYards",
    "rushingYards": "rushingYards",
    "rushing_yards": "rushingYards",
    "passingTouchdowns": "passingTouchdowns",
    "passing_tds": "passingTouchdowns",
    "rushingTouchdowns": "rushingTouchdowns",
    "receivingTouchdowns": "receivingTouchdowns",
    "receptions": "receptions",
    "interceptions": "interceptions",
    "tackles": "tackles",
    "sacks": "sacks",
    "fieldGoals": "fieldGoals",
    "extraPoints": "extraPoints",
    "totalYards": "totalYards",
    # NBA
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threePointersMade": "threePointersMade",
    "three_pointers": "threePointersMade",
    "pointsReboundsAssists": "pointsReboundsAssists",
    "pra": "pointsReboundsAssists",
    "blocks": "blocks",
    "steals": "steals",
    # NHL
    "goals": "goals",
    "assists_nhl": "assists",
    "shotsOnGoal": "shotsOnGoal",
    "goalieSaves": "goalieSaves",
    "goalieGoalsAgainst": "goalieGoalsAgainst",
    # UFC
    "significantStrikes": "significantStrikes",
    "takedowns": "takedowns",
    "knockdowns": "knockdowns",
    "totalRounds": "totalRounds",
    "fightGoesDistance": "fightGoesDistance",
}


def resolve_market(raw_name: str) -> str | None:
    """Resolve an SGO market name to SB ME normalized key."""
    key = str(raw_name).strip()
    # Try exact match first
    if key in SGO_MARKET_ALIASES:
        return SGO_MARKET_ALIASES[key]
    # Try lowercase
    lk = key.lower().replace(" ", "").replace("_", "")
    for alias, normalized in SGO_MARKET_ALIASES.items():
        if alias.lower().replace(" ", "").replace("_", "") == lk:
            return normalized
    return None


def get_sport_markets(sport: str) -> dict:
    """Get market definitions for a sport. Returns empty dict if unconfigured."""
    return SPORT_MARKETS.get(sport.upper(), {})