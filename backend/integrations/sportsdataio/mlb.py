"""
SportsDataIO MLB ingestion pipeline.

Ingests: players, slates, projections, salaries, injuries, matchups.
All data labeled TRIAL_SCRAMBLED until paid key is activated.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.sportsdataio.client import fetch, IngestionMetrics
from integrations.sportsdataio.normalizer import (
    upsert_player, upsert_slate, upsert_projection, upsert_matchup,
)
from integrations.sportsdataio.exceptions import TrialDataWarning


async def ingest_players(db: AsyncSession) -> int:
    """Ingest all active MLB players from SportsDataIO player roster."""
    data = fetch("/scores/json/Players")
    count = 0
    for p in data:
        name = (p.get("FirstName", "") + " " + p.get("LastName", "")).strip()
        team = p.get("Team", "")
        if not name:
            continue
        status = p.get("Status", "")
        if status not in ("Active", "Probable", "Day-To-Day"):
            continue  # skip minors, injured, etc. for DFS optimizer

        await upsert_player(
            db,
            provider_id=p.get("PlayerID", 0),
            name=name,
            team=team,
            position=p.get("Position"),
        )
        count += 1
    IngestionMetrics.records_ingested += count
    return count


async def ingest_dfs_projections(db: AsyncSession, date_str: str) -> dict:
    """Ingest DFS projections for a given date (YYYY-MMM-DD format like 2026-AUG-07)."""
    data = fetch(f"/projections/json/PlayerGameProjectionStatsByDate/{date_str}")
    result = {"players": 0, "projections": 0, "dk_players": 0, "fd_players": 0}

    slate_dk = await upsert_slate(db, "MLB", "DraftKings", datetime.now(timezone.utc))
    slate_fd = await upsert_slate(db, "MLB", "FanDuel", datetime.now(timezone.utc))

    for p in data:
        name = p.get("Name", "")
        team = p.get("Team", "")
        if not name:
            continue

        player = await upsert_player(db, p["PlayerID"], name, team, p.get("Position"))
        result["players"] += 1

        # DraftKings projection
        dk_sal = p.get("DraftKingsSalary")
        if dk_sal and dk_sal > 0:
            dk_pos = p.get("DraftKingsPosition", "UTIL")
            dk_fp = p.get("FantasyPointsDraftKings", 0.0) or 0.0
            await upsert_projection(
                db, slate_dk.id, player.id, dk_sal, dk_pos,
                dk_fp, dk_fp * 1.3, dk_fp * 0.5, 5.0, (dk_fp * 1000 / dk_sal) if dk_sal else 0,
            )
            result["dk_players"] += 1
            result["projections"] += 1

        # FanDuel projection
        fd_sal = p.get("FanDuelSalary")
        if fd_sal and fd_sal > 0:
            fd_pos = p.get("FanDuelPosition", "UTIL")
            fd_fp = p.get("FantasyPointsFanDuel", 0.0) or 0.0
            await upsert_projection(
                db, slate_fd.id, player.id, fd_sal, fd_pos,
                fd_fp, fd_fp * 1.3, fd_fp * 0.5, 5.0, (fd_fp * 1000 / fd_sal) if fd_sal else 0,
            )
            result["fd_players"] += 1
            result["projections"] += 1

    IngestionMetrics.records_ingested += result["projections"]
    return result


async def ingest_all(db: AsyncSession, date_str: str = None) -> dict:
    """Run full MLB ingestion: players + projections for given date."""
    if date_str is None:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%b-%d").upper()  # e.g. 2026-AUG-07

    IngestionMetrics.start("SportsDataIO MLB Ingestion")
    print(f"Ingestion started: {date_str} (TRIAL_SCRAMBLED)")

    try:
        players = await ingest_players(db)
        print(f"  Players: {players}")

        proj = await ingest_dfs_projections(db, date_str)
        print(f"  Projections: {proj['projections']} (DK: {proj['dk_players']}, FD: {proj['fd_players']})")

        await db.commit()
        IngestionMetrics.finish()

        summary = IngestionMetrics.summary()
        summary["players"] = players
        summary["projections"] = proj
        print(f"Ingestion complete: {players} players, {proj['projections']} projections")
        print(f"Data mode: {IngestionMetrics.data_mode}")
        return summary
    except Exception:
        await db.rollback()
        raise