"""Minimal SGO audit — key endpoints only."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from providers.sportsgameodds import SportsGameOddsProvider


async def main():
    async with SportsGameOddsProvider() as p:
        # 1. Account
        u = await p._request("GET", "/account/usage")
        d = u.get("data", u)
        print("TIER:", d.get("tier"), "| active:", d.get("isActive"))
        rl = d.get("rateLimits", {})
        print("RATE LIMITS:", json.dumps({k: {kk: vv for kk, vv in v.items() if "max" in kk} for k, v in rl.items()}))

        # 2. Sports
        s = await p._request("GET", "/sports")
        sports = s if isinstance(s, list) else s.get("data", s.get("sports", s.get("data", [])))
        if isinstance(sports, list):
            for sp in sports:
                print("SPORT:", sp.get("sportID"), sp.get("name"), [lg.get("leagueID") for lg in (sp.get("leagues") or [])][:5])
        elif isinstance(sports, dict):
            print("SPORTS:", list(sports.keys())[:10])

        # 3. Events summary per league
        for lg in ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "WNBA", "UFC", "PGA", "SOCCER"]:
            try:
                e = await p._request("GET", f"/events?leagueID={lg}&limit=1")
                evs = e if isinstance(e, list) else e.get("data", e.get("events", []))
                n = len(evs) if isinstance(evs, list) else 0
                print(f"EVENTS {lg}: {n} (1st)")
                if n and isinstance(evs, list):
                    ev = evs[0]
                    print(f"  status={ev.get('status',{}).get('live', False) if isinstance(ev.get('status'), dict) else ev.get('status')} teams={ev.get('teams',{}).get('home',{}).get('names',{}).get('short','?')} scores={ev.get('teams',{}).get('home',{}).get('score', '?')} vs {ev.get('teams',{}).get('away',{}).get('score', '?')}")
            except Exception as ex:
                print(f"EVENTS {lg}: {type(ex).__name__} {str(ex)[:80]}")

        # 4. Players
        for lg in ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"]:
            try:
                pl = await p._request("GET", f"/players?leagueID={lg}&limit=2")
                players = pl if isinstance(pl, list) else pl.get("data", pl.get("players", []))
                n = len(players) if isinstance(players, list) else 0
                name = players[0].get("names", {}).get("display", "?") if n else "N/A"
                print(f"PLAYERS {lg}: {n}, sample={name}")
            except Exception as ex:
                print(f"PLAYERS {lg}: {type(ex).__name__} {str(ex)[:60]}")

        # 5. Player stats (Last-5 historical) for MLB, NBA, NFL
        for lg in ["MLB", "NBA", "NFL"]:
            try:
                pl = await p._request("GET", f"/players?leagueID={lg}&limit=1")
                players = pl if isinstance(pl, list) else pl.get("data", pl.get("players", []))
                if not players:
                    print(f"STATS {lg}: no players")
                    continue
                pid = players[0].get("playerID") or players[0].get("id")
                name = players[0].get("names", {}).get("display", "?")
                try:
                    st = await p._request("GET", f"/players/{pid}/stats")
                    print(f"STATS {lg} {name}: {str(st)[:400]}")
                except Exception as e:
                    print(f"STATS {lg} {name}: BLOCKED {type(e).__name__} {str(e)[:80]}")
                    # Try game logs
                    try:
                        gl = await p._request("GET", f"/players/{pid}/games")
                        print(f"GAMES {lg} {name}: {str(gl)[:400]}")
                    except Exception as e2:
                        print(f"GAMES {lg} {name}: BLOCKED {type(e2).__name__} {str(e2)[:80]}")
            except Exception as ex:
                print(f"PLAYERS-STATS {lg}: {type(ex).__name__} {str(ex)[:80]}")

        # 6. Bookmaker check from event odds
        print("\n=== BOOKMAKERS FROM EVENT ===")
        e = await p._request("GET", "/events?leagueID=MLB&oddsAvailable=true&limit=1")
        evs = e if isinstance(e, list) else e.get("data", e.get("events", []))
        if evs:
            odds = evs[0].get("odds", {})
            # Grab first 3 odds to see bookmaker list
            for i, (k, v) in enumerate(odds.items()):
                if i >= 3: break
                bm = v.get("byBookmaker", {})
                print(f"  {k}: books={list(bm.keys())}")
            # Count total unique books
            all_books = set()
            for v in odds.values():
                all_books.update(v.get("byBookmaker", {}).keys())
            print(f"  Total unique bookmakers: {len(all_books)} -> {sorted(all_books)}")

        print(f"\nREQUESTS: {p.stats.requests} OBJECTS: {p.stats.objects_consumed} ERRORS: {p.stats.errors}")


asyncio.run(main())