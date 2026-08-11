"""Native DFS contest data layer tests."""

import pytest
from dfs.models import DFSContestPlayer, DFSSlate
from dfs.parsers import parse_draftkings_csv, parse_fanduel_csv
from dfs.reconciliation import reconcile_player

DK_SAMPLE = """Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame
P,Tarik Skubal (12345),Tarik Skubal,12345,SP,10500,DET@CLE 08/11/2026 07:10PM ET,DET,22.5
P,Zack Wheeler (67890),Zack Wheeler,67890,RP,9800,PHI@ATL 08/11/2026 07:20PM ET,PHI,19.8
C,J.T. Realmuto (11111),J.T. Realmuto,11111,C,4500,PHI@ATL 08/11/2026 07:20PM ET,PHI,8.2
1B,Pete Alonso (22222),Pete Alonso,22222,1B,5200,NYM@MIA 08/11/2026 06:40PM ET,NYM,9.1
2B,Ozzie Albies (33333),Ozzie Albies,33333,2B,5100,ATL@PHI 08/11/2026 07:20PM ET,ATL,8.5
3B,Austin Riley (44444),Austin Riley,44444,3B,5400,ATL@PHI 08/11/2026 07:20PM ET,ATL,9.2
SS,Francisco Lindor (55555),Francisco Lindor,55555,SS,5600,NYM@MIA 08/11/2026 06:40PM ET,NYM,9.8
OF,Ronald Acuna (66666),Ronald Acuna,66666,OF,6200,ATL@PHI 08/11/2026 07:20PM ET,ATL,10.5
OF,Mookie Betts (77777),Mookie Betts,77777,OF,6000,LAD@SD 08/11/2026 09:40PM ET,LAD,10.0
OF,Fernando Tatis (88888),Fernando Tatis,88888,OF,5500,SD@LAD 08/11/2026 09:40PM ET,SD,9.0
P,Corbin Burnes (99999),Corbin Burnes,99999,SP,9700,MIL@CHC 08/11/2026 08:05PM ET,MIL,18.5
"""

FD_SAMPLE = """Id,First Name,Last Name,Position,FPPG,Played,Salary,Game,Team,Opponent,Injury
12345,Tarik,Skubal,SP,22.5,1,10500,DET@CLE,DET,CLE,
67890,Zack,Wheeler,SP,19.8,1,9800,PHI@ATL,PHI,ATL,
11111,JT,Realmuto,C,8.2,1,4500,PHI@ATL,PHI,ATL,
"""

SGO_PLAYERS = [
    {"playerID": "12345", "name": "Tarik Skubal", "team": "DET", "position": "SP"},
    {"playerID": "67890", "name": "Zack Wheeler", "team": "PHI", "position": "SP"},
    {"playerID": "11111", "name": "J.T. Realmuto", "team": "PHI", "position": "C"},
    {"playerID": "22222", "name": "Pete Alonso", "team": "NYM", "position": "1B"},
    {"playerID": "55555", "name": "Francisco Lindor", "team": "NYM", "position": "SS"},
]


class TestDKParser:
    def test_parse_count(self):
        slate, players = parse_draftkings_csv(DK_SAMPLE)
        assert len(players) == 11
        assert slate.player_count == 11

    def test_parse_sport_detection(self):
        slate, _ = parse_draftkings_csv(DK_SAMPLE)
        assert slate.sport == "MLB"

    def test_parse_player_fields(self):
        _, players = parse_draftkings_csv(DK_SAMPLE)
        p = players[0]
        assert p.player_name == "Tarik Skubal"
        assert p.player_id == "12345"
        assert p.salary == 10500
        assert p.position == "P"  # SP → P normalization
        assert p.team == "DET"
        assert p.opponent == "CLE"

    def test_to_optimizer_pool(self):
        _, players = parse_draftkings_csv(DK_SAMPLE)
        pool = DFSContestPlayer.list_to_pool(players)
        assert len(pool) == 11
        assert pool[0]["name"] == "Tarik Skubal"
        assert pool[0]["salary"] == 10500
        assert "projected_fp" in pool[0]


class TestFDParser:
    def test_parse_fd_csv(self):
        slate, players = parse_fanduel_csv(FD_SAMPLE)
        assert len(players) == 3
        assert slate.platform == "fanduel"
        assert slate.salary_cap == 35000

    def test_fd_player_name(self):
        _, players = parse_fanduel_csv(FD_SAMPLE)
        assert players[0].player_name == "Tarik Skubal"


class TestReconciliation:
    def test_exact_match(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="12345", player_name="Tarik Skubal", team="DET")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result == "12345"
        assert dp.sbme_confidence == 1.0

    def test_punctuation_variant(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="11111", player_name="JT Realmuto", team="PHI")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result is not None
        assert dp.sbme_confidence >= 0.85

    def test_no_match(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="99999", player_name="Nobody Jones", team="XXX")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result is None
        assert dp.sbme_confidence == 0.0