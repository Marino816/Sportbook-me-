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
from dfs.name_normalize import fold_player_name
from dfs.team_normalize import normalize_team_abbr, teams_equivalent

logger = logging.getLogger(__name__)

# Team abbreviation mapping: DK abbreviation → full name keywords
TEAM_NAME_MAP = {
    # MLB
    "ATL": "braves", "ARI": "diamondbacks", "BAL": "orioles", "BOS": "red sox",
    "CHC": "cubs", "CHW": "white sox", "CIN": "reds", "CLE": "guardians",
    "COL": "rockies", "DET": "tigers", "HOU": "astros", "KC": "royals",
    "LAA": "angels", "LAD": "dodgers", "MIA": "marlins", "MIL": "brewers",
    "MIN": "twins", "NYM": "mets", "NYY": "yankees", "OAK": "athletics",
    "ATH": "athletics", "CWS": "white sox",
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
    """Normalize player name for comparison (case, whitespace, accents)."""
    return fold_player_name(name)


def _looks_like_team_abbr(value: str) -> bool:
    raw = (value or "").strip()
    return 2 <= len(raw) <= 3 and raw.isalpha()


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
    dfs_team = normalize_team_abbr(dfs_player.team)

    best_id = None
    best_score = 0.0

    for sgo in sgo_players:
        sgo_name = _normalize_name(sgo.get("name", "") or sgo.get("playerName", ""))
        sgo_team_raw = (sgo.get("teamAbbrev") or sgo.get("team") or "").strip()
        sgo_team = normalize_team_abbr(sgo_team_raw) if _looks_like_team_abbr(sgo_team_raw) else ""

        # Team must match when both sides have a real abbreviation.
        # Non-abbr values (SGO teamIDs) are treated as unknown, not as a mismatch.
        if sgo_team and dfs_team and not teams_equivalent(sgo_team, dfs_team):
            team_keywords = TEAM_NAME_MAP.get(dfs_team, dfs_team.lower())
            team_name = (sgo.get("teamName", "") or "").lower()
            if team_keywords not in team_name:
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


def apply_mapping_to_row(dbp, sgo_id: str | None, confidence: float) -> str:
    """Write mapping onto a DFSPlayer ORM row. Never force uncertain matches."""
    if sgo_id and confidence >= 0.95:
        dbp.mapping_status = "MATCHED"
        dbp.sbme_player_id = sgo_id
        dbp.mapping_confidence = confidence
        return "MATCHED"
    if sgo_id and confidence >= 0.85:
        dbp.mapping_status = "REVIEW_REQUIRED"
        dbp.sbme_player_id = sgo_id
        dbp.mapping_confidence = confidence
        return "REVIEW_REQUIRED"
    dbp.mapping_status = "UNMATCHED"
    dbp.sbme_player_id = None
    dbp.mapping_confidence = 0.0
    return "UNMATCHED"


def merge_reconciliation_report(existing, stats: dict) -> dict:
    """Merge mapping stats into slate.reconciliation_report without dropping BC metadata."""
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(stats)
    return merged


async def load_sgo_player_dicts(sport: str) -> list[dict]:
    """Best-effort SGO player list for reconciliation (name + team abbreviation)."""
    players: list[dict] = []
    try:
        from providers.sdk_provider import SdkSgoProvider
        events = await SdkSgoProvider().get_sb_events(sport)
        for evt in events or []:
            home = getattr(evt, "home_team", None)
            away = getattr(evt, "away_team", None)
            home_id = getattr(home, "team_id", "") or ""
            away_id = getattr(away, "team_id", "") or ""
            home_abbr = normalize_team_abbr(getattr(home, "abbreviation", "") or "")
            away_abbr = normalize_team_abbr(getattr(away, "abbreviation", "") or "")
            for sp in getattr(evt, "players", None) or []:
                pid = getattr(sp, "player_id", None) or getattr(sp, "id", None)
                name = getattr(sp, "name", "") or ""
                if not pid or not name:
                    continue
                team_id = getattr(sp, "team_id", "") or ""
                if team_id and away_id and team_id.upper() == str(away_id).upper():
                    team = away_abbr
                else:
                    team = home_abbr
                players.append({
                    "id": str(pid),
                    "playerID": str(pid),
                    "name": name,
                    "team": team,
                    "teamAbbrev": team,
                    "position": getattr(sp, "position", "") or "",
                })
    except Exception as e:
        logger.warning("SGO player load for reconciliation failed: %s", e)
    seen = set()
    unique = []
    for p in players:
        if p["playerID"] not in seen:
            seen.add(p["playerID"])
            unique.append(p)
    return unique


def reconcile_db_players(db_players, sgo_players: list[dict]) -> dict:
    """Apply reconcile_player to ORM DFSPlayer rows. Returns mapping stats."""
    matched = review = unmatched = 0
    for dbp in db_players:
        dp = DFSContestPlayer(
            platform="",
            player_id=dbp.provider_player_id or "",
            player_name=dbp.player_name or "",
            team=dbp.team or "",
            opponent=dbp.opponent or "",
            position=dbp.position or "",
            salary=dbp.salary or 0,
        )
        sgo_id = reconcile_player(dp, sgo_players)
        status = apply_mapping_to_row(dbp, sgo_id, dp.sbme_confidence)
        if status == "MATCHED":
            matched += 1
        elif status == "REVIEW_REQUIRED":
            review += 1
        else:
            unmatched += 1
    return {
        "matched": matched,
        "review": review,
        "unmatched": unmatched,
        "total": len(db_players),
        "sgo_pool_size": len(sgo_players),
    }