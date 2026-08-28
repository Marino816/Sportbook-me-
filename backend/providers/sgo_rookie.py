"""SportsGameOdds Rookie-tier constants and pure helpers.

Confirmed against live GET /v2/account/usage and GET /v2/leagues/ for
credential …0b5a (tier=rookie, 17 enabled leagues). Do not treat Amateur
rate limits as the product default.
"""

from __future__ import annotations

from typing import Any, Optional

# Rookie update frequency is ~3 minutes. Nested event cache TTL matches that.
NESTED_EVENT_TTL_SECONDS = 180

# Confirmed 17 enabled Rookie leagues (live /v2/leagues/, 2026-08-28).
ROOKIE_LEAGUES: tuple[dict[str, str], ...] = (
    {"leagueID": "MLB", "name": "MLB", "shortName": "MLB", "sportID": "BASEBALL"},
    {"leagueID": "NBA", "name": "NBA", "shortName": "NBA", "sportID": "BASKETBALL"},
    {"leagueID": "NCAAB", "name": "College Basketball", "shortName": "NCAAB", "sportID": "BASKETBALL"},
    {"leagueID": "WNBA", "name": "WNBA", "shortName": "WNBA", "sportID": "BASKETBALL"},
    {"leagueID": "NCAAF", "name": "College Football", "shortName": "NCAAF", "sportID": "FOOTBALL"},
    {"leagueID": "NFL", "name": "NFL", "shortName": "NFL", "sportID": "FOOTBALL"},
    {"leagueID": "EHF_EURO", "name": "EHF European League", "shortName": "EHF", "sportID": "HANDBALL"},
    {"leagueID": "NHL", "name": "NHL", "shortName": "NHL", "sportID": "HOCKEY"},
    {"leagueID": "UFC", "name": "UFC", "shortName": "UFC", "sportID": "MMA"},
    {"leagueID": "BUNDESLIGA", "name": "Bundesliga", "shortName": "Bundesliga", "sportID": "SOCCER"},
    {"leagueID": "EPL", "name": "Premier League", "shortName": "EPL", "sportID": "SOCCER"},
    {"leagueID": "FR_LIGUE_1", "name": "Ligue 1", "shortName": "Ligue 1", "sportID": "SOCCER"},
    {"leagueID": "INTERNATIONAL_SOCCER", "name": "International Soccer", "shortName": "Intl Soccer", "sportID": "SOCCER"},
    {"leagueID": "IT_SERIE_A", "name": "Serie A", "shortName": "Serie A", "sportID": "SOCCER"},
    {"leagueID": "LA_LIGA", "name": "La Liga", "shortName": "La Liga", "sportID": "SOCCER"},
    {"leagueID": "MLS", "name": "MLS", "shortName": "MLS", "sportID": "SOCCER"},
    {"leagueID": "UEFA_CHAMPIONS_LEAGUE", "name": "Champions League", "shortName": "UCL", "sportID": "SOCCER"},
)

ROOKIE_LEAGUE_IDS: tuple[str, ...] = tuple(row["leagueID"] for row in ROOKIE_LEAGUES)

SOCCER_LEAGUE_IDS: tuple[str, ...] = tuple(
    row["leagueID"] for row in ROOKIE_LEAGUES if row["sportID"] == "SOCCER"
)

LEAGUE_ALIASES: dict[str, str] = {
    "UCL": "UEFA_CHAMPIONS_LEAGUE",
    "CHAMPIONS_LEAGUE": "UEFA_CHAMPIONS_LEAGUE",
    "UEFA": "UEFA_CHAMPIONS_LEAGUE",
    "LIGUE_1": "FR_LIGUE_1",
    "LIGUE1": "FR_LIGUE_1",
    "SERIE_A": "IT_SERIE_A",
    "SERIEA": "IT_SERIE_A",
    "LALIGA": "LA_LIGA",
    "PREMIER_LEAGUE": "EPL",
    "PREMIER": "EPL",
    "INTL_SOCCER": "INTERNATIONAL_SOCCER",
    "INTERNATIONAL": "INTERNATIONAL_SOCCER",
}

FULL_GAME_PERIODS = frozenset({"", "game", "ft", "full", "regulation"})

# SGO playerIDs end with _{leagueID}. Include every Rookie league suffix.
SGO_ID_SPORT_SUFFIXES: tuple[str, ...] = tuple(f"_{lid}" for lid in ROOKIE_LEAGUE_IDS)


def normalize_league_id(league: str | None) -> str:
    raw = (league or "MLB").strip().upper().replace(" ", "_").replace("-", "_")
    if raw in LEAGUE_ALIASES:
        return LEAGUE_ALIASES[raw]
    return raw


def is_rookie_league(league: str | None) -> bool:
    return normalize_league_id(league) in ROOKIE_LEAGUE_IDS


def is_soccer_league(league: str | None) -> bool:
    return normalize_league_id(league) in SOCCER_LEAGUE_IDS


def is_full_game_period(period_id: str | None) -> bool:
    return (period_id or "").strip().lower() in FULL_GAME_PERIODS


def parse_american(val) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(str(val).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def parse_float(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def classify_sgo_market(
    *,
    odd_id: str = "",
    stat_entity_id: str = "",
    player_id: str = "",
    bet_type_id: str = "",
    stat_id: str = "",
    period_id: str = "",
) -> str:
    """Classify a nested oddID into SB ME bet_type.

    Team totals (over/under with statEntity home/away) are team_prop.
    Game totals use statEntity all (or empty) with betType ou.
    Period is stored separately — 1H moneyline is still moneyline.
    """
    oid = (odd_id or "").lower()
    parts = (odd_id or "").split("-")
    seid = (stat_entity_id or "").strip()
    seid_l = seid.lower()
    pid = (player_id or "").strip()
    bt = (bet_type_id or "").lower()
    if not bt and len(parts) >= 4:
        bt = parts[3].lower()

    if pid or (seid and seid_l not in ("home", "away", "all")):
        return "player_prop"

    if bt == "ml" or "moneyline" in oid:
        return "moneyline"
    if bt == "sp" or "spread" in oid or "handicap" in oid:
        return "spread"
    if bt in ("ou",) or "total" in oid:
        if seid_l in ("home", "away"):
            return "team_prop"
        return "total"
    if seid_l in ("home", "away"):
        return "team_prop"
    return "other"


def _as_dict(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        try:
            return dump(by_alias=False) or {}
        except TypeError:
            return dump() or {}
    to_dict = getattr(raw, "dict", None)
    if callable(to_dict):
        try:
            return to_dict() or {}
        except TypeError:
            return {}
    out = {}
    for name in dir(raw):
        if name.startswith("_"):
            continue
        try:
            val = getattr(raw, name)
        except Exception:
            continue
        if callable(val):
            continue
        out[name] = val
    return out


def parse_account_usage(raw: Any) -> dict:
    """Normalize /v2/account/usage. Never includes email, keyID, or customerID."""
    payload = _as_dict(raw)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}
    rate = data.get("rateLimits") or data.get("rate_limits") or {}
    if hasattr(rate, "model_dump"):
        rate = _as_dict(rate)
    if not isinstance(rate, dict):
        rate = {}
    used = rate.get("current-entities") or rate.get("current_entities")
    monthly_limit = rate.get("objects-per-month") or rate.get("objects_per_month")
    remaining = None
    pct = None
    try:
        if used is not None and monthly_limit:
            remaining = max(0, int(monthly_limit) - int(used))
            pct = round(100.0 * int(used) / int(monthly_limit), 2) if int(monthly_limit) else None
    except (TypeError, ValueError):
        remaining = None
        pct = None
    return {
        "available": True,
        "success": payload.get("success", True),
        "tier": data.get("tier"),
        "is_active": data.get("isActive", data.get("is_active")),
        "rate_limits": rate,
        "monthly_limit": monthly_limit,
        "used": used,
        "remaining": remaining,
        "percent_used": pct,
        "source": "sportsgameodds_v2_account_usage",
    }


def catalog_fallback() -> list[dict]:
    """Static confirmed Rookie catalog used when /v2/leagues/ is unreachable."""
    return [
        {**row, "enabled": True, "source": "rookie_catalog_fallback"}
        for row in ROOKIE_LEAGUES
    ]
