"""SportsGameOdds API v2 Discovery Audit — Phase 2.1 CORRECTED.

Uses official documented endpoints and leagueID format.
Determines exactly what the free account provides for SB ME.

Usage:
    SPORTSGAMEODDS_API_KEY=*** python3 providers/audit.py
"""

import asyncio, os, json, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from providers.sportsgameodds import SportsGameOddsProvider

LEAGUE_IDS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "UFC"]

# Bookmakers we care about for DFS intelligence
TARGET_BOOKS = {"DraftKings", "FanDuel", "BetMGM", "Caesars", "ESPN BET", "ESPNBET"}


async def main():
    async with SportsGameOddsProvider() as p:
        print("=== SPORTSGAMEODDS DISCOVERY AUDIT v2.1 ===\n")

        # ── Account Usage ──
        try:
            usage = await p._request("GET", "/account/usage")
            print(f"ACCOUNT_USAGE: {json.dumps(usage, default=str)[:300]}")
        except Exception as e:
            print(f"ACCOUNT_USAGE: ERROR — {e}")

        # ── Events per league (odds available, 1 event for cost control) ──
        print("\n=== EVENTS (oddsAvailable=true, limit=1) ===")
        event_samples = {}
        for lid in LEAGUE_IDS:
            try:
                data = await p._request("GET", f"/events?leagueID={lid}&oddsAvailable=true&limit=1")
                events = data if isinstance(data, list) else data.get("data", data.get("events", []))
                count = len(events)
                print(f"  {lid}: {count} event(s)")
                if events:
                    ev = events[0]
                    print(f"    ID={ev.get('id','?')}  {ev.get('home_team','?')} vs {ev.get('away_team','?')}  status={ev.get('status','?')}")
                    event_samples[lid] = ev
            except Exception as e:
                print(f"  {lid}: ERROR — {e}")

        # ── Odds detail (one MLB event) ──
        print("\n=== ODDS DETAIL (MLB event) ===")
        mlb_ev = event_samples.get("MLB")
        if mlb_ev:
            eid = mlb_ev.get("id") or mlb_ev.get("event_id")
            if eid:
                try:
                    odds = await p._request("GET", f"/odds/{eid}")
                    books = odds.get("books", odds.get("bookmakers", []))
                    book_names = {b.get("bookmaker", b.get("book", "?")) for b in books}
                    found = TARGET_BOOKS & book_names
                    print(f"  Bookmakers present: {book_names}")
                    print(f"  Target books found: {found}")

                    # Check for DK/FD-specific fields
                    sample_book = books[0] if books else {}
                    print(f"  Fields per book: {list(sample_book.keys())[:10]}")

                    # Moneyline / Spread / Total present?
                    has_ml = any(b.get("moneyline_home") or b.get("moneylineHome") for b in books)
                    has_spread = any(b.get("spread") or b.get("spread_home") for b in books)
                    has_total = any(b.get("total") or b.get("total_over") for b in books)
                    print(f"  MONEYLINES={'YES' if has_ml else 'NO'}")
                    print(f"  SPREADS={'YES' if has_spread else 'NO'}")
                    print(f"  TOTALS={'YES' if has_total else 'NO'}")

                    # Scan for DFS salary fields in odds response
                    all_keys = set()
                    for b in books:
                        all_keys.update(b.keys())
                    dfs_keys = {k for k in all_keys if "salary" in k.lower() or "dfs" in k.lower() or "slate" in k.lower()}
                    print(f"  DFS-RELATED KEYS IN ODDS: {dfs_keys or 'NONE'}")
                except Exception as e:
                    print(f"  ODDS: ERROR — {e}")

        # ── Player Props ──
        print("\n=== PLAYER PROPS ===")
        if mlb_ev:
            eid = mlb_ev.get("id") or mlb_ev.get("event_id")
            if eid:
                try:
                    props = await p._request("GET", f"/props/players/{eid}")
                    plist = props if isinstance(props, list) else props.get("data", props.get("props", []))
                    print(f"  Count: {len(plist)}")
                    if plist:
                        print(f"  Sample: {json.dumps(plist[0], default=str)[:200]}")
                except Exception as e:
                    print(f"  PLAYER_PROPS: ERROR — {type(e).__name__}: {e}")

        # ── Fair Odds + Consensus ──
        print("\n=== FAIR ODDS / CONSENSUS ===")
        if mlb_ev:
            eid = mlb_ev.get("id") or mlb_ev.get("event_id")
            if eid:
                for ep_name, ep_path in [("FAIR_ODDS", f"/fair-odds/{eid}"),
                                          ("CONSENSUS", f"/consensus/{eid}")]:
                    try:
                        r = await p._request("GET", ep_path)
                        print(f"  {ep_name}: YES — keys={list(r.keys())[:8] if isinstance(r, dict) else 'list'}")
                    except Exception as e:
                        print(f"  {ep_name}: NO — {type(e).__name__}")

        # ── Players ──
        print("\n=== PLAYERS (MLB, limit=1) ===")
        try:
            players = await p._request("GET", "/players?league=MLB&limit=1")
            plist = players if isinstance(players, list) else players.get("data", [])
            if plist:
                pkeys = list(plist[0].keys())[:15]
                print(f"  Count: {len(plist)}  Keys: {pkeys}")
                dfs_in_player = [k for k in pkeys if "salary" in k.lower() or "dfs" in k.lower() or "slate" in k.lower() or "position" in k.lower()]
                print(f"  DFS-RELATED PLAYER KEYS: {dfs_in_player or 'NONE'}")
        except Exception as e:
            print(f"  PLAYERS: ERROR — {e}")

        # ── Player Stats ──
        print("\n=== PLAYER STATS ===")
        try:
            pdata = await p._request("GET", "/players?league=MLB&limit=1")
            plist = pdata if isinstance(pdata, list) else pdata.get("data", [])
            if plist:
                pid = plist[0].get("id") or plist[0].get("player_id")
                if pid:
                    try:
                        stats = await p._request("GET", f"/players/{pid}/stats")
                        print(f"  YES — keys={list(stats.keys())[:10] if isinstance(stats, dict) else 'list'}")
                    except Exception as e:
                        print(f"  NO — {type(e).__name__}")
        except Exception:
            print("  NO — could not fetch players")

        # ── Scores ──
        print("\n=== SCORES ===")
        if mlb_ev:
            eid = mlb_ev.get("id") or mlb_ev.get("event_id")
            if eid:
                try:
                    scores = await p._request("GET", f"/scores/{eid}")
                    print(f"  YES — keys={list(scores.keys())[:10]}")
                except Exception as e:
                    print(f"  NO — {type(e).__name__}")

        # ── Stats ──
        print(f"\n=== PROVIDER STATS ===")
        print(f"  Requests: {p.stats.requests}")
        print(f"  Objects consumed: {p.stats.objects_consumed}")
        print(f"  Errors: {p.stats.errors}")

        # ── DFS Verdict ──
        print("\n=== DFS VERDICT ===")
        print("  SportsGameOdds provides game/market/player/prop/odds intelligence.")
        print("  DFS salary/slate/position data: inspect keys above for 'salary'/'dfs'/'slate'.")
        print("  If none found: SportsDataIO stays as temporary DFS-only provider.")
        print("  Architecture: SGO = PRIMARY (intelligence) + SDIO = FALLBACK (DFS salaries only)")


asyncio.run(main())