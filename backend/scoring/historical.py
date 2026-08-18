"""
Historical game-log builder — fetches SGO events and scores them.

Separate from projection/native.py.  Uses the MLBScorekeeper for
per-game stat→FP computation, then aggregates into a PlayerGameLog.
"""

from __future__ import annotations

import logging
from typing import Optional

from scoring.models import (
    GameScore,
    PlayerGameLog,
    ScoringPlatform,
    PlayerRole,
    ScoringMode,
)
from scoring.mlb import MLBScorekeeper, _detect_role

logger = logging.getLogger(__name__)


async def build_game_log(
    events: list[dict],
    player_id: str,
    *,
    platform: ScoringPlatform = ScoringPlatform.DRAFTKINGS,
    n: int = 5,
) -> Optional[PlayerGameLog]:
    """Build a last-N game log from a list of finalized SGO events.

    *events* must be SGO /v2/events responses with include=results —
    each dict contains results.game.{playerID} stat objects.

    Returns None when the player is not found in any event.
    """
    keeper = MLBScorekeeper(platform=platform)
    player_games: list[GameScore] = []
    player_name = ""

    for ev in events:
        # Extract event-level context
        starts_at = _safe_str(ev, "status.startsAt", "")[:10]
        event_id = ev.get("eventID", "")
        home_short = _safe_str(ev, "teams.home.names.short", "???")
        away_short = _safe_str(ev, "teams.away.names.short", "???")
        home_score = ev.get("teams", {}).get("home", {}).get("score", 0) or 0
        away_score = ev.get("teams", {}).get("away", {}).get("score", 0) or 0
        status = ev.get("status", {})

        # Player info
        players_map = ev.get("players", {})
        player_info = players_map.get(player_id, {})
        if not player_name and player_info:
            player_name = player_info.get("name", player_info.get("firstName", player_id))

        # Game stats
        game = ev.get("results", {}).get("game", {})
        if not isinstance(game, dict):
            continue

        sgo_stats = game.get(player_id)
        if not isinstance(sgo_stats, dict):
            continue

        # Determine opponent / home-away
        player_team = player_info.get("teamID", "")
        home_team_id = _safe_str(ev, "teams.home.teamID", "")
        is_home = player_team == home_team_id
        opponent = away_short if is_home else home_short
        home_away = "home" if is_home else "away"

        # Build event_status enriched with game-level score for CGSO derivation
        enriched_status = dict(status)
        enriched_status["_opponent_score"] = away_score if is_home else home_score

        result = keeper.score(sgo_stats, event_status=enriched_status)

        player_games.append(GameScore(
            date=starts_at,
            event_id=event_id,
            opponent=opponent,
            home_away=home_away,
            result=result,
        ))

        # Keep only the most recent N
        player_games.sort(key=lambda g: g.date)
        if len(player_games) > n:
            player_games = player_games[-n:]

    if not player_games:
        return None

    # Aggregate
    fps = [g.result.fantasy_points for g in player_games]
    avg_fp = round(sum(fps) / len(fps), 1) if fps else 0.0

    all_exact = all(g.result.is_exact for g in player_games)
    global_missing = sorted(set(
        f for g in player_games for f in g.result.missing_fields
    ))

    # Overall scoring mode
    if all_exact:
        mode = ScoringMode.HISTORICAL_EXACT
    else:
        mode = ScoringMode.HISTORICAL_PARTIAL

    return PlayerGameLog(
        player_id=player_id,
        player_name=player_name or player_id,
        platform=platform.value,
        sport="MLB",
        player_role=player_games[0].result.player_role.value,
        scoring_mode=mode.value,
        n=n,
        games=player_games,
        average_fp=avg_fp,
        min_fp=min(fps) if fps else 0.0,
        max_fp=max(fps) if fps else 0.0,
        average_is_exact=all_exact,
        global_missing_fields=global_missing,
    )


def _safe_str(obj: dict, dotted: str, default: str = "") -> str:
    """Drill into a nested dict by dotted path, returning str or default."""
    cur = obj
    for key in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key, default)
        else:
            return default
    return str(cur) if cur is not None else default