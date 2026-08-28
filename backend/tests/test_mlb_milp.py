"""Tests for MLB MILP optimizer — DraftKings + FanDuel using MLBOptimizer."""

import pytest
from optimizer.mlb_optimizer import MLBOptimizer

TEST_POOL = [
    # Pitchers
    {"id":1,"name":"P1","team":"TEX","salary":10200,"roster_position":"SP","projected_fp":22.0},
    {"id":2,"name":"P2","team":"LAD","salary":8500,"roster_position":"SP","projected_fp":18.0},
    {"id":3,"name":"P3","team":"SF","salary":6200,"roster_position":"RP","projected_fp":12.0},
    {"id":4,"name":"P4","team":"NYY","salary":5500,"roster_position":"SP","projected_fp":10.0},
    # Catchers
    {"id":5,"name":"C1","team":"NYY","salary":5200,"roster_position":"C","projected_fp":8.0},
    {"id":6,"name":"C2","team":"MIA","salary":3500,"roster_position":"C","projected_fp":5.0},
    {"id":7,"name":"C3","team":"CHC","salary":3200,"roster_position":"C","projected_fp":4.0},
    # 1B
    {"id":8,"name":"1B1","team":"LAD","salary":5800,"roster_position":"1B","projected_fp":10.0},
    {"id":9,"name":"1B2","team":"CIN","salary":4100,"roster_position":"1B","projected_fp":7.0},
    {"id":10,"name":"1B3","team":"PIT","salary":3600,"roster_position":"1B","projected_fp":5.0},
    # 2B
    {"id":11,"name":"2B1","team":"HOU","salary":5500,"roster_position":"2B","projected_fp":9.0},
    {"id":12,"name":"2B2","team":"CLE","salary":4000,"roster_position":"2B","projected_fp":6.0},
    {"id":13,"name":"2B3","team":"DET","salary":3500,"roster_position":"2B","projected_fp":4.5},
    # 3B
    {"id":14,"name":"3B1","team":"ATL","salary":5600,"roster_position":"3B","projected_fp":9.5},
    {"id":15,"name":"3B2","team":"PIT","salary":3900,"roster_position":"3B","projected_fp":6.0},
    {"id":16,"name":"3B3","team":"MIN","salary":3400,"roster_position":"3B","projected_fp":4.0},
    # SS
    {"id":17,"name":"SS1","team":"SD","salary":5700,"roster_position":"SS","projected_fp":10.0},
    {"id":18,"name":"SS2","team":"MIL","salary":4200,"roster_position":"SS","projected_fp":6.5},
    {"id":19,"name":"SS3","team":"SEA","salary":3300,"roster_position":"SS","projected_fp":4.0},
    # OF
    {"id":20,"name":"OF1","team":"LAA","salary":6200,"roster_position":"OF","projected_fp":11.0},
    {"id":21,"name":"OF2","team":"CHC","salary":4800,"roster_position":"OF","projected_fp":8.5},
    {"id":22,"name":"OF3","team":"BOS","salary":4600,"roster_position":"RF","projected_fp":8.0},
    {"id":23,"name":"OF4","team":"DET","salary":3800,"roster_position":"CF","projected_fp":6.0},
    {"id":24,"name":"OF5","team":"COL","salary":3500,"roster_position":"OF","projected_fp":5.5},
    {"id":25,"name":"OF6","team":"KC","salary":3000,"roster_position":"OF","projected_fp":4.5},
    {"id":26,"name":"OF7","team":"OAK","salary":2800,"roster_position":"OF","projected_fp":3.5},
    # Extra hitters for UTIL
    {"id":27,"name":"UTIL1","team":"ARI","salary":3100,"roster_position":"1B","projected_fp":4.0},
    {"id":28,"name":"UTIL2","team":"WSH","salary":2900,"roster_position":"2B","projected_fp":3.5},
]


class TestMLBOptimizer:
    def test_dk_roster_10_players(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        assert len(lu) == 1
        assert lu[0]["player_count"] == 10

    def test_dk_2_pitchers(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("P") == 2

    def test_dk_roster_slots(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        slots = sorted([p["roster_slot"] for p in lu[0]["players"]])
        assert slots == sorted(["P","P","C","1B","2B","3B","SS","OF","OF","OF"])

    def test_dk_salary_under_50k(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        assert lu[0]["total_salary"] <= 50000

    def test_fd_9_players(self):
        opt = MLBOptimizer(TEST_POOL, platform="fanduel", strategy="balanced")
        lu = opt.generate(1)
        assert len(lu) == 1
        assert lu[0]["player_count"] == 9

    def test_fd_1_pitcher(self):
        opt = MLBOptimizer(TEST_POOL, platform="fanduel", strategy="balanced")
        lu = opt.generate(1)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("P") == 1

    def test_fd_slots(self):
        opt = MLBOptimizer(TEST_POOL, platform="fanduel", strategy="balanced")
        lu = opt.generate(1)
        slots = sorted([p["roster_slot"] for p in lu[0]["players"]])
        assert slots == sorted(["P","C1B","2B","3B","SS","OF","OF","OF","UTIL"])

    def test_fd_salary_under_35k(self):
        opt = MLBOptimizer(TEST_POOL, platform="fanduel", strategy="balanced")
        lu = opt.generate(1)
        assert lu[0]["total_salary"] <= 35000

    def test_dk_multi_lineup_unique(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(3)
        assert len(lu) >= 2
        ids_sets = [frozenset(p["id"] for p in l["players"]) for l in lu]
        assert len(set(ids_sets)) == len(lu)

    def test_gpp_stacking(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="gpp")
        lu = opt.generate(1)
        assert len(lu) == 1
        # GPP should have stack_summary
        assert "stack" in lu[0] or "stack_summary" in lu[0]

    def test_no_zero_proj(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        for p in lu[0]["players"]:
            assert (p.get("projected_fp", 0) or 0) > 0

    def test_no_fake_ownership(self):
        opt = MLBOptimizer(TEST_POOL, platform="draftkings", strategy="balanced")
        lu = opt.generate(1)
        for p in lu[0]["players"]:
            assert p.get("ownership") is None or p.get("ownership", 0) > 0

    def test_lock_and_exclude_by_player_name(self):
        """Frontend/Data Hub send player names; solver must honor them."""
        pool = [{**p, "fppg": float(p.get("projected_fp") or 1)} for p in TEST_POOL]
        opt = MLBOptimizer(
            pool,
            platform="draftkings",
            strategy="balanced",
            locks=["P1"],
            excludes=["OF7"],
        )
        lu = opt.generate(1)
        assert lu
        names = [p["name"] for p in lu[0]["players"]]
        assert "P1" in names
        assert "OF7" not in names