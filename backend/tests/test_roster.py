from dfs.roster import (
    average_remaining_per_player,
    eligible_for_slot,
    get_roster,
    uses_slot_optimizer,
)


class TestRosterTemplates:
    def test_mlb_dk_unchanged(self):
        r = get_roster("MLB", "draftkings")
        assert r is not None
        assert r.slots == ("P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF")
        assert r.salary_cap == 50000
        assert r.player_count == 10

    def test_mlb_fd_unchanged(self):
        r = get_roster("MLB", "fanduel")
        assert r is not None
        assert r.slots[0] == "P"
        assert "C1B" in r.slots
        assert r.salary_cap == 35000

    def test_dk_ncaaf_slots(self):
        r = get_roster("NCAAF", "draftkings")
        assert r is not None
        assert r.slots == ("QB", "RB", "RB", "WR", "WR", "WR", "FLEX", "SFLX")
        assert r.salary_cap == 50000
        assert r.slots != get_roster("MLB", "draftkings").slots

    def test_dk_nfl_slots(self):
        r = get_roster("NFL", "draftkings")
        assert r is not None
        assert r.slots == ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
        assert r.salary_cap == 50000

    def test_fd_ncaaf_slots_and_cap(self):
        r = get_roster("NCAAF", "fanduel")
        assert r is not None
        assert r.slots == ("QB", "RB", "RB", "WR", "WR", "WR", "SFLX")
        assert r.salary_cap == 60000
        assert r.player_count == 7
        assert average_remaining_per_player(60000, 7) == 8571

    def test_fd_nfl_slots_and_cap(self):
        r = get_roster("NFL", "fanduel")
        assert r is not None
        assert r.slots == ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF")
        assert r.salary_cap == 60000
        assert r.player_count == 9
        assert average_remaining_per_player(60000, 9) == 6667

    def test_keyed_by_sport_and_platform(self):
        assert get_roster("NFL", "draftkings").slots != get_roster("NFL", "fanduel").slots
        assert get_roster("NFL", "draftkings").slots != get_roster("NCAAF", "draftkings").slots

    def test_flex_eligibility(self):
        r = get_roster("NFL", "draftkings")
        assert eligible_for_slot("RB", "FLEX", r)
        assert eligible_for_slot("WR", "FLEX", r)
        assert eligible_for_slot("TE", "FLEX", r)
        assert not eligible_for_slot("QB", "FLEX", r)
        assert eligible_for_slot("DST", "DST", r)
        assert eligible_for_slot("DEF", "DST", r)

    def test_slot_optimizer_sports(self):
        assert uses_slot_optimizer("NFL") is True
        assert uses_slot_optimizer("NCAAF") is True
        assert uses_slot_optimizer("MLB") is False
        assert uses_slot_optimizer("NBA") is False
