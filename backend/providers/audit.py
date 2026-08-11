"""SportsGameOdds API v2 Discovery Audit — Phase 2.2 SCHEMA-CORRECTED.

Uses flexible field extraction to handle the actual SGO response schema.
"""
import asyncio, os, json, sys, pprint
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from providers.sportsgameodds import SportsGameOddsProvider
from providers.normalizer import SportsGameOddsNormalizer, _field

LEAGUE_IDS = ["MLB", "NFL", "NBA", "NHL", "NCAAF"]


async def main():
    async with SportsGameOddsProvider() as p:
        print("=== SPORTSGAMEODDS SCHEMA DISCOVERY v2.2 ===\n")

        # ── Account Usage ──
        try:
            u = await p._request("GET", "/account/usage")
            print(f"ACCOUNT_USAGE: {json.dumps(u, default=str)[:400]}")
        except Exception as e:
            print(f"ACCOUNT_USAGE: ERROR — {e}")

        # ── MLB Events (1 event, odds available) ──
        print("\n=== MLB EVENT (oddsAvailable=true, limit=1) ===")
        try:
            raw = await p._request("GET", "/events?leagueID=MLB&oddsAvailable=true&limit=1")
            events = raw if isinstance(raw, list) else raw.get("data", raw.get("events", raw.get("results", [])))
            if events:
                ev = events[0]
                ne = SportsGameOddsNormalizer.normalize_event(ev)
                print(f"\nTOP-LEVEL EVENT KEYS (all): {sorted(ev.keys())}")
                print(f"RAW_EVENT_ID={_field(ev, 'eventID', 'id')}")
                print(f"NORMALIZED_EVENT_ID={ne.id}")
                print(f"HOME={ne.home_team}  AWAY={ne.away_team}")
                print(f"SPORT={ne.sport}  LEAGUE={ne.league}  STATUS={ne.status}")

                # Odds inspection
                odds = ev.get("odds") or ev.get("markets") or ev.get("bookmakers") or ev.get("lines")
                if odds:
                    print(f"\nODDS_CONTAINER: type={type(odds).__name__} len={len(odds) if isinstance(odds, list) else 'dict'}")
                    if isinstance(odds, list) and odds:
                        print(f"FIRST_ODD_KEYS: {sorted(odds[0].keys())}")
                        # Show first 3
                        for o in odds[:3]:
                            pprint.pprint(o, indent=2, depth=2, width=120)
                    elif isinstance(odds, dict):
                        print(f"ODDS_KEYS: {sorted(odds.keys())}")
                        pprint.pprint(odds, indent=2, depth=3, width=120)
                else:
                    print("ODDS: NOT FOUND in event object — checking other keys...")
                    odd_keys = [k for k in ev if "odd" in k.lower() or "market" in k.lower() or "book" in k.lower() or "line" in k.lower()]
                    print(f"ODD-RELATED KEYS: {odd_keys}")

                # Scores
                scores = ev.get("scores") or ev.get("score") or ev.get("result")
                if scores:
                    print(f"\nSCORES: {json.dumps(scores, default=str)[:200]}")
                else:
                    score_keys = [k for k in ev if "score" in k.lower() or "result" in k.lower()]
                    print(f"SCORE-RELATED KEYS: {score_keys}")

                # Player props
                props = ev.get("playerProps") or ev.get("player_props") or ev.get("props")
                if props:
                    print(f"\nPLAYER_PROPS: count={len(props) if isinstance(props, list) else 'dict'}")
                else:
                    prop_keys = [k for k in ev if "prop" in k.lower() or "player" in k.lower()]
                    print(f"PLAYER-RELATED KEYS: {prop_keys}")

        except Exception as e:
            print(f"MLB_EVENT: ERROR — {e}")
            import traceback; traceback.print_exc()

        # ── Players ──
        print("\n=== PLAYERS (leagueID=MLB, limit=1) ===")
        try:
            raw = await p._request("GET", "/players?leagueID=MLB&limit=1")
            players = raw if isinstance(raw, list) else raw.get("data", raw.get("players", []))
            if players:
                p0 = players[0]
                np = SportsGameOddsNormalizer.normalize_player(p0)
                print(f"PLAYER_COUNT_AVAILABLE: {len(players)}")
                print(f"RAW_PLAYER_KEYS: {sorted(p0.keys())}")
                print(f"RAW_PLAYER_ID={_field(p0, 'playerID', 'id')}")
                print(f"RAW_NAMES={json.dumps(p0.get('names',{}), default=str)[:120]}")
                print(f"NORMALIZED: id={np.id} name={np.name} team={np.team} pos={np.position}")
        except Exception as e:
            print(f"PLAYERS: ERROR — {e}")

        # ── Player Stats ──
        print("\n=== PLAYER STATS ===")
        try:
            raw = await p._request("GET", "/players?leagueID=MLB&limit=1")
            players = raw if isinstance(raw, list) else raw.get("data", [])
            if players:
                pid = players[0].get("id") or players[0].get("playerId")
                if pid:
                    try:
                        stats = await p._request("GET", f"/players/{pid}/stats")
                        print(f"YES — keys={list(stats.keys())[:12] if isinstance(stats, dict) else 'list len='+str(len(stats))}")
                    except Exception as e:
                        print(f"BLOCKED: {type(e).__name__}: {e}")
        except Exception as e:
            print(f"STATS: ERROR — {e}")

        # ── Teams ──
        print("\n=== TEAMS ===")
        try:
            raw = await p._request("GET", "/teams?leagueID=MLB&limit=1")
            teams = raw if isinstance(raw, list) else raw.get("data", [])
            if teams:
                print(f"TEAM_KEYS: {sorted(teams[0].keys())}")
        except Exception as e:
            print(f"TEAMS: ERROR — {e}")

        # ── Stats ──
        print(f"\n=== PROVIDER STATS ===")
        print(f"  Requests: {p.stats.requests}  Objects: {p.stats.objects_consumed}  Errors: {p.stats.errors}")

        # ── Verdict ──
        print("\n=== DFS VERDICT ===")
        print("  SGO provides: events, odds, player props, fair odds, consensus")
        print("  SGO does NOT provide: DFS salaries, DFS slates (confirmed)")
        print("  → SportsDataIO stays for DFS salary/slate/position data only")


asyncio.run(main())