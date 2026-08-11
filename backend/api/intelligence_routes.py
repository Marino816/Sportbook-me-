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
from providers.intelligence import SGOIntelligenceBuilder

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def intelligence_health():
    """Provider status + odds math verification."""
    return {
        "provider": {
            "dfs": "SportsDataIO",
            "market": "SportsGameOdds",
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
    Return SB ME intelligence combining SportsDataIO DFS data
    with SportsGameOdds market context.

    Data sources:
      - SportsDataIO: DFS salaries, projections, positions (via Projection table)
      - SportsGameOdds: market context (via providers/integration.py cache)

    Provider statuses are separated in every record.
    """
    t0 = time.time()

    # ── Load slate ──
    r = await db.execute(select(DBSlate).where(DBSlate.id == slate_id))
    slate = r.scalars().first()
    if not slate:
        raise HTTPException(404, "Slate not found")

    # ── Load DFS projections (SportsDataIO fallback) ──
    r = await db.execute(
        select(Projection, DBPlayer)
        .join(DBPlayer, Projection.player_id == DBPlayer.id)
        .where(Projection.slate_id == slate_id)
        .where(Projection.salary > 0)
        .limit(200)
    )
    rows = r.all()

    # ── Load SGO market context (cached) ──
    sgo_games = {}
    sgo_available = False
    try:
        from providers.integration import SGOIntegration
        async with SGOIntegration() as sgo:
            sgo_events = await sgo.get_events(league_id="MLB")
            for ev in sgo_events:
                eid = ev.id
                odds = await sgo.get_odds(eid)
                props = await sgo.get_player_props(eid)
                sgo_games[eid] = {"event": ev, "odds": odds, "props": props}
            sgo_available = True
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

        # Match to SGO game context if available
        if sgo_available:
            for eid, game in sgo_games.items():
                home = game["event"].home_team.lower()
                away = game["event"].away_team.lower()
                pt = (player.team or "").lower()
                if pt and (pt in home or pt in away):
                    pi.team_id = player.team
                    pi.opponent_id = away if pt in home else home

                    # Game intelligence (build once per event)
                    if eid not in seen_events:
                        seen_events.add(eid)
                        gi = GameIntelligence(
                            event_id=eid,
                            home_team_name=game["event"].home_team,
                            away_team_name=game["event"].away_team,
                        )
                        if game["odds"]:
                            books = game["odds"].books if game["odds"] else []
                            gi.book_count = len(books)
                            if books:
                                gi.total_line = books[0].total_over
                                gi.spread_line = books[0].spread_home
                                gi.moneyline_home = books[0].moneyline_home
                                gi.moneyline_away = books[0].moneyline_away
                            gi.game_environment = SignalComputer.game_environment(gi.total_line)
                        games[eid] = gi

                    if eid in games:
                        pi.game_total = games[eid].total_line
                        pi.game_environment = games[eid].game_environment

                    # Player props
                    if game["props"]:
                        player_data = {"playerID": str(proj.player_id), "name": player.name, "position": proj.roster_position}
                        builder = SGOIntelligenceBuilder()
                        dp = builder.build_player_intelligence(player_data, game["props"], {})
                        if dp.fantasy_market_line is not None:
                            pi.fantasy_market_line = dp.fantasy_market_line
                            pi.fantasy_market_edge = round(pi.base_projection - dp.fantasy_market_line, 1)
                            pi.fantasy_market_book = dp.fantasy_market_book
                        for mk, sig in dp.prop_signals.items():
                            pi.prop_signals[mk] = PropIntelligence(
                                market=mk,
                                bookmaker=sig.bookmaker,
                                line=sig.line,
                                over_price=sig.over_price,
                                under_price=sig.under_price,
                                fair_line=sig.fair_line,
                                edge_pct=sig.edge_pct,
                            )
                        pi.prop_book_count = dp.sportsbook_count
                    break  # matched game

        SignalComputer.compute_all(pi)
        players.append(pi.to_dict())

    build_ms = round((time.time() - t0) * 1000)

    return wrap_data({
        "slate_id": slate_id,
        "sport": slate.sport or "MLB",
        "platform": slate.site or "draftkings",
        "provider": {
            "dfs": "SportsDataIO",
            "dfs_data_mode": DFSDataMode.TRIAL_SCRAMBLED.value,
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