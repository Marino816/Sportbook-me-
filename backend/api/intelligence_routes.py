"""SB ME Intelligence API — normalized market context from live providers."""

import time
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from api.auth import get_current_user
from models.domain import User, Projection, Player as DBPlayer, Slate as DBSlate
from api.utils import wrap_data
from intelligence.engine import (
    PlayerIntelligence, GameIntelligence, SignalComputer, PropIntelligence,
    DataSourceStatus,
    american_to_implied_probability, probability_edge, SPORT_ENV_THRESHOLDS,
)
from dfs.team_normalize import normalize_team_abbr, teams_equivalent
from dfs.name_normalize import fold_player_name
from dfs.db import DFSSlate, DFSPlayer

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def intelligence_health():
    """Provider status + odds math verification."""
    return {
        "provider": {
            "dfs": "native DFS (Blue Collar / CSV)",
            "market": "SportsGameOdds (nested /v2/events)",
        },
        "market_context_status": "check /intelligence/slate/{id} for live status",
        "odds_math_verify": {
            "american_plus150": american_to_implied_probability(150),
            "american_minus200": american_to_implied_probability(-200),
            "probability_edge_example": probability_edge(-110, -105),
        },
        "sport_configs": list(SPORT_ENV_THRESHOLDS.keys()),
    }


def empty_intelligence_payload(slate_id: int, reason: str, sport: str = "", platform: str = ""):
    return {
        "slate_id": slate_id,
        "sport": sport or None,
        "platform": platform or None,
        "available": False,
        "empty": True,
        "reason": reason,
        "provider": {
            "dfs": "unavailable",
            "dfs_data_mode": "unavailable",
            "market": "unavailable",
            "market_context_status": DataSourceStatus.UNAVAILABLE.value,
        },
        "game_count": 0,
        "player_intelligence_count": 0,
        "players": [],
        "games": [],
        "performance": {"build_ms": 0},
    }


async def _load_sgo_games(sport: str) -> tuple[dict, bool]:
    sgo_games = {}
    try:
        from providers.nested_events import (
            derive_game_environment,
            extract_research_props,
            load_cached_or_fetch_events,
        )
        nested_events = await load_cached_or_fetch_events((sport or "MLB").upper())
        for ev in nested_events:
            if not isinstance(ev, dict):
                continue
            eid = str(ev.get("id") or "")
            if not eid:
                continue
            sgo_games[eid] = {
                "event": ev,
                "env": derive_game_environment(ev),
                "props": extract_research_props(ev),
            }
    except Exception as e:
        logger.warning(f"SGO unavailable for intelligence: {e}")
    return sgo_games, bool(sgo_games)


def assemble_intelligence_records(rows: list[dict], sgo_games: dict, sgo_available: bool):
    players = []
    games = {}
    seen_events = set()

    for row in rows:
        fp = row.get("projected_fp") or 0
        pi = PlayerIntelligence(
            player_id=str(row.get("player_id") or ""),
            player_name=row.get("player_name") or "",
            team_id=row.get("team") or "",
            position=row.get("position") or "",
            dfs_salary=int(row.get("salary") or 0),
            base_projection=round(float(fp), 1) if fp else 0.0,
        )

        if sgo_available:
            pt = normalize_team_abbr(row.get("team") or "")
            folded = fold_player_name(row.get("player_name") or "")
            for eid, game in sgo_games.items():
                ev = game["event"]
                env = game["env"]
                home = ev.get("home_team") if isinstance(ev.get("home_team"), dict) else {}
                away = ev.get("away_team") if isinstance(ev.get("away_team"), dict) else {}
                home_abbr = normalize_team_abbr(home.get("abbreviation") or "")
                away_abbr = normalize_team_abbr(away.get("abbreviation") or "")
                if pt and not (teams_equivalent(pt, home_abbr) or teams_equivalent(pt, away_abbr)):
                    continue
                pi.team_id = row.get("team") or ""
                pi.opponent_id = away_abbr if teams_equivalent(pt, home_abbr) else home_abbr

                if eid not in seen_events:
                    seen_events.add(eid)
                    gi = GameIntelligence(
                        event_id=eid,
                        home_team_name=home.get("name") or home_abbr,
                        away_team_name=away.get("name") or away_abbr,
                    )
                    gi.book_count = len(ev.get("bookmakers") or [])
                    gi.total_line = env.get("sbme_game_total")
                    gi.spread_line = env.get("sbme_home_spread")
                    gi.moneyline_home = env.get("sbme_home_ml")
                    gi.moneyline_away = env.get("sbme_away_ml")
                    gi.game_environment = SignalComputer.game_environment(gi.total_line)
                    games[eid] = gi

                if eid in games:
                    pi.game_total = games[eid].total_line
                    pi.game_environment = games[eid].game_environment

                research = game["props"].get(folded) or {}
                if research.get("hits_line") is not None:
                    pi.prop_signals["hits"] = PropIntelligence(
                        market="hits",
                        bookmaker="",
                        line=research.get("hits_line"),
                    )
                if research.get("hr_line") is not None:
                    pi.prop_signals["home_runs"] = PropIntelligence(
                        market="home_runs",
                        bookmaker="",
                        line=research.get("hr_line"),
                    )
                if research.get("strikeouts_line") is not None:
                    pi.prop_signals["strikeouts"] = PropIntelligence(
                        market="strikeouts",
                        bookmaker="",
                        line=research.get("strikeouts_line"),
                    )
                pi.prop_book_count = len(research) - 2 if research else 0
                break

        SignalComputer.compute_all(pi)
        players.append(pi.to_dict())

    return players, games


def finalize_intelligence_payload(
    slate_id: int,
    sport: str,
    platform: str,
    dfs_mode: str,
    players: list,
    games: dict,
    sgo_available: bool,
    build_ms: int,
    reason_if_empty: str = "no_player_intelligence",
):
    available = bool(players or games)
    return {
        "slate_id": slate_id,
        "sport": sport or "MLB",
        "platform": platform or "draftkings",
        "available": available,
        "empty": not available,
        "reason": None if available else reason_if_empty,
        "provider": {
            "dfs": dfs_mode or "native",
            "dfs_data_mode": dfs_mode or "native",
            "market": "SportsGameOdds" if sgo_available else "unavailable",
            "market_context_status": (
                DataSourceStatus.LIVE.value if sgo_available
                else DataSourceStatus.UNAVAILABLE.value
            ),
        },
        "game_count": len(games),
        "player_intelligence_count": len(players),
        "players": players[:50],
        "games": [g.to_dict() for g in games.values()],
        "performance": {"build_ms": build_ms},
    }


@router.get("/slate/{slate_id}")
async def get_slate_intelligence(
    slate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return SB ME intelligence for a contest slate.

    DFS slate IDs (dfs_slates) are resolved first against that slate's
    player pool. Legacy ``slates`` / ``projections`` IDs are used only when
    no DFS slate exists with that id — never mixed.
    """
    t0 = time.time()

    dfs_r = await db.execute(select(DFSSlate).where(DFSSlate.id == slate_id))
    dfs_slate = dfs_r.scalars().first()
    if dfs_slate:
        players_r = await db.execute(select(DFSPlayer).where(DFSPlayer.slate_id == dfs_slate.id))
        dfs_players = players_r.scalars().all()
        rows = []
        for p in dfs_players:
            if (p.salary or 0) <= 0:
                continue
            rows.append({
                "player_id": str(p.provider_player_id or p.id),
                "player_name": p.player_name or "",
                "team": p.team or "",
                "position": p.position or "",
                "salary": p.salary or 0,
                "projected_fp": float(p.fppg or 0),
            })
        sport = (dfs_slate.sport or "MLB")
        sgo_games, sgo_available = await _load_sgo_games(sport)
        scored, games = assemble_intelligence_records(rows, sgo_games, sgo_available)
        build_ms = round((time.time() - t0) * 1000)
        return wrap_data(finalize_intelligence_payload(
            slate_id=slate_id,
            sport=sport,
            platform=dfs_slate.platform or "draftkings",
            dfs_mode=dfs_slate.data_source or "native",
            players=scored,
            games=games,
            sgo_available=sgo_available,
            build_ms=build_ms,
        ))

    r = await db.execute(select(DBSlate).where(DBSlate.id == slate_id))
    slate = r.scalars().first()
    if not slate:
        return wrap_data(empty_intelligence_payload(slate_id, "slate_not_found"))

    proj_r = await db.execute(
        select(Projection, DBPlayer)
        .join(DBPlayer, Projection.player_id == DBPlayer.id)
        .where(Projection.slate_id == slate_id)
        .where(Projection.salary > 0)
        .limit(200)
    )
    rows = []
    for proj, player in proj_r.all():
        fp = proj.projected_fp or 0
        if fp <= 0:
            continue
        rows.append({
            "player_id": str(proj.player_id),
            "player_name": player.name or "",
            "team": player.team or "",
            "position": proj.roster_position or "",
            "salary": proj.salary or 0,
            "projected_fp": fp,
        })
    sport = slate.sport or "MLB"
    sgo_games, sgo_available = await _load_sgo_games(sport)
    scored, games = assemble_intelligence_records(rows, sgo_games, sgo_available)
    build_ms = round((time.time() - t0) * 1000)
    return wrap_data(finalize_intelligence_payload(
        slate_id=slate_id,
        sport=sport,
        platform=slate.site or "draftkings",
        dfs_mode="native",
        players=scored,
        games=games,
        sgo_available=sgo_available,
        build_ms=build_ms,
    ))
