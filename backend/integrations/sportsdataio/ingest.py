"""CLI entry point for SportsDataIO ingestion.

Usage:
  DATABASE_URL='...' python3 integrations/sportsdataio/ingest.py
  DATABASE_URL='...' python3 integrations/sportsdataio/ingest.py 2026-AUG-07
"""

import asyncio, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from models.database import SessionLocal
from integrations.sportsdataio.mlb import ingest_all

async def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    session = SessionLocal()
    try:
        result = await ingest_all(session, date_str)
        print("\nIngestion Summary:")
        print(f"  Data Mode: TRIAL_SCRAMBLED")
        print(f"  Players: {result.get('players', '?')}")
        proj = result.get('projections', {})
        print(f"  Projections: {proj.get('projections', '?')} (DK: {proj.get('dk_players', '?')}, FD: {proj.get('fd_players', '?')})")
        print(f"  API Calls: {result.get('api_calls', '?')}")
        print("\nDone.")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())