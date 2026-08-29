from optimizer.slot_optimizer import SlotOptimizer
from dfs.roster import UNIQUE_LINEUP_UNAVAILABLE, get_roster


def _nfl_pool():
    """Enough DK NFL players to fill a roster twice with different sets."""
    rows = []
    n = 1
    def add(pos, count, sal, fp):
        nonlocal n
        for i in range(count):
            rows.append({
                "id": f"{pos}-{n}",
                "name": f"{pos} Player {n}",
                "position": pos,
                "roster_position": pos,
                "team": "NE" if n % 2 else "BUF",
                "salary": sal + i * 100,
                "projected_fp": fp - i * 0.4,
            })
            n += 1
    add("QB", 4, 7000, 22)
    add("RB", 8, 5500, 16)
    add("WR", 10, 5000, 15)
    add("TE", 4, 4200, 12)
    add("DST", 4, 3000, 8)
    return rows


class TestSlotOptimizer:
    def test_dk_nfl_roster_size_and_cap(self):
        opt = SlotOptimizer(_nfl_pool(), sport="NFL", platform="draftkings", strategy="cash")
        lus = opt.generate(count=1)
        assert len(lus) == 1
        assert len(lus[0]["players"]) == 9
        assert lus[0]["total_salary"] <= 50000
        slots = [p["roster_slot"] for p in lus[0]["players"]]
        assert slots.count("QB") == 1
        assert slots.count("RB") == 2
        assert slots.count("WR") == 3
        assert slots.count("TE") == 1
        assert "FLEX" in slots
        assert "DST" in slots

    def test_regenerate_rejects_exact_duplicate(self):
        opt = SlotOptimizer(_nfl_pool(), sport="NFL", platform="draftkings", strategy="cash", min_unique_players=1)
        first = opt.generate(count=1)
        assert first
        prior_ids = [[str(p["id"]) for p in first[0]["players"]]]
        second = opt.generate(count=1, regenerate_from_ids=prior_ids)
        if second:
            a = {p["id"] for p in first[0]["players"]}
            b = {p["id"] for p in second[0]["players"]}
            assert a != b
        else:
            assert UNIQUE_LINEUP_UNAVAILABLE

    def test_fd_nfl_uses_60k_and_nine_slots(self):
        r = get_roster("NFL", "fanduel")
        assert r.salary_cap == 60000
        opt = SlotOptimizer(_nfl_pool(), sport="NFL", platform="fanduel", strategy="cash")
        lus = opt.generate(count=1)
        assert len(lus) == 1
        assert len(lus[0]["players"]) == 9
        assert lus[0]["total_salary"] <= 60000
        slots = [p["roster_slot"] for p in lus[0]["players"]]
        assert slots.count("QB") == 1
        assert slots.count("RB") == 2
        assert slots.count("WR") == 3
        assert slots.count("TE") == 1
        assert "FLEX" in slots
        assert "DEF" in slots

    def test_fd_ncaaf_uses_60k_and_seven_slots(self):
        r = get_roster("NCAAF", "fanduel")
        assert r.salary_cap == 60000
        opt = SlotOptimizer(_nfl_pool(), sport="NCAAF", platform="fanduel", strategy="cash")
        lus = opt.generate(count=1)
        assert len(lus) == 1
        assert len(lus[0]["players"]) == 7
        assert lus[0]["total_salary"] <= 60000
        slots = [p["roster_slot"] for p in lus[0]["players"]]
        assert slots.count("QB") == 1
        assert slots.count("RB") == 2
        assert slots.count("WR") == 3
        assert "SFLX" in slots or "SUPER FLEX" in slots
