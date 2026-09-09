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


def _production_shaped_nfl_pool():
    """Slate-105 shape: 817 players, 13 native projections, DST all 0.0."""
    rows = []
    rows.append({
        "id": "JOSH_ALLEN_1_NFL", "name": "Josh Allen", "position": "QB",
        "roster_position": "QB", "team": "BUF", "salary": 7000, "projected_fp": 0.0,
    })
    rows.append({
        "id": "DEVON_ACHANE_1_NFL", "name": "De'Von Achane", "position": "RB",
        "roster_position": "RB", "team": "MIA", "salary": 7000, "projected_fp": 0.0,
    })
    rows.append({
        "id": "KYREN_WILLIAMS_1_NFL", "name": "Kyren Williams", "position": "RB",
        "roster_position": "RB", "team": "LAR", "salary": 6200, "projected_fp": 0.0,
    })
    n = 1
    for pos, count, sal, fp in (
        ("QB", 4, 5500, 18.0),
        ("RB", 4, 4800, 14.0),
        ("WR", 4, 4500, 13.0),
        ("TE", 1, 4000, 11.0),
    ):
        for i in range(count):
            rows.append({
                "id": f"PROJ-{pos}-{n}",
                "name": f"Projected {pos} {n}",
                "position": pos,
                "roster_position": pos,
                "team": "NE" if n % 2 else "SEA",
                "salary": sal + i * 100,
                "projected_fp": fp,
            })
            n += 1
    # Production mix on slate 105: WR/TE/RB/QB heavy, 32 DST, all unprojected.
    remaining = 817 - len(rows)
    dst_count = 32
    skill_zero = remaining - dst_count
    pos_cycle = [("QB", 5200), ("RB", 4200), ("WR", 3800), ("TE", 3200)]
    for i in range(skill_zero):
        pos, sal = pos_cycle[i % 4]
        rows.append({
            "id": f"ZERO-{pos}-{n}",
            "name": f"Zero {pos} {n}",
            "position": pos,
            "roster_position": pos,
            "team": "KC" if n % 2 else "NYJ",
            "salary": sal + (i % 20) * 50,
            "projected_fp": 0.0,
        })
        n += 1
    for i in range(dst_count):
        rows.append({
            "id": f"ZERO-DST-{n}",
            "name": f"Zero DST {n}",
            "position": "DST",
            "roster_position": "DST",
            "team": "KC" if n % 2 else "NYJ",
            "salary": 2400 + (i % 10) * 100,
            "projected_fp": 0.0,
        })
        n += 1
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

    def test_missing_projections_still_fill_empty_nfl_roster(self):
        pool = []
        n = 1
        for pos, count, sal in (("QB", 3, 6000), ("RB", 6, 5000), ("WR", 8, 4500), ("TE", 3, 3500), ("DST", 3, 2500)):
            for i in range(count):
                pool.append({
                    "id": f"{pos}-{n}",
                    "name": f"{pos} Zero {n}",
                    "position": pos,
                    "roster_position": pos,
                    "team": "BUF" if n % 2 else "MIA",
                    "salary": sal + i * 50,
                    "projected_fp": 0.0,
                })
                n += 1
        opt = SlotOptimizer(pool, sport="NFL", platform="draftkings", strategy="balanced")
        lus = opt.generate(count=1)
        assert len(lus) == 1
        assert len(lus[0]["players"]) == 9
        assert lus[0]["total_salary"] <= 50000
        assert {p["roster_slot"] for p in lus[0]["players"]} >= {"QB", "RB", "WR", "TE", "FLEX", "DST"}

    def test_partial_locks_with_zero_projections_fill_remaining_slots(self):
        pool = _nfl_pool()
        for p in pool:
            if p["id"] in ("QB-1", "RB-5", "RB-6"):
                p["projected_fp"] = 0.0
                p["name"] = {"QB-1": "Josh Allen", "RB-5": "De'Von Achane", "RB-6": "Kyren Williams"}[p["id"]]
        opt = SlotOptimizer(
            pool,
            sport="NFL",
            platform="draftkings",
            strategy="balanced",
            locks=["QB-1", "RB-5", "RB-6"],
        )
        lus = opt.generate(count=1)
        assert len(lus) == 1
        ids = {p["id"] for p in lus[0]["players"]}
        assert {"QB-1", "RB-5", "RB-6"} <= ids
        assert len(lus[0]["players"]) == 9
        assert lus[0]["total_salary"] <= 50000

    def test_zero_fp_filter_would_drop_every_dst(self):
        """Slate 105 shape: 817 players, 13 projected, DST all 0.0, three locks."""
        pool = _production_shaped_nfl_pool()
        assert len(pool) == 817
        kept = [p for p in pool if (p.get("projected_fp") or 0) > 0]
        assert len(kept) == 13
        assert not any((p.get("position") or "") == "DST" for p in kept)
        opt = SlotOptimizer(
            pool,
            sport="NFL",
            platform="draftkings",
            strategy="balanced",
            locks=["JOSH_ALLEN_1_NFL", "DEVON_ACHANE_1_NFL", "KYREN_WILLIAMS_1_NFL"],
        )
        lus = opt.generate(count=1)
        assert len(lus) >= 1
        lu = lus[0]
        assert len(lu["players"]) == 9
        names = {p["name"] for p in lu["players"]}
        ids = [p["id"] for p in lu["players"]]
        assert {"Josh Allen", "De'Von Achane", "Kyren Williams"} <= names
        assert any(p["roster_slot"] == "DST" for p in lu["players"])
        assert lu["total_salary"] <= 50000
        assert len(ids) == len(set(ids))

    def test_two_locked_qbs_are_infeasible_with_actionable_reason(self):
        opt = SlotOptimizer(
            _nfl_pool(),
            sport="NFL",
            platform="draftkings",
            strategy="cash",
            locks=["QB-1", "QB-2"],
        )
        lus = opt.generate(count=1)
        assert lus == []
        assert opt.last_infeasible_reason
        assert "locked" in opt.last_infeasible_reason.lower()

    def test_lock_missing_from_slate_is_actionable(self):
        opt = SlotOptimizer(
            _nfl_pool(),
            sport="NFL",
            platform="draftkings",
            locks=["NOT-ON-SLATE"],
        )
        lus = opt.generate(count=1)
        assert lus == []
        assert "not in this slate pool" in opt.last_infeasible_reason
