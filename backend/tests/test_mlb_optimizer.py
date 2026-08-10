"""Tests for MLB DraftKings optimizer — roster, validation, uniqueness, exposure."""

import pytest

# Use the fresh test fixtures/helper data — small pool so logic is testable
TEST_POOL = [
    # 3 pitchers
    {"id":1,"name":"SP Ace","team":"TEX","salary":10200,"roster_position":"SP","projected_fp":22.0,"ceiling":28.0,"floor":15.0,"ownership":None,"value":2.15},
    {"id":2,"name":"SP Mid","team":"LAD","salary":8500,"roster_position":"SP","projected_fp":18.0,"ceiling":22.0,"floor":12.0,"ownership":None,"value":2.11},
    {"id":3,"name":"SP Value","team":"SF","salary":6200,"roster_position":"RP","projected_fp":12.0,"ceiling":16.0,"floor":7.0,"ownership":None,"value":1.93},
    # 2 catchers
    {"id":4,"name":"C Top","team":"NYY","salary":5200,"roster_position":"C","projected_fp":8.0,"ceiling":10.0,"floor":4.0,"ownership":None,"value":1.53},
    {"id":5,"name":"C Budget","team":"MIA","salary":3500,"roster_position":"C","projected_fp":5.0,"ceiling":7.0,"floor":2.0,"ownership":None,"value":1.42},
    # 2 each infield
    {"id":6,"name":"1B Top","team":"LAD","salary":5800,"roster_position":"1B","projected_fp":10.0,"ceiling":13.0,"floor":6.0,"ownership":None,"value":1.72},
    {"id":7,"name":"1B Val","team":"CIN","salary":4100,"roster_position":"1B","projected_fp":7.0,"ceiling":9.0,"floor":4.0,"ownership":None,"value":1.70},
    {"id":8,"name":"2B Top","team":"HOU","salary":5500,"roster_position":"2B","projected_fp":9.0,"ceiling":12.0,"floor":5.0,"ownership":None,"value":1.63},
    {"id":9,"name":"2B Val","team":"CLE","salary":4000,"roster_position":"2B","projected_fp":6.0,"ceiling":8.0,"floor":3.0,"ownership":None,"value":1.50},
    {"id":10,"name":"3B Top","team":"ATL","salary":5600,"roster_position":"3B","projected_fp":9.5,"ceiling":12.5,"floor":5.5,"ownership":None,"value":1.69},
    {"id":11,"name":"3B Val","team":"PIT","salary":3900,"roster_position":"3B","projected_fp":6.0,"ceiling":8.0,"floor":3.0,"ownership":None,"value":1.53},
    {"id":12,"name":"SS Top","team":"SD","salary":5700,"roster_position":"SS","projected_fp":10.0,"ceiling":13.0,"floor":6.0,"ownership":None,"value":1.75},
    {"id":13,"name":"SS Val","team":"MIL","salary":4200,"roster_position":"SS","projected_fp":6.5,"ceiling":8.5,"floor":3.5,"ownership":None,"value":1.54},
    # 4 outfielders
    {"id":14,"name":"OF Top","team":"LAA","salary":6200,"roster_position":"OF","projected_fp":11.0,"ceiling":14.0,"floor":7.0,"ownership":None,"value":1.77},
    {"id":15,"name":"OF Mid","team":"CHC","salary":4800,"roster_position":"OF","projected_fp":8.5,"ceiling":11.0,"floor":5.0,"ownership":None,"value":1.77},
    {"id":16,"name":"OF Mid2","team":"BOS","salary":4600,"roster_position":"RF","projected_fp":8.0,"ceiling":10.0,"floor":5.0,"ownership":None,"value":1.73},
    {"id":17,"name":"OF Val","team":"DET","salary":3800,"roster_position":"CF","projected_fp":6.0,"ceiling":8.0,"floor":3.0,"ownership":None,"value":1.57},
]


class TestMLBOptimizer:

    def test_roster_size(self):
        """A: roster contains exactly 10 players."""
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        assert len(lu) == 1
        assert len(lu[0]["players"]) == 10

    def test_exactly_two_pitchers(self):
        """B: exactly 2 P."""
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("P") == 2

    def test_exactly_one_catcher(self):
        """C: exactly 1 C."""
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("C") == 1

    def test_exactly_one_1b(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("1B") == 1

    def test_exactly_one_2b(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("2B") == 1

    def test_exactly_one_3b(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("3B") == 1

    def test_exactly_one_ss(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("SS") == 1

    def test_exactly_three_of(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        slots = [p["roster_slot"] for p in lu[0]["players"]]
        assert slots.count("OF") == 3

    def test_salary_under_cap(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        assert lu[0]["total_salary"] <= 50000

    def test_no_duplicate_players(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 3, [], [], 50000)
        for lineup in lu:
            ids = [p["id"] for p in lineup["players"]]
            assert len(ids) == len(set(ids))

    def test_lineups_not_identical(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 3, [], [], 50000)
        assert len(lu) >= 2  # test pool limited, but at least 2 unique
        ids_sets = [frozenset(p["id"] for p in l["players"]) for l in lu]
        assert len(set(ids_sets)) == len(lu)  # all unique sets

    def test_min_uniqueness(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 2, [], [], 50000)
        ids1 = {p["id"] for p in lu[0]["players"]}
        ids2 = {p["id"] for p in lu[1]["players"]}
        overlap = len(ids1 & ids2)
        assert (10 - overlap) >= 2  # at least 2 different players

    def test_players_across_lineups(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 3, [], [], 50000)
        # SP Ace (id=1) can appear in multiple lineups
        appear = sum(1 for l in lu if 1 in {p["id"] for p in l["players"]})
        assert appear >= 1  # should appear in at least one, possibly more

    def test_ownership_null(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        for p in lu[0]["players"]:
            assert p["ownership"] is None

    def test_trial_label(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        assert lu[0]["data_mode"] == "TRIAL_SCRAMBLED"
        assert lu[0]["data_source"] == "sportsdataio"

    def test_projection_equals_sum(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        player_sum = sum(p["projected_fp"] for p in lu[0]["players"])
        assert round(player_sum, 1) == lu[0]["projected_score"]

    def test_salary_equals_sum(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "balanced", 1, [], [], 50000)
        player_sum = sum(p["salary"] for p in lu[0]["players"])
        assert player_sum == lu[0]["total_salary"]

    def test_strategy_cash_exposure(self):
        from api.builder_routes import _gen_unique_lineups
        lu = _gen_unique_lineups(TEST_POOL, "cash", 2, [], [], 50000)
        # Cash relaxes min_unique to 1 — players CAN appear in both
        appear = sum(1 for l in lu if 1 in {p["id"] for p in l["players"]})
        # SP Ace should be in at least 1 lineup
        assert appear >= 1

    def test_all_strategies_work(self):
        from api.builder_routes import _gen_unique_lineups
        for strat in ["balanced", "cash", "gpp", "aggressive", "nuclear"]:
            lu = _gen_unique_lineups(TEST_POOL, strat, 1, [], [], 50000)
            assert len(lu) == 1, f"'{strat}' failed to generate"
            assert len(lu[0]["players"]) == 10