"""Canonical nested /v2/events helpers — cache-first, no dedicated SGO URLs.

Customer market tools, implied environment, research props, and SB ME AI
read this layer. Dedicated /odds/{id}, /props, /fair-odds, /consensus paths
are not used here.
"""

from __future__ import annotations

import logging
from statistics import median
from typing import Optional

from dfs.name_normalize import fold_player_name
from dfs.team_normalize import normalize_team_abbr, teams_equivalent

logger = logging.getLogger(__name__)

RESEARCH_PROP_MAP = (
    ("hits", "hits_line"),
    ("homeruns", "hr_line"),
    ("home_run", "hr_line"),
    ("pitchingstrikeouts", "strikeouts_line"),
    ("pitcherstrikeouts", "strikeouts_line"),
    ("pitcher_strikeouts", "strikeouts_line"),
)

SGO_ID_SPORT_SUFFIXES = ("_MLB", "_NFL", "_NBA", "_NHL", "_NCAAF", "_NCAAB")


def looks_like_sgo_player_id(player_id: str | None) -> bool:
    """True only for confirmed SGO playerID shape (sport suffix).

    DraftKings / FanDuel / Blue Collar site IDs are never treated as SGO IDs
    just because they contain digits or underscores.
    """
    raw = (player_id or "").strip()
    if not raw or " " in raw:
        return False
    upper = raw.upper()
    return any(upper.endswith(suf) for suf in SGO_ID_SPORT_SUFFIXES)


def american_implied_prob(american: int | float | None) -> Optional[float]:
    if american is None:
        return None
    try:
        a = int(american)
    except (TypeError, ValueError):
        return None
    if a > 0:
        return 100.0 / (a + 100.0)
    if a < 0:
        return abs(a) / (abs(a) + 100.0)
    return 0.5


def _median(values: list[float]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return float(median(nums))


def load_cached_events(league: str) -> list[dict]:
    """Redis-only. Never hits SGO. Empty list on miss."""
    from api.sgo_data import _rget

    data = _rget(f"sgo:v2:sbevents:{(league or 'MLB').upper()}")
    return data if isinstance(data, list) else []


async def load_cached_or_fetch_events(league: str, *, allow_fetch: bool = True) -> list[dict]:
    """Return nested SBEvent dicts. Writes Redis on live fetch so later callers share it."""
    league_u = (league or "MLB").upper()
    cached = load_cached_events(league_u)
    if cached:
        return cached
    if not allow_fetch:
        return []
    try:
        from api.sgo_data import _canonical_event_provider, _sb_event_to_dict, _rset, _clear_obsolete_event_model_keys

        sb_events = await _canonical_event_provider().get_sb_events(league_u)
        events = [_sb_event_to_dict(e) for e in (sb_events or [])]
        if events:
            _clear_obsolete_event_model_keys(league_u)
            _rset(f"sgo:v2:sbevents:{league_u}", events, ttl=900)
        return events
    except Exception as exc:
        logger.warning("Nested SGO event fetch failed for %s: %s", league_u, exc)
        return []


def find_event_by_id(events: list[dict], event_id: str) -> Optional[dict]:
    want = str(event_id or "")
    if not want:
        return None
    for evt in events:
        if not isinstance(evt, dict):
            continue
        if str(evt.get("id") or evt.get("event_id") or "") == want:
            return evt
    return None


def find_cached_event(event_id: str, leagues: Optional[list[str]] = None) -> Optional[dict]:
    for lg in leagues or ["MLB", "NFL", "NBA", "NHL"]:
        found = find_event_by_id(load_cached_events(lg), event_id)
        if found:
            return found
    return None


def _markets(evt: dict) -> list[dict]:
    raw = evt.get("markets") if isinstance(evt, dict) else None
    return raw if isinstance(raw, list) else []


def _main_books(market: dict) -> list[dict]:
    books = market.get("books") if isinstance(market, dict) else None
    if not isinstance(books, list):
        return []
    main = [b for b in books if isinstance(b, dict) and b.get("available") and b.get("is_main_line")]
    return main or [b for b in books if isinstance(b, dict) and b.get("available")]


def _collect_numeric(evt: dict, bet_types: tuple[str, ...], side: str, book_field: str, fair_field: str) -> list[float]:
    out: list[float] = []
    for m in _markets(evt):
        if (m.get("bet_type") or "") not in bet_types:
            continue
        if side and (m.get("side") or "") != side:
            continue
        fair = m.get(fair_field)
        if fair is not None:
            try:
                out.append(float(fair))
                continue
            except (TypeError, ValueError):
                pass
        for b in _main_books(m):
            val = b.get(book_field)
            if val is None:
                continue
            try:
                out.append(float(val))
            except (TypeError, ValueError):
                continue
    return out


def derive_game_environment(evt: dict) -> dict:
    """SB ME derived game/team environment from nested moneyline/total/spread.

    Never presented as a SportsGameOdds-supplied fact. Not an eligibility gate.
    """
    home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
    away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
    home_abbr = normalize_team_abbr(home.get("abbreviation") or "")
    away_abbr = normalize_team_abbr(away.get("abbreviation") or "")

    totals = _collect_numeric(evt, ("total", "over_under"), "over", "over_under", "fair_over_under")
    if not totals:
        totals = _collect_numeric(evt, ("total", "over_under"), "", "over_under", "fair_over_under")
    game_total = _median(totals)

    home_mls = _collect_numeric(evt, ("moneyline",), "home", "moneyline", "fair_odds")
    away_mls = _collect_numeric(evt, ("moneyline",), "away", "moneyline", "fair_odds")
    home_ml = _median(home_mls)
    away_ml = _median(away_mls)
    p_home_raw = american_implied_prob(int(home_ml) if home_ml is not None else None)
    p_away_raw = american_implied_prob(int(away_ml) if away_ml is not None else None)
    p_home_devig = p_away_devig = None
    if p_home_raw is not None and p_away_raw is not None and (p_home_raw + p_away_raw) > 0:
        s = p_home_raw + p_away_raw
        p_home_devig = p_home_raw / s
        p_away_devig = p_away_raw / s

    home_spreads = _collect_numeric(evt, ("spread",), "home", "spread", "fair_spread")
    home_spread = _median(home_spreads)

    implied_home = implied_away = None
    method = None
    # Team implied totals require both a game total and a home-aligned spread.
    # Win probability is not a scoring share — never derive totals from moneyline.
    if game_total is not None and home_spread is not None:
        implied_home = round(game_total / 2.0 - home_spread / 2.0, 2)
        implied_away = round(game_total - implied_home, 2)
        method = "spread_and_total"

    return {
        "source": "sbme_derived",
        "note": "SB ME derived from nested SGO moneyline/total/spread. Not a provider-supplied fact.",
        "event_id": evt.get("id"),
        "status": evt.get("status"),
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "home_score": evt.get("home_score"),
        "away_score": evt.get("away_score"),
        "sbme_game_total": round(game_total, 2) if game_total is not None else None,
        "sbme_home_ml": int(home_ml) if home_ml is not None else None,
        "sbme_away_ml": int(away_ml) if away_ml is not None else None,
        "sbme_home_win_prob_raw": round(p_home_raw, 4) if p_home_raw is not None else None,
        "sbme_away_win_prob_raw": round(p_away_raw, 4) if p_away_raw is not None else None,
        "sbme_home_win_prob_devig": round(p_home_devig, 4) if p_home_devig is not None else None,
        "sbme_away_win_prob_devig": round(p_away_devig, 4) if p_away_devig is not None else None,
        "sbme_home_spread": round(home_spread, 2) if home_spread is not None else None,
        "sbme_implied_team_total_home": implied_home,
        "sbme_implied_team_total_away": implied_away,
        "sbme_implied_total_method": method,
    }


def environments_by_team(events: list[dict]) -> dict[str, dict]:
    """Map canonical team abbr → derived environment (player's team perspective)."""
    by_team: dict[str, dict] = {}
    for evt in events:
        if not isinstance(evt, dict):
            continue
        env = derive_game_environment(evt)
        home = env.get("home_abbr") or ""
        away = env.get("away_abbr") or ""
        if home:
            by_team[home] = {**env, "sbme_implied_team_total": env.get("sbme_implied_team_total_home"),
                             "sbme_opponent_implied_total": env.get("sbme_implied_team_total_away"),
                             "sbme_team_win_prob_devig": env.get("sbme_home_win_prob_devig")}
        if away:
            by_team[away] = {**env, "sbme_implied_team_total": env.get("sbme_implied_team_total_away"),
                             "sbme_opponent_implied_total": env.get("sbme_implied_team_total_home"),
                             "sbme_team_win_prob_devig": env.get("sbme_away_win_prob_devig")}
    return by_team


def _prop_key(market: dict) -> Optional[str]:
    raw = ((market.get("market_name") or "") + " " + (market.get("stat_id") or "")).lower()
    clean = raw.replace(" ", "").replace("_", "").replace("-", "")
    for pattern, key in RESEARCH_PROP_MAP:
        if pattern in clean:
            return key
    return None


def extract_research_props(evt: dict) -> dict[str, dict]:
    """Player prop O/U lines for research only — never convert hitter thresholds to FP."""
    by_player: dict[str, dict] = {}
    for m in _markets(evt):
        if (m.get("bet_type") or "") != "player_prop":
            continue
        pname = (m.get("player_name") or "").strip()
        pid = str(m.get("player_id") or "")
        if not pname and not pid:
            continue
        key = _prop_key(m)
        if not key:
            continue
        line = m.get("fair_over_under")
        if line is None:
            books = _main_books(m)
            if books:
                line = books[0].get("over_under")
        if line is None:
            continue
        try:
            line_f = float(line)
        except (TypeError, ValueError):
            continue
        bucket = by_player.setdefault(fold_player_name(pname) or pid, {
            "player_id": pid,
            "player_name": pname,
            "note": "SGO betting O/U threshold. Not an expected-value fantasy-point projection.",
        })
        bucket[key] = line_f
        if m.get("fair_odds") is not None:
            bucket.setdefault("fair_odds", m.get("fair_odds"))
    return by_player


def sbevent_to_game_row(evt: dict) -> dict:
    env = derive_game_environment(evt)
    home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
    away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
    books = []
    for m in _markets(evt):
        if (m.get("bet_type") or "") != "moneyline":
            continue
        side = m.get("side")
        for b in _main_books(m):
            name = b.get("bookmaker") or ""
            if not name:
                continue
            row = next((x for x in books if x["bookmaker_name"] == name), None)
            if row is None:
                row = {"bookmaker_name": name, "sportsbook": name, "moneyline_home": None, "moneyline_away": None}
                books.append(row)
            if side == "home":
                row["moneyline_home"] = b.get("moneyline")
            elif side == "away":
                row["moneyline_away"] = b.get("moneyline")
    return {
        "game_id": evt.get("id"),
        "id": evt.get("id"),
        "event_id": evt.get("id"),
        "home_team_name": home.get("name") or home.get("abbreviation"),
        "away_team_name": away.get("name") or away.get("abbreviation"),
        "home_abbr": env.get("home_abbr"),
        "away_abbr": env.get("away_abbr"),
        "start_time": evt.get("start_time"),
        "status": evt.get("status"),
        "home_score": evt.get("home_score"),
        "away_score": evt.get("away_score"),
        "total_line": env.get("sbme_game_total"),
        "spread_line": env.get("sbme_home_spread"),
        "moneyline_home": env.get("sbme_home_ml"),
        "moneyline_away": env.get("sbme_away_ml"),
        "sbme_environment": env,
        "odds": books,
        "bookmakers": evt.get("bookmakers") or [],
    }


def sbevent_to_compare_books(evt: dict) -> list[dict]:
    by_book: dict[str, dict] = {}
    for m in _markets(evt):
        bt = m.get("bet_type") or ""
        side = m.get("side") or ""
        for b in m.get("books") or []:
            if not isinstance(b, dict):
                continue
            name = b.get("bookmaker") or ""
            if not name:
                continue
            row = by_book.setdefault(name, {
                "bookmaker_name": name, "sportsbook": name, "name": name,
                "moneyline_home": None, "moneyline_away": None,
                "spread_home": None, "spread_away": None, "total": None,
            })
            if bt == "moneyline" and side == "home":
                row["moneyline_home"] = b.get("moneyline")
            elif bt == "moneyline" and side == "away":
                row["moneyline_away"] = b.get("moneyline")
            elif bt == "spread" and side == "home":
                row["spread_home"] = b.get("spread")
            elif bt == "spread" and side == "away":
                row["spread_away"] = b.get("spread")
            elif bt in ("total", "over_under") and b.get("over_under") is not None:
                row["total"] = b.get("over_under")
    return list(by_book.values())


def sbevent_player_props(evt: dict, player_id: str = "") -> list[dict]:
    want = fold_player_name(player_id) if player_id and " " in player_id else (player_id or "")
    out = []
    for m in _markets(evt):
        if (m.get("bet_type") or "") != "player_prop":
            continue
        pid = str(m.get("player_id") or "")
        pname = m.get("player_name") or ""
        if want and pid != want and fold_player_name(pname) != fold_player_name(want) and pid != player_id:
            continue
        books = []
        for b in m.get("books") or []:
            if not isinstance(b, dict):
                continue
            books.append({
                "bookmaker_name": b.get("bookmaker"),
                "line": b.get("over_under"),
                "price": b.get("moneyline"),
                "over_price": b.get("moneyline") if (m.get("side") or "") == "over" else None,
                "under_price": b.get("moneyline") if (m.get("side") or "") == "under" else None,
                "last_updated": b.get("last_updated"),
            })
        out.append({
            "player_id": pid,
            "player_name": pname,
            "market": m.get("market_name"),
            "line": m.get("fair_over_under"),
            "fair_odds": m.get("fair_odds"),
            "fair_over_under": m.get("fair_over_under"),
            "note": "SGO betting O/U threshold. Not an expected-value fantasy-point projection.",
            "books": books,
        })
    return out


def resolve_sgo_id_from_events(
    events: list[dict],
    *,
    player_id: str = "",
    name: str = "",
    team: str = "",
) -> Optional[str]:
    """Exact folded-name (+ optional team) match. No fuzzy mapping."""
    if looks_like_sgo_player_id(player_id):
        for evt in events:
            for p in evt.get("players") or []:
                if isinstance(p, dict) and str(p.get("player_id") or "") == player_id:
                    return player_id
        return player_id  # already SGO-shaped; last-n will no-op if absent from results

    folded = fold_player_name(name)
    want_team = normalize_team_abbr(team)
    hits: list[str] = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        home = evt.get("home_team") if isinstance(evt.get("home_team"), dict) else {}
        away = evt.get("away_team") if isinstance(evt.get("away_team"), dict) else {}
        home_id = str(home.get("team_id") or "")
        away_id = str(away.get("team_id") or "")
        home_abbr = normalize_team_abbr(home.get("abbreviation") or "")
        away_abbr = normalize_team_abbr(away.get("abbreviation") or "")
        for p in evt.get("players") or []:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("player_id") or "")
            if player_id and pid == str(player_id):
                return pid
            if folded and fold_player_name(p.get("name") or "") == folded:
                pteam = ""
                tid = str(p.get("team_id") or "")
                if tid and away_id and tid.upper() == away_id.upper():
                    pteam = away_abbr
                elif tid:
                    pteam = home_abbr
                if want_team and pteam and not teams_equivalent(want_team, pteam):
                    continue
                if pid:
                    hits.append(pid)
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    return None


def attach_environment_to_pool(pool: list[dict], events: list[dict]) -> list[dict]:
    """Annotate canonical players with derived env + research props. Not an eligibility gate."""
    if not pool:
        return pool
    by_team = environments_by_team(events)
    props_all: dict[str, dict] = {}
    for evt in events:
        if not isinstance(evt, dict):
            continue
        for key, payload in extract_research_props(evt).items():
            props_all[key] = payload
    for pl in pool:
        team = normalize_team_abbr(pl.get("team") or "")
        env = by_team.get(team) or {}
        sgo_id = resolve_sgo_id_from_events(
            events,
            player_id=str(pl.get("id") or ""),
            name=pl.get("name") or "",
            team=pl.get("team") or "",
        )
        pl["sgo_player_id"] = sgo_id
        pl["dfs_player_id"] = str(pl.get("id") or "")
        pl["sbme_game_total"] = env.get("sbme_game_total")
        pl["sbme_implied_team_total"] = env.get("sbme_implied_team_total")
        pl["sbme_opponent_implied_total"] = env.get("sbme_opponent_implied_total")
        pl["sbme_team_win_prob_devig"] = env.get("sbme_team_win_prob_devig")
        pl["sbme_home_win_prob_devig"] = env.get("sbme_home_win_prob_devig")
        pl["sbme_away_win_prob_devig"] = env.get("sbme_away_win_prob_devig")
        pl["sbme_implied_total_method"] = env.get("sbme_implied_total_method")
        pl["sbme_environment_source"] = "sbme_derived" if env else None
        pl["sbme_environment_note"] = env.get("note")
        folded = fold_player_name(pl.get("name") or "")
        research = props_all.get(folded) or (props_all.get(sgo_id) if sgo_id else None)
        pl["sgo_prop_lines"] = research or None
    return pool
