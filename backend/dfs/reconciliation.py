"""
Player reconciliation between DFS contest data and SportsGameOdds.

Maps DK/FD player names/teams to SGO player IDs using
deterministic name + team matching. Never silently merges ambiguous players.
"""

from __future__ import annotations
import logging
from difflib import SequenceMatcher
from typing import Optional

from dfs.models import DFSContestPlayer

logger = logging.getLogger(__name__)

# Team abbreviation mapping: DK abbreviation → full name keywords
TEAM_NAME_MAP = {
    # MLB
    "ATL": "braves", "ARI": "diamondbacks", "BAL": "orioles", "BOS": "red sox",
    "CHC": "cubs", "CHW": "white sox", "CIN": "reds", "CLE": "guardians",
    "COL": "rockies", "DET": "tigers", "HOU": "astros", "KC": "royals",
    "LAA": "angels", "LAD": "dodgers", "MIA": "marlins", "MIL": "brewers",
    "MIN": "twins", "NYM": "mets", "NYY": "yankees", "OAK": "athletics",
    "PHI": "phillies", "PIT": "pirates", "SD": "padres", "SF": "giants",
    "SEA": "mariners", "STL": "cardinals", "TB": "rays", "TEX": "rangers",
    "TOR": "blue jays", "WSH": "nationals",
    # NFL
    "SF": "49ers", "GB": "packers", "KC": "chiefs", "DAL": "cowboys",
    "NE": "patriots", "PHI": "eagles", "BUF": "bills", "CIN": "bengals",
    "BAL": "ravens", "PIT": "steelers", "NYG": "giants", "NYJ": "jets",
    "MIA": "dolphins", "LV": "raiders", "LAC": "chargers", "LAR": "rams",
    "DEN": "broncos", "MIN": "vikings", "DET": "lions", "CHI": "bears",
    "TB": "buccaneers", "NO": "saints", "HOU": "texans", "ATL": "falcons",
    "CAR": "panthers", "JAX": "jaguars", "CLE": "browns", "WAS": "commanders",
    "TEN": "titans", "SEA": "seahawks", "ARI": "cardinals", "IND": "colts",
    # NBA
    "BOS": "celtics", "LAL": "lakers", "GSW": "warriors", "MIL": "bucks",
    "DEN": "nuggets", "PHX": "suns", "MIA": "heat",
}


def _normalize_name(name: str) -> str:
    """Normalize player name for comparison."""
    return " ".join(name.lower().strip().split())


def _name_similarity(a: str, b: str) -> float:
    """Compute string similarity between two names."""
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def reconcile_player(
    dfs_player: DFSContestPlayer,
    sgo_players: list[dict],
    min_confidence: float = 0.85,
) -> Optional[str]:
    """
    Match a DFS player to an SGO player ID.

    Strategy:
      1. Exact name + team match → confidence=1.0
      2. High-similarity name (>0.90) + same team → confidence=0.90
      3. Partial name match (first+last appear) + same team → confidence=0.85
      4. Below threshold → return None (ambiguous — no match)

    Never returns a low-confidence match. Caller must handle None.
    """
    dfs_name = _normalize_name(dfs_player.player_name)
    dfs_team = dfs_player.team.upper().strip()

    best_id = None
    best_score = 0.0

    for sgo in sgo_players:
        sgo_name = _normalize_name(sgo.get("name", "") or sgo.get("playerName", ""))
        sgo_team = (sgo.get("teamAbbrev") or sgo.get("team") or "").upper().strip()

        # Team must match (or SGO team field unknown)
        team_match = not sgo_team or not dfs_team or sgo_team == dfs_team
        if not team_match:
            team_keywords = TEAM_NAME_MAP.get(dfs_team, dfs_team.lower())
            if team_keywords not in (sgo.get("teamName", "") or "").lower():
                continue

        # Exact name match
        if dfs_name == sgo_name:
            best_id = sgo.get("id") or sgo.get("playerID")
            best_score = 1.0
            break

        # High similarity
        sim = _name_similarity(dfs_name, sgo_name)
        if sim > best_score and sim >= 0.90:
            best_id = sgo.get("id") or sgo.get("playerID")
            best_score = sim

    if best_score >= 0.90 and best_id:
        dfs_player.sbme_player_id = str(best_id)
        dfs_player.sbme_confidence = min(best_score, 1.0)
        return str(best_id)

    if best_score >= min_confidence and best_id:
        logger.info(f"Partial match: {dfs_player.player_name} → SGO {best_id} (score={best_score:.2f})")
        dfs_player.sbme_player_id = str(best_id)
        dfs_player.sbme_confidence = best_score
        return str(best_id)

    dfs_player.sbme_confidence = 0.0
    logger.debug(f"No SGO match for {dfs_player.player_name} ({dfs_team})")
    return None


def reconcile_all(
    dfs_players: list[DFSContestPlayer],
    sgo_players: list[dict],
) -> dict[str, int]:
    """
    Batch reconcile all DFS players to SGO player IDs.
    Returns stats: {matched, unmatched, total, high_conf, partial}.
    """
    stats = {"matched": 0, "unmatched": 0, "total": len(dfs_players),
              "high_conf": 0, "partial": 0}

    for dp in dfs_players:
        result = reconcile_player(dp, sgo_players)
        if result:
            stats["matched"] += 1
            if dp.sbme_confidence >= 0.95:
                stats["high_conf"] += 1
            else:
                stats["partial"] += 1
        else:
            stats["unmatched"] += 1

    return stats