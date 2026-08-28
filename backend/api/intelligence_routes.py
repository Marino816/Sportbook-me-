"""SB ME Intelligence API — normalized market context from live providers."""

import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from api.auth import get_current_user
from models.domain import User, Projection, Player as DBPlayer, Slate as DBSlate
from api.utils import wrap_data
from intelligence.engine import (
    PlayerIntelligence, GameIntelligence, SignalComputer, PropIntelligence,
    PlayerSignal, GameEnvironmentSignal, DataSourceStatus, DFSDataMode,
    american_to_implied_probability, probability_edge, SPORT_ENV_THRESHOLDS,
)
from dfs.team_normalize import normalize_team_abbr, teams_equivalent
from dfs.name_normalize import fold_player_name

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


@router.get("/slate/{slate_id}")
async def get_slate_intelligence(
    slate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return SB ME intelligence combining native DFS contest data
    (Blue Collar / CSV salaries) with SportsGameOdds nested event markets.

    Data sources:
      - Native DFS: salaries, positions, Blue Collar fppg
      - SportsGameOdds: nested /v2/events markets (fantasyScore, props, odds)

    Provider statuses are separated in every record.
    """
    t0 = time.time()

    # ── Load slate ──
    r = await db.execute(select(DBSlate).where(DBSlate.id == slate_id))
    slate = r.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")

    # ── Load DFS projections (native / published slate) ──
    r = await db.execute(
        select(Projection, DBPlayer)
        .join(DBPlayer, Projection.player_id == DBPlayer.id)
        .where(Projection.slate_id == slate_id)
        .where(Projection.salary > 0)
        .limit(200)
    )
    rows = r.all()

    # ── Load SGO market context from nested /v2/events cache ──
    sgo_games = {}
    sgo_available = False
    try:
        from providers.nested_events import (
            derive_game_environment,
            extract_research_props,
            load_cached_or_fetch_events,
        )
        nested_events = await load_cached_or_fetch_events((slate.sport or "MLB").upper())
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
        sgo_available = bool(sgo_games)
    except Exception as e:
        logger.warning(f"SGO unavailable for intelligence: {e}")

    # ── Build intelligence records ──
    players = []
    games = {}
    game_idx = 1
    seen_events = set()

    for proj, player in rows:
        fp = proj.projected_fp or 0
        if fp <= 0:
            continue

        pi = PlayerIntelligence(
            player_id=str(proj.player_id),
            player_name=player.name or "",
            team_id=player.team or "",
            position=proj.roster_position or "",
            dfs_salary=proj.salary or 0,
            base_projection=round(fp, 1),
        )

        # Match to nested SGO game context if available
        if sgo_available:
            pt = normalize_team_abbr(player.team or "")
            folded = fold_player_name(player.name or "")
            for eid, game in sgo_games.items():
                ev = game["event"]
                env = game["env"]
                home = ev.get("home_team") if isinstance(ev.get("home_team"), dict) else {}
                away = ev.get("away_team") if isinstance(ev.get("away_team"), dict) else {}
                home_abbr = normalize_team_abbr(home.get("abbreviation") or "")
                away_abbr = normalize_team_abbr(away.get("abbreviation") or "")
                if pt and not (teams_equivalent(pt, home_abbr) or teams_equivalent(pt, away_abbr)):
                    continue
                pi.team_id = player.team
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
                pi.prop_book_count = len(research) - 2 if research else 0  # minus note/name keys
                break

        SignalComputer.compute_all(pi)
        players.append(pi.to_dict())

    build_ms = round((time.time() - t0) * 1000)

    return wrap_data({
        "slate_id": slate_id,
        "sport": slate.sport or "MLB",
        "platform": slate.site or "draftkings",
        "provider": {
            "dfs": "native",
            "dfs_data_mode": "native",
            "market": "SportsGameOdds" if sgo_available else "unavailable",
            "market_context_status": (
                DataSourceStatus.LIVE.value if sgo_available
                else DataSourceStatus.UNAVAILABLE.value
            ),
        },
        "game_count": len(games),
        "player_intelligence_count": len(players),
        "players": players[:50],  # paginate
        "games": [g.to_dict() for g in games.values()],
        "performance": {"build_ms": build_ms},
    })