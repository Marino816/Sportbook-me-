#!/usr/bin/env python3
"""
SGO PRODUCTION INTELLIGENCE POPULATION — MLB Slate 1 DraftKings

Fetches real SGO market data, matches to DK slate players,
computes native projections, and runs the CP-SAT optimizer.

No SportsDataIO. No 0.01 customer projections.
"""
import asyncio, os, sys, json, time, re
from collections import defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Credentials come from the environment only. Never hardcode provider keys.
SGO_API_KEY = os.environ.get("SPORTSGAMEODDS_API_KEY", "").strip()
DB_URL = os.environ.get("DATABASE_URL", "").strip()
SGO_BASE = os.environ.get("SPORTSGAMEODDS_BASE_URL", "https://api.sportsgameodds.com/v2")
SLATE_ID = int(os.environ.get("SLATE_ID", "1"))
PLATFORM = os.environ.get("PLATFORM", "draftkings")
SPORT = os.environ.get("SPORT", "MLB")
LINEUP_COUNT = int(os.environ.get("LINEUP_COUNT", "3"))

if not SGO_API_KEY:
    raise SystemExit("SPORTSGAMEODDS_API_KEY is required")
if not DB_URL:
    raise SystemExit("DATABASE_URL is required")

import httpx
from models.database import _init_engine, get_db
from sqlalchemy import select
from dfs.db import DFSSlate, DFSPlayer
from projection.native import compute_projections, projections_to_pool
from optimizer.mlb_optimizer import MLBOptimizer

# ── SGO Client ────────────────────────────────────────────────
class SGOClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=SGO_BASE,
            headers={"x-api-key": SGO_API_KEY, "Accept": "application/json"},
            timeout=httpx.Timeout(30),
        )
        self.rate_limit = 1.2
        self._last = 0.0
        self.stats = {"requests": 0, "errors": 0}

    async def _rl(self):
        now = time.monotonic()
        gap = now - self._last
        if gap < self.rate_limit:
            await asyncio.sleep(self.rate_limit - gap)
        self._last = time.monotonic()

    async def _get(self, path, params=None):
        await self._rl()
        self.stats["requests"] += 1
        for attempt in range(3):
            try:
                resp = await self.client.get(path, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                self.stats["errors"] += 1
                if attempt == 2:
                    print(f"  SGO ERROR {path}: {e}")
                    return None
                await asyncio.sleep(1 * (attempt + 1))
        return None

    async def get_events(self, league_id="MLB"):
        return await self._get("/events", {
            "leagueID": league_id,
            "oddsAvailable": "true",
            "includeAltLines": "true",
            "includeOpenCloseOdds": "true",
            "limit": "50",
        })

    async def get_player_props(self, event_id):
        """Extract nested player props from /v2/events — never /props/players/{id}."""
        payload = await self._get("/events", {
            "eventID": event_id,
            "oddsAvailable": "true",
            "includeAltLines": "true",
            "limit": "1",
        })
        return payload

    async def get_odds(self, event_id):
        """Nested event odds from /v2/events — never /odds/{id}."""
        return await self._get("/events", {
            "eventID": event_id,
            "oddsAvailable": "true",
            "includeAltLines": "true",
            "includeOpenCloseOdds": "true",
            "limit": "1",
        })

    async def get_fair_odds(self, event_id):
        return await self.get_odds(event_id)

    async def get_consensus(self, event_id):
        return await self.get_odds(event_id)

    async def close(self):
        await self.client.aclose()


# ── Team Name Mapping ─────────────────────────────────────────
# SGO uses full team names; DK uses abbreviations
DK_TO_SGO_TEAM = {
    "ARI": "Arizona Diamondbacks",
    "ATH": "Athletics",  # or "Oakland Athletics" / "Sacramento Athletics"
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CIN": "Cincinnati Reds",
    "CWS": "Chicago White Sox",
    "COL": "Colorado Rockies",
    "HOU": "Houston Astros",
    "KC":  "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "PHI": "Philadelphia Phillies",
    "SD":  "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SF":  "San Francisco Giants",
    "STL": "St. Louis Cardinals",
    "TB":  "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
}

# Also try abbreviations
DK_ABBREV = {k: k for k in DK_TO_SGO_TEAM}


def _fuzzy_match(a, b, threshold=0.75):
    """Case-insensitive fuzzy name match."""
    a = a.lower().strip()
    b = b.lower().strip()
    if a == b:
        return 1.0
    # Remove common words
    for word in ["the", "los", "san", "st.", "new"]:
        a = a.replace(word, "")
        b = b.replace(word, "")
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def match_team(dk_abbrev, sgo_names):
    """Match a DK team abbreviation to one of the SGO team name strings."""
    # Try direct map
    full = DK_TO_SGO_TEAM.get(dk_abbrev, "")
    for sgo in sgo_names:
        sgo_lower = sgo.lower()
        # Check abbreviation
        if dk_abbrev.lower() == sgo_lower[:3]:
            return sgo
        # Check full name
        if full and _fuzzy_match(full, sgo, 0.7) > 0.7:
            return sgo
        # Check partial
        if dk_abbrev.lower() in sgo_lower:
            return sgo
    return None


# ── Main Pipeline ─────────────────────────────────────────────
async def main():
    print("=" * 70)
    print("SGO PRODUCTION INTELLIGENCE — MLB DK Slate 1")
    print("=" * 70)

    # 1. Load slate players from DB
    _init_engine()
    async for db in get_db():
        r = await db.execute(select(DFSSlate).where(DFSSlate.id == SLATE_ID))
        slate = r.scalars().first()
        print(f"\nSlate: {slate.slate_name} | {slate.platform} | {slate.sport}")
        print(f"Status: {slate.status} | {slate.player_count} players")

        r2 = await db.execute(
            select(DFSPlayer).where(DFSPlayer.slate_id == SLATE_ID)
        )
        db_players = r2.scalars().all()
        break

    # Build player lookup by (name, team)
    player_map = {}  # (name_lower, team) -> DFSPlayer
    for p in db_players:
        key = (p.player_name.lower().strip(), p.team)
        player_map[key] = p

    # 2. Identify the 12 games
    games = {
        ("ARI", "COL"), ("ATH", "TB"), ("ATL", "NYM"),
        ("BAL", "MIN"), ("BOS", "TOR"), ("CIN", "CWS"),
        ("HOU", "SF"),  ("KC", "LAD"),  ("LAA", "TEX"),
        ("MIL", "SD"),  ("NYY", "SEA"), ("PHI", "STL"),
    }
    print(f"\n12 DK games to match:")
    for a, b in sorted(games):
        print(f"  {a} @ {b}")

    # 3. Fetch SGO events
    print("\n─── Fetching SGO MLB Events ───")
    sgo = SGOClient()
    try:
        events_data = await sgo.get_events("MLB")
    except Exception as e:
        print(f"ERROR fetching events: {e}")
        return

    if not events_data:
        print("No events returned. Check API key / quota.")
        return

    # SGO returns data in various formats
    if isinstance(events_data, dict):
        events_list = events_data.get("data", events_data.get("events", []))
    else:
        events_list = events_data

    if not events_list and isinstance(events_data, list):
        events_list = events_data

    print(f"SGO returned {len(events_list)} MLB events")

    # 4. Match SGO events to DK games
    # Extract team info from each SGO event
    matched_events = {}  # (dk_team1, dk_team2) -> sgo_event_id

    for evt in events_list:
        if not isinstance(evt, dict):
            continue
        eid = evt.get("eventID") or evt.get("id") or ""
        if not eid:
            continue

        # Try to get team names
        home = ""
        away = ""
        teams = evt.get("teams", {})
        if isinstance(teams, dict):
            home_obj = teams.get("home", teams.get("homeTeam", {}))
            away_obj = teams.get("away", teams.get("awayTeam", {}))
            if isinstance(home_obj, dict):
                names = home_obj.get("names", {})
                home = names.get("display", names.get("full", home_obj.get("name", "")))
            if isinstance(away_obj, dict):
                names = away_obj.get("names", {})
                away = names.get("display", names.get("full", away_obj.get("name", "")))

        # Also try flat fields
        if not home:
            home = evt.get("homeTeamName", evt.get("homeTeam", ""))
        if not away:
            away = evt.get("awayTeamName", evt.get("awayTeam", ""))

        if not home or not away:
            continue

        # Find what DK abbreviations match
        sgo_teams = [home, away]
        dk_home = None
        dk_away = None
        for dk_abbrev, full_name in DK_TO_SGO_TEAM.items():
            for st in sgo_teams:
                ratio = _fuzzy_match(full_name, st, 0.6)
                if ratio > 0.6 or dk_abbrev.lower() in st.lower():
                    if st == home:
                        dk_home = dk_abbrev
                    else:
                        dk_away = dk_abbrev

        if dk_home and dk_away:
            key = tuple(sorted([dk_home, dk_away]))
            if key in games and key not in matched_events:
                matched_events[key] = {
                    "event_id": eid,
                    "home_sgo": home,
                    "away_sgo": away,
                    "dk_home": dk_home,
                    "dk_away": dk_away,
                }
                print(f"  MATCHED: {dk_home} @ {dk_away} → SGO {eid} ({away} @ {home})")

    print(f"\nMatched {len(matched_events)}/12 games")

    # 5. Fetch player props for each matched event
    print("\n─── Fetching Player Props ───")
    all_props = {}  # event_id -> list of prop dicts
    sgo_fantasy_markets = {}  # player_id -> fantasyScore line
    sgo_player_names = {}  # player_id -> name

    for (dk1, dk2), info in matched_events.items():
        eid = info["event_id"]
        print(f"\n  Event {eid} ({info['dk_away']} @ {info['dk_home']}):")
        
        # Fetch player props
        props = await sgo.get_player_props(eid)
        if not props:
            print(f"    No props returned")
            continue

        # Props can be in various formats
        if isinstance(props, dict):
            props_list = props.get("data", props.get("props", props.get("markets", [])))
        else:
            props_list = props

        if not props_list:
            print(f"    Empty props list")
            continue

        print(f"    {len(props_list)} prop entries")

        for prop_entry in props_list:
            if not isinstance(prop_entry, dict):
                continue

            # Extract player info
            player = prop_entry.get("player", prop_entry.get("playerInfo", {}))
            if isinstance(player, dict):
                pid = player.get("playerID", player.get("id", ""))
                names = player.get("names", {})
                pname = names.get("display", names.get("full", player.get("name", "")))
                pteam = player.get("teamID", player.get("team", ""))
            else:
                pid = prop_entry.get("playerID", "")
                pname = prop_entry.get("playerName", "")
                pteam = prop_entry.get("teamID", prop_entry.get("team", ""))

            if not pid:
                continue

            # Store player name
            if pid not in sgo_player_names and pname:
                sgo_player_names[pid] = pname

            # Look for markets
            markets = prop_entry.get("markets", prop_entry.get("market", []))
            if isinstance(markets, dict):
                markets = [markets]
            elif not isinstance(markets, list):
                # Single market
                markets = [prop_entry] if prop_entry.get("line") else []

            props_for_player = []
            for mkt in markets:
                mkt_name = mkt.get("market", mkt.get("marketName", mkt.get("name", "")))
                mkt_line = mkt.get("line", mkt.get("value", mkt.get("lineValue")))
                mkt_book = mkt.get("bookmaker", mkt.get("book", ""))

                if not mkt_name or mkt_line is None:
                    continue

                try:
                    mkt_line = float(mkt_line)
                except (ValueError, TypeError):
                    continue

                # Check for fantasyScore market
                if "fantasy" in mkt_name.lower() or "fantasyScore" in str(mkt_name).lower():
                    if pid not in sgo_fantasy_markets:
                        sgo_fantasy_markets[pid] = mkt_line
                        print(f"      🎯 FANTASY: {pname or pid} = {mkt_line}")

                props_for_player.append({
                    "market": mkt_name,
                    "line": mkt_line,
                    "book": mkt_book,
                })

            if props_for_player:
                if pid not in all_props:
                    all_props[pid] = []
                all_props[pid].extend(props_for_player)

    print(f"\n  Total SGO players with props: {len(all_props)}")
    print(f"  Players with fantasyScore market: {len(sgo_fantasy_markets)}")

    # 6. Also fetch game totals, moneylines, spreads
    print("\n─── Fetching Game Odds ───")
    game_contexts = {}
    for (dk1, dk2), info in matched_events.items():
        eid = info["event_id"]
        odds = await sgo.get_odds(eid)
        if odds:
            # Extract DK book lines
            dk_lines = None
            books = odds.get("books", odds.get("bookmakers", []))
            if not books and isinstance(odds, dict):
                books = odds.get("data", [])
            for book in books:
                book_name = book.get("bookmaker", book.get("book", "")).lower()
                if "draftking" in book_name:
                    dk_lines = book
                    break
            if not dk_lines and books:
                dk_lines = books[0]  # fallback to first book

            if dk_lines:
                game_contexts[eid] = {
                    "total": dk_lines.get("total", dk_lines.get("totalOver", dk_lines.get("over"))),
                    "spread": dk_lines.get("spread", dk_lines.get("pointSpread")),
                    "moneyline_home": dk_lines.get("moneylineHome", dk_lines.get("homeMoneyline")),
                    "moneyline_away": dk_lines.get("moneylineAway", dk_lines.get("awayMoneyline")),
                }
                print(f"  {eid}: Total={game_contexts[eid]['total']}, "
                      f"ML Home={game_contexts[eid]['moneyline_home']}, "
                      f"ML Away={game_contexts[eid]['moneyline_away']}")

    # 7. Map SGO players to DK slate players
    print("\n─── Mapping SGO → DK Players ───")
    sgo_to_dk = {}  # sgo_player_id -> dk_player_id (sbme_player_id)
    dk_matched = set()

    for sgo_pid, pname in sgo_player_names.items():
        if not pname:
            continue
        name_lower = pname.lower().strip()
        
        # Try exact match
        for (dk_name, dk_team), dk_player in player_map.items():
            if dk_player.mapping_status == "MATCHED":
                continue  # already matched
            if dk_name == name_lower:
                sgo_to_dk[sgo_pid] = dk_player.sbme_player_id or str(dk_player.id)
                dk_matched.add(dk_player.id)
                break
        
        # Try fuzzy
        if sgo_pid not in sgo_to_dk:
            best_ratio = 0
            best_dk = None
            for (dk_name, dk_team), dk_player in player_map.items():
                if dk_player.id in dk_matched:
                    continue
                ratio = SequenceMatcher(None, dk_name, name_lower).ratio()
                if ratio > best_ratio and ratio >= 0.85:
                    best_ratio = ratio
                    best_dk = dk_player
            if best_dk:
                sgo_to_dk[sgo_pid] = best_dk.sbme_player_id or str(best_dk.id)
                dk_matched.add(best_dk.id)

    print(f"  SGO→DK mappings: {len(sgo_to_dk)}")
    print(f"  DK players matched: {len(dk_matched)}")

    # 8. Compute projections
    print("\n─── Computing Native Projections ───")
    
    # Build SGO intelligence dict for projection engine
    sgo_intelligence = {}
    for sgo_pid, dk_pid in sgo_to_dk.items():
        intel = {}
        
        # Fantasy score market
        fs = sgo_fantasy_markets.get(sgo_pid)
        if fs:
            intel["fantasyScore"] = fs
            intel["fantasyMarketLine"] = fs
        
        # Player props
        props_list = all_props.get(sgo_pid, [])
        props_dict = {}
        for p in props_list:
            mkt = p["market"]
            # Normalize market names to our model's keys
            mkt_lower = mkt.lower().replace(" ", "").replace("_", "")
            
            # Map common SGO market names to our prop keys
            key_map = {
                "hits": "hits",
                "totalhits": "hits",
                "homeruns": "homeRuns",
                "home_run": "homeRuns",
                "rbi": "rbi",
                "runsbattedin": "rbi",
                "totalbases": "totalBases",
                "stolenbases": "stolenBases",
                "stolen_base": "stolenBases",
                "walks": "walks",
                "basesonballs": "walks",
                "battingstrikeouts": "battingStrikeouts",
                "strikeouts": "battingStrikeouts",
                "pitchingstrikeouts": "pitchingStrikeouts",
                "pitcherstrikeouts": "pitchingStrikeouts",
                "outs": "pitchingOuts",
                "pitchingouts": "pitchingOuts",
                "earnedruns": "pitchingEarnedRuns",
                "pitchingearnedruns": "pitchingEarnedRuns",
                "hitsallowed": "pitchingHits",
                "pitchinghits": "pitchingHits",
                "pitchingwalks": "pitchingWalks",
                "walksallowed": "pitchingWalks",
            }
            
            mapped_key = None
            for k, v in key_map.items():
                if k in mkt_lower:
                    mapped_key = v
                    break
            
            if mapped_key:
                # Take the best (highest for positive props, lowest for negative)
                # For simplicity, use average or first value
                if mapped_key not in props_dict:
                    props_dict[mapped_key] = p["line"]
                else:
                    # Average multiple books for same prop
                    props_dict[mapped_key] = (props_dict[mapped_key] + p["line"]) / 2
        
        if props_dict:
            intel["props"] = props_dict
        
        if intel:
            sgo_intelligence[dk_pid] = intel

    # Build player list for projection engine
    projection_pool = []
    for p in db_players:
        pid = p.sbme_player_id or str(p.id)
        proj_entry = {
            "id": pid,
            "name": p.player_name,
            "position": p.position,
            "salary": p.salary,
            "team": p.team,
            "opponent": p.opponent or "",
            "roster_position": p.position,
        }
        # Inject SGO intelligence if available
        sgo_data = sgo_intelligence.get(pid, {})
        if sgo_data.get("fantasyScore"):
            proj_entry["fantasyMarketLine"] = sgo_data["fantasyScore"]
        if sgo_data.get("props"):
            proj_entry["props"] = sgo_data["props"]
        projection_pool.append(proj_entry)

    # Run projection engine
    projections = compute_projections(SPORT, projection_pool, sgo_intelligence)
    
    # Count sources
    fantasy_count = sum(1 for p in projections if p.projection_source == "SGO_FANTASY_MARKET")
    prop_count = sum(1 for p in projections if p.projection_source == "PROP_BASED")
    unavailable = sum(1 for p in projections if p.projection_source == "UNAVAILABLE")
    
    print(f"  SGO_FANTASY_MARKET: {fantasy_count}")
    print(f"  PROP_BASED: {prop_count}")
    print(f"  UNAVAILABLE: {unavailable}")

    # Convert to optimizer pool
    pool = projections_to_pool(projections)

    # Apply fallback: players with 0.0 projection get 0.01 for solver
    zero_count = sum(1 for p in pool if p["projected_fp"] == 0.0)
    for p in pool:
        if p["projected_fp"] == 0.0:
            p["projected_fp"] = 0.01
            p["projection_source"] = "INTERNAL_SAFETY"

    print(f"\n  Pool: {len(pool)} total, {zero_count} zero-projection (0.01 safety)")

    # 9. Run the CP-SAT optimizer
    print(f"\n─── Running DK MLB Optimizer (requested={LINEUP_COUNT}) ───")
    
    opt = MLBOptimizer(pool, platform=PLATFORM, strategy="balanced")
    lineups = opt.generate(count=LINEUP_COUNT)
    
    print(f"  Requested: {LINEUP_COUNT}")
    print(f"  Generated: {len(lineups)}")

    if lineups:
        for i, lu in enumerate(lineups):
            total_sal = lu.get("total_salary", 0)
            proj = lu.get("projected_score", 0)
            players = lu.get("players", [])
            print(f"\n  Lineup {i+1}:")
            print(f"    Salary: ${total_sal:,} / Projected: {proj}")
            for p in players:
                source = p.get("projection_source", "")
                marker = ""
                if source == "SGO_FANTASY_MARKET":
                    marker = " 🎯"
                elif source == "PROP_BASED":
                    marker = " 📊"
                elif source == "INTERNAL_SAFETY":
                    marker = " ⚠️"
                elif source == "UNAVAILABLE":
                    marker = " ❌"
                print(f"    {p.get('roster_slot', '?'):4s} {p.get('name', ''):20s} "
                      f"${p.get('salary', 0):,} → {p.get('projected_fp', 0):.1f} fp{marker}")
    else:
        print("  NO LINEUPS GENERATED — check constraints/pool")

    # 10. Print player intelligence samples
    print(f"\n─── Player Intelligence Samples ───")
    fantasy_players = [p for p in projections if p.projection_source == "SGO_FANTASY_MARKET"]
    prop_players = [p for p in projections if p.projection_source == "PROP_BASED"]
    
    if fantasy_players:
        print(f"\n  🎯 SGO_FANTASY_MARKET ({len(fantasy_players)}):")
        for p in sorted(fantasy_players, key=lambda x: x.base_projection, reverse=True)[:10]:
            print(f"    {p.player_name:25s} {p.position:4s} ${p.salary:5d} → {p.base_projection:.1f} fp")
    
    if prop_players:
        print(f"\n  📊 PROP_BASED ({len(prop_players)}):")
        for p in sorted(prop_players, key=lambda x: x.base_projection, reverse=True)[:10]:
            print(f"    {p.player_name:25s} {p.position:4s} ${p.salary:5d} → {p.base_projection:.1f} fp "
                  f"[{', '.join(p.props_used[:3])}]")

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"  SGO Events fetched:      {len(events_list)}")
    print(f"  DK Games matched:        {len(matched_events)}/12")
    print(f"  SGO Players with props:  {len(all_props)}")
    print(f"  SGO→DK mappings:         {len(sgo_to_dk)}")
    print(f"  SGO_FANTASY_MARKET:      {fantasy_count}")
    print(f"  PROP_BASED_COUNT:        {prop_count}")
    print(f"  UNAVAILABLE_COUNT:       {unavailable}")
    print(f"  Pool size:               {len(pool)}")
    print(f"  Lineups requested:       {LINEUP_COUNT}")
    print(f"  Lineups generated:       {len(lineups)}")
    print(f"  SPORTSDATAIO_CALLED:     false")
    print(f"  SGO API requests:        {sgo.stats['requests']} ({sgo.stats['errors']} errors)")

    await sgo.close()


if __name__ == "__main__":
    asyncio.run(main())