"""SportsGameOdds API Discovery Audit — Phase 2.

Tests SGO API v2 against the free/trial account to determine
exactly what data is available for SPORTBOOK ME DFS AI.

Usage:
    SPORTSGAMEODDS_API_KEY=xxx python3 providers/audit.py
"""

import asyncio
import os
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from providers.sportsgameodds import SportsGameOddsProvider


async def check(path: str, label: str, paginated: bool = False) -> dict:
    """Test an endpoint and return {status, count, sample_keys}."""
    try:
        result = await p._request("GET", path, paginated=paginated)
        if isinstance(result, list):
            return {"label": label, "ok": True, "count": len(result),
                    "sample": result[0] if result else None}
        return {"label": label, "ok": True, "count": 1,
                "keys": list(result.keys())[:10] if isinstance(result, dict) else []}
    except Exception as e:
        return {"label": label, "ok": False, "error": str(e)[:120]}


async def main():
    global p
    async with SportsGameOddsProvider() as p:
        print("=== SPORTSGAMEODDS API DISCOVERY AUDIT ===\n")

        # Account
        r = await check("/account", "Account/plan")
        print(f"Account: {r}")

        # Sports
        r = await check("/sports", "Sports", paginated=True)
        sports_list = []
        if r.get("ok") and r.get("sample"):
            sports_list = [s.get("name") or s.get("slug") or s.get("id") for s in (r.get("count") and [r["sample"]]) or []]
        print(f"Sports: count={r.get('count')}")

        # Leagues
        for sport in ["mlb", "nfl", "nba", "nhl", "ncaaf", "ncaab", "ufc"]:
            r = await check(f"/leagues?sport={sport}", f"Leagues/{sport}")
            count = r.get("count", 0)
            sample = r.get("sample", {})
            name = sample.get("name", sample.get("id", "")) if sample else ""
            print(f"  {sport}: {count} leagues — {name}" if count else f"  {sport}: NONE")

        # MLB Events
        r = await check("/events?league=mlb", "Events/MLB", paginated=True)
        print(f"\nMLB Events: {r.get('count', 0)}")
        if r.get("sample"):
            ev = r["sample"]
            print(f"  Sample: {ev.get('home_team','?')} vs {ev.get('away_team','?')} — {ev.get('status','?')}")

        # Odds
        events_sample = []
        if r.get("count") and r["sample"]:
            events_sample = [r["sample"]] if r["count"] > 0 else []
        for ev in events_sample[:2]:
            eid = ev.get("id") or ev.get("event_id")
            if eid:
                odds_r = await check(f"/odds/{eid}", f"Odds/{eid}")
                print(f"  Odds for {eid}: keys={odds_r.get('keys')}")

        # Player Props
        if events_sample:
            eid = events_sample[0].get("id") or events_sample[0].get("event_id")
            if eid:
                rp = await check(f"/props/players/{eid}", "PlayerProps")
                print(f"\nPlayer Props: count={rp.get('count', 0)}")
                if rp.get("sample"):
                    print(f"  Sample: {json.dumps(rp['sample'], default=str)[:200]}")

        # Fair Odds + Consensus
        if events_sample:
            eid = events_sample[0].get("id") or events_sample[0].get("event_id")
            if eid:
                for ep in ["/fair-odds/", "/consensus/"]:
                    r = await check(f"{ep}{eid}", ep.strip("/"))
                    print(f"  {ep.strip('/')}: ok={r.get('ok')}")

        # DFS-specific queries
        print("\n=== DFS DATA ===")
        for ep in ["/dfs/salaries", "/dfs/slates"]:
            try:
                r = await p._request("GET", ep)
                c = len(r) if isinstance(r, list) else 1
                print(f"  {ep}: FOUND ({c} items)")
            except Exception as e:
                print(f"  {ep}: NOT FOUND ({type(e).__name__})")

        # Usage stats
        print(f"\n=== PROVIDER STATS ===")
        print(f"  Requests: {p.stats.requests}")
        print(f"  Objects consumed: {p.stats.objects_consumed}")
        print(f"  Errors: {p.stats.errors}")


asyncio.run(main())