"""
DraftKings DFS Contest CSV Parser.

Parses official DraftKings contest salary CSV exports into
normalized DFSContestPlayer objects.

DK CSV format:
  Position, Name + ID, Name, ID, Roster Position, Salary, Game Info,
  TeamAbbrev, AvgPointsPerGame

Example row:
  P, Tarik Skubal (12345), Tarik Skubal, 12345, SP, 10500,
  DET@CLE 08/11/2026 07:10PM ET, DET, 22.5
"""

import csv
import io
import re
import logging
from datetime import datetime
from typing import Optional

from dfs.models import DFSContestPlayer, DFSSlate

logger = logging.getLogger(__name__)

# Position normalization: DK position → our internal format
DK_POSITION_MAP = {
    "SP": "P", "RP": "P", "P": "P",
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "OF": "OF", "LF": "OF", "CF": "OF", "RF": "OF",
    "DH": "DH",
    # NFL
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
    "DST": "DST", "FLEX": "FLEX",
    # NBA
    "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C",
    "G": "G", "F": "F", "UTIL": "UTIL",
    # NHL
    "G": "G", "D": "D", "W": "W",
}


def _parse_dk_id(name_id: str) -> tuple[str, Optional[str]]:
    """Extract player name and ID from 'Name (ID)' format."""
    match = re.search(r'\((\d+)\)$', name_id.strip())
    if match:
        name = name_id[:match.start()].strip()
        pid = match.group(1)
        return name, pid
    return name_id.strip(), None


def _parse_game_info(game_info: str) -> tuple[str, str, Optional[datetime]]:
    """
    Parse 'TEAM@TEAM MM/DD/YYYY HH:MM PM ET' into (team, opponent, start_time).
    """
    parts = game_info.strip().split()
    if not parts:
        return "", "", None

    team_part = parts[0]  # "DET@CLE"
    teams = team_part.split("@")
    team = teams[0].strip() if len(teams) > 0 else ""
    opponent = teams[1].strip() if len(teams) > 1 else ""

    # Parse datetime
    start_time = None
    try:
        datetime_str = " ".join(parts[1:]).replace(" ET", "").replace(" PM", "PM").replace(" AM", "AM")
        from datetime import datetime
        start_time = datetime.strptime(datetime_str, "%m/%d/%Y %I:%M%p")
    except (ValueError, IndexError):
        pass

    return team, opponent, start_time


def parse_draftkings_csv(csv_content: str, slate_name: str = "DK Main") -> tuple[DFSSlate, list[DFSContestPlayer]]:
    """
    Parse a DraftKings contest CSV file into normalized DFS data.

    Returns DFSSlate with embedded player list.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    players = []
    sport = "MLB"  # default, detected from positions
    slate_id = f"dk-{slate_name.lower().replace(' ', '-')}"
    start_time = None
    positions_seen = set()

    for row in reader:
        pos_raw = (row.get("Roster Position") or row.get("Position") or "").strip()
        name_id = (row.get("Name + ID") or row.get("Name") or "").strip()
        salary_raw = (row.get("Salary") or "0").strip().replace(",", "").replace("$", "")
        game_info = (row.get("Game Info") or "").strip()
        team = (row.get("TeamAbbrev") or row.get("Team") or "").strip()

        try:
            salary = int(salary_raw)
        except ValueError:
            salary = 0

        name, pid = _parse_dk_id(name_id)
        # Handle multi-position: "2B/3B" → ["2B", "3B"]
        pos_parts = [p.strip() for p in pos_raw.split("/")]
        primary_pos = DK_POSITION_MAP.get(pos_parts[0], pos_parts[0])
        positions_seen.add(primary_pos)
        eligible = list({DK_POSITION_MAP.get(p, p) for p in pos_parts})
        team_abbrev, opponent, game_start = _parse_game_info(game_info)

        if game_start and start_time is None:
            start_time = game_start

        players.append(DFSContestPlayer(
            platform="draftkings",
            slate_id=slate_id,
            slate_name=slate_name,
            sport="",  # detected below
            start_time=start_time,
            player_id=pid or name,
            player_name=name,
            team=team or team_abbrev,
            opponent=opponent,
            position=primary_pos,
            eligible_positions=eligible if len(eligible) > 1 else [primary_pos],
            salary=salary,
            game_info=game_info,
            data_source="native",
        ))

    # Detect sport from positions
    if positions_seen & {"SP", "RP"}:
        sport = "MLB"
    elif positions_seen & {"QB", "RB", "WR", "TE"}:
        sport = "NFL"
    elif positions_seen & {"PG", "SG", "SF", "PF", "G", "F"}:
        sport = "NBA"
    elif positions_seen & {"G", "D", "W"}:
        sport = "NHL"

    for p in players:
        p.sport = sport

    return DFSSlate(
        platform="draftkings",
        slate_id=slate_id,
        slate_name=slate_name,
        sport=sport,
        start_time=start_time,
        player_count=len(players),
        salary_cap=50000,
        data_source="native",
    ), players


def parse_fanduel_csv(csv_content: str, slate_name: str = "FD Main") -> tuple[DFSSlate, list[DFSContestPlayer]]:
    """
    Parse a FanDuel contest CSV file.

    FD CSV format (typical):
      Id, First Name, Last Name, Position, FPPG, Played, Salary, Game, Team, Opponent, Injury
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    players = []
    sport = "MLB"
    slate_id = f"fd-{slate_name.lower().replace(' ', '-')}"
    positions_seen = set()

    for row in reader:
        pid = (row.get("Id") or row.get("ID") or "").strip()
        first = (row.get("First Name") or row.get("FirstName") or "").strip()
        last = (row.get("Last Name") or row.get("LastName") or "").strip()
        name = f"{first} {last}".strip()
        pos_raw = (row.get("Position") or row.get("Roster Position") or "").strip()
        salary_raw = (row.get("Salary") or "0").strip().replace(",", "").replace("$", "")
        team = (row.get("Team") or "").strip()
        opponent = (row.get("Opponent") or "").strip()
        game = (row.get("Game") or "").strip()
        injury = (row.get("Injury") or row.get("Injury Indicator") or "").strip()

        try:
            salary = int(salary_raw)
        except ValueError:
            salary = 0

        pos = DK_POSITION_MAP.get(pos_raw, pos_raw)
        positions_seen.add(pos)

        # Extract team/opponent/start_time from the game field
        # (FD "Game" field is typically "TEAM@OPP MM/DD/YYYY HH:MM PM ET").
        team_abbrev, opp_abbrev, game_start = _parse_game_info(game)
        team = team or team_abbrev
        opponent = opponent or opp_abbrev

        players.append(DFSContestPlayer(
            platform="fanduel",
            slate_id=slate_id,
            slate_name=slate_name,
            sport="",
            start_time=game_start,
            player_id=pid or name,
            player_name=name,
            team=team,
            opponent=opponent,
            position=pos,
            eligible_positions=[pos],
            salary=salary,
            game_info=game,
            data_source="native",
        ))

    if positions_seen & {"SP", "RP", "1B", "2B", "3B", "SS", "OF"}:
        sport = "MLB"
    elif positions_seen & {"QB", "RB", "WR", "TE"}:
        sport = "NFL"
    elif positions_seen & {"PG", "SG", "SF", "PF"}:
        sport = "NBA"

    for p in players:
        p.sport = sport

    # Derive slate start_time from the first player with a parsed game time
    start_time = next((p.start_time for p in players if p.start_time), None)

    return DFSSlate(
        platform="fanduel",
        slate_id=slate_id,
        slate_name=slate_name,
        sport=sport,
        start_time=start_time,
        player_count=len(players),
        salary_cap=35000,
        data_source="native",
    ), players