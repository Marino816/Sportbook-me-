"""Get actual SGO league IDs for full sport inventory."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from providers.sportsgameodds import SportsGameOddsProvider


async def main():
    async with SportsGameOddsProvider() as p:
        # Leagues endpoint
        for ep in ["/leagues", "/sports/leagues", "/leagues?all=true"]:
            try:
                r = await p._request("GET", ep)
                print(f"{ep}: {json.dumps(r)[:1500]}")
            except Exception as e:
                print(f"{ep}: {type(e).__name__} {str(e)[:80]}")

        # Try common league IDs for golf/soccer/MMA
        for lg in ["GOLF", "PGA", "PGA_TOUR", "SOCCER", "EPL", "MLS", "MMA", "UFC", "WNBA", "TENNIS", "ATP"]:
            try:
                e = await p._request("GET", f"/events?leagueID={lg}&limit=1")
                evs = e if isinstance(e, list) else e.get("data", e.get("events", []))
                n = len(evs) if isinstance(evs, list) else 0
                print(f"EVENTS leagueID={lg}: {n} events")
            except Exception as ex:
                print(f"EVENTS leagueID={lg}: {str(ex)[:70]}")


asyncio.run(main())