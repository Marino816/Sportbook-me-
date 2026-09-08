"""Canonical unordered DFS game counts."""

from dfs.games import canonical_matchup_key, count_canonical_games


def test_reversed_matchups_count_as_one_game():
    players = [
        {"game_info": "LAD@SD 09/08/2026 09:40PM ET", "team": "LAD", "opponent": "SD"},
        {"game_info": "SD@LAD 09/08/2026 09:40PM ET", "team": "SD", "opponent": "LAD"},
        {"game_info": "NYY@BOS 09/08/2026 07:10PM ET", "team": "NYY", "opponent": "BOS"},
        {"game_info": "BOS@NYY 09/08/2026 07:10PM ET", "team": "BOS", "opponent": "NYY"},
        {"game_info": "CLE@DET 09/08/2026 06:40PM ET", "team": "CLE", "opponent": "DET"},
        {"game_info": "DET@CLE 09/08/2026 06:40PM ET", "team": "DET", "opponent": "CLE"},
        {"game_info": "CHC@MIL 09/08/2026 08:10PM ET", "team": "CHC", "opponent": "MIL"},
        {"game_info": "MIL@CHC 09/08/2026 08:10PM ET", "team": "MIL", "opponent": "CHC"},
        {"game_info": "PHI@ATL 09/08/2026 07:20PM ET", "team": "PHI", "opponent": "ATL"},
        {"game_info": "ATL@PHI 09/08/2026 07:20PM ET", "team": "ATL", "opponent": "PHI"},
    ]
    assert count_canonical_games(players) == 5
    assert canonical_matchup_key("LAD@SD 09/08/2026 09:40PM ET") == canonical_matchup_key(
        "SD@LAD 09/08/2026 09:40PM ET"
    )


def test_identical_csv_game_info_counts_once():
    shared = "DET@CLE 08/11/2026 07:10PM ET"
    players = [
        {"game_info": shared, "team": "DET", "opponent": "CLE"},
        {"game_info": shared, "team": "CLE", "opponent": "DET"},
        {"game_info": shared, "team": "DET", "opponent": "CLE"},
    ]
    assert count_canonical_games(players) == 1


def test_dk_csv_reversed_matchups_count_as_one():
    from dfs.parsers import parse_draftkings_csv

    sample = """Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame
P,A (1),A,1,SP,10000,LAD@SD 08/11/2026 09:40PM ET,LAD,20
OF,B (2),B,2,OF,5000,SD@LAD 08/11/2026 09:40PM ET,SD,9
C,C (3),C,3,C,4000,DET@CLE 08/11/2026 07:10PM ET,DET,8
1B,D (4),D,4,1B,4200,DET@CLE 08/11/2026 07:10PM ET,CLE,8
"""
    _, players = parse_draftkings_csv(sample)
    rows = [{"game_info": p.game_info, "team": p.team, "opponent": p.opponent} for p in players]
    assert count_canonical_games(rows) == 2


def test_two_csv_games_stay_two():
    players = [
        {"game_info": "DET@CLE 08/11/2026 07:10PM ET", "team": "DET", "opponent": "CLE"},
        {"game_info": "PHI@ATL 08/11/2026 07:20PM ET", "team": "PHI", "opponent": "ATL"},
        {"game_info": "PHI@ATL 08/11/2026 07:20PM ET", "team": "ATL", "opponent": "PHI"},
    ]
    assert count_canonical_games(players) == 2
