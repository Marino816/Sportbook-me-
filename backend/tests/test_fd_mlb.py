"""Tests for FanDuel MLB roster — separate from DK."""
import pytest

FD_TEST_POOL = [
    {"id":1,"name":"SP Ace","team":"TEX","salary":9500,"roster_position":"SP","projected_fp":22.0},
    {"id":2,"name":"SP Mid","team":"LAD","salary":7800,"roster_position":"SP","projected_fp":18.0},
    {"id":3,"name":"C1B Top","team":"NYY","salary":4500,"roster_position":"C","projected_fp":8.0},
    {"id":4,"name":"1B Top","team":"LAD","salary":5000,"roster_position":"1B","projected_fp":10.0},
    {"id":5,"name":"2B Top","team":"HOU","salary":4200,"roster_position":"2B","projected_fp":9.0},
    {"id":6,"name":"3B Top","team":"ATL","salary":4000,"roster_position":"3B","projected_fp":9.5},
    {"id":7,"name":"SS Top","team":"SD","salary":4300,"roster_position":"SS","projected_fp":10.0},
    {"id":8,"name":"OF A","team":"LAA","salary":5000,"roster_position":"OF","projected_fp":11.0},
    {"id":9,"name":"OF B","team":"CHC","salary":3800,"roster_position":"OF","projected_fp":8.5},
    {"id":10,"name":"OF C","team":"BOS","salary":3400,"roster_position":"RF","projected_fp":8.0},
    {"id":11,"name":"OF D","team":"DET","salary":3000,"roster_position":"CF","projected_fp":6.0},
    {"id":12,"name":"UTIL OF","team":"MIA","salary":2800,"roster_position":"OF","projected_fp":5.0},
    {"id":13,"name":"UTIL C","team":"SEA","salary":2500,"roster_position":"C","projected_fp":4.0},
    {"id":14,"name":"UTIL 1B","team":"ARI","salary":2700,"roster_position":"1B","projected_fp":4.5},
    {"id":15,"name":"UTIL SS","team":"MIN","salary":2900,"roster_position":"SS","projected_fp":5.5},
]


class TestFanDuelMLB:
    def test_fd_roster_size_9(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        assert len(lu) == 1
        assert len(lu[0]["players"]) == 9

    def test_fd_exactly_one_pitcher(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("P") == 1

    def test_fd_c1b_slot(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("C1B") == 1

    def test_fd_three_of(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("OF") == 3

    def test_fd_slot_distribution(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        slots = sorted([p["roster_slot"] for p in lu[0]["players"]])
        expected = sorted(["P", "C1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL"])
        assert slots == expected

    def test_fd_salary_under_cap(self):
        from api.builder_routes import _gen_unique_lineups, FD_MLB_CAP
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        assert lu[0]["total_salary"] <= FD_MLB_CAP

    def test_dk_still_10_players(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="draftkings")
        assert len(lu[0]["players"]) == 10

    def test_dk_still_2p(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="draftkings")
        assert sum(1 for p in lu[0]["players"] if p["roster_slot"] == "P") == 2

    def test_no_dk_cap_in_fd(self):
        from api.builder_routes import _gen_unique_lineups, FD_MLB_CAP, MLB_CAP
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        assert lu[0]["total_salary"] <= FD_MLB_CAP
        assert FD_MLB_CAP < MLB_CAP

    def test_fd_util_not_pitcher(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(FD_TEST_POOL, "balanced", 1, [], [], platform="fanduel")
        util = [p for p in lu[0]["players"] if p["roster_slot"] == "UTIL"]
        assert len(util) == 1
        assert util[0]["roster_slot"] != "P"