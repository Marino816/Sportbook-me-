"""Focused SGO capability audit — subscription, endpoints, historical stats, DFS salaries."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from providers.sportsgameodds import SportsGameOddsProvider


async def main():
    async with SportsGameOddsProvider() as p:
        # 1. Account usage (full)
        print("=== 1. ACCOUNT / RATE LIMITS ===")
        try:
            u = await p._request("GET", "/account/usage")
            d = u.get("data", u) if isinstance(u, dict) else u
            print(json.dumps({k: d.get(k) for k in ("tier", "isActive", "rateLimits", "customerID")}, indent=2))
        except Exception as e:
            print("ERROR", e)

        # 2. Sports inventory
        print("\n=== 2. SPORTS ===")
        try:
            s = await p._request("GET", "/sports")
            sports = s if isinstance(s, list) else s.get("data", s.get("sports", []))
            if isinstance(sports, dict):
                sports = sports.get("sports", sports.get("data", []))
            print("sports:", json.dumps(sports)[:600])
        except Exception as e:
            print("ERROR", e)

        # 3. Teams (all leagues)
        print("\n=== 3. TEAMS per league ===")
        for lg in ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "WNBA", "UFC", "PGA", "SOCCER"]:
            try:
                t = await p._request("GET", f"/teams?leagueID={lg}&limit=5")
                teams = t if isinstance(t, list) else t.get("data", t.get("teams", []))
                n = len(teams) if isinstance(teams, list) else 0
                sample = teams[0].get("names", teams[0].get("name", "")) if n else "N/A"
                print(f"  {lg}: {n} teams, sample={str(sample)[:50]}")
            except Exception as e:
                print(f"  {lg}: ERROR {type(e).__name__} {str(e)[:60]}")

        # 4. Player stats (historical — Last-5 proof) for MLB/NBA/NFL
        print("\n=== 4. PLAYER STATS (historical Last-5) ===")
        for lg in ["MLB", "NBA", "NFL"]:
            try:
                pl = await p._request("GET", f"/players?leagueID={lg}&limit=3")
                players = pl if isinstance(pl, list) else pl.get("data", pl.get("players", []))
                if not players:
                    print(f"  {lg}: no players returned")
                    continue
                pid = players[0].get("playerID") or players[0].get("id")
                name = players[0].get("names", {}).get("display") or players[0].get("name", "?")
                print(f"  {lg}: sample player = {name} ({pid})")
                # Try stats endpoints
                for stats_ep in [f"/players/{pid}/stats", f"/players/{pid}/games", f"/players/{pid}/stats?leagueID={lg}"]:
                    try:
                        st = await p._request("GET", stats_ep)
                        print(f"    {stats_ep}: {type(st).__name__} {json.dumps(st)[:200]}")
                    except Exception as e:
                        print(f"    {stats_ep}: {type(e).__name__} {str(e)[:80]}")
            except Exception as e:
                print(f"  {lg}: players fetch ERROR {str(e)[:80]}")

        # 5. Bookmakers list
        print("\n=== 5. BOOKMAKERS ===")
        try:
            b = await p._request("GET", "/bookmakers")
            bks = b if isinstance(b, list) else b.get("data", b.get("bookmakers", []))
            print("bookmakers:", json.dumps(bks)[:500])
        except Exception as e:
            print("ERROR", e)

        # 6. DFS salary check (does SGO provide DFS slates/salaries?)
        print("\n=== 6. DFS SALARY/SLATE check ===")
        for ep in ["/dfs", "/dfs/slates", "/dfs/salaries", "/contests", "/slates", "/fantasy"]:
            try:
                r = await p._request("GET", ep)
                print(f"  {ep}: {json.dumps(r)[:150]}")
            except Exception as e:
                print(f"  {ep}: {type(e).__name__} {str(e)[:60]}")

        # 7. Stats summary
        print(f"\n=== 7. PROVIDER STATS === requests={p.stats.requests} objects={p.stats.objects_consumed} errors={p.stats.errors}")


asyncio.run(main())
