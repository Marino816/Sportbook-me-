"""MLB pitcher eligibility + canonical projection policy (Repair Batch 2)."""

from projection.native import (
    apply_projection_policy,
    count_projected_players,
    resolve_eligible_pitcher_ids,
    has_bc_pitcher_coverage,
)
from optimizer.mlb_optimizer import MLBOptimizer
from dfs.reconciliation import reconcile_player
from dfs.models import DFSContestPlayer
from dfs.team_normalize import normalize_team_abbr, teams_equivalent


def _p(**kwargs):
    base = {
        "id": "x",
        "name": "X",
        "team": "NYY",
        "salary": 8000,
        "position": "P",
        "roster_position": "P",
        "eligible_positions": ["P"],
        "projected_fp": 0.0,
        "projection_source": "UNAVAILABLE",
        "fppg": None,
    }
    base.update(kwargs)
    return base


class TestBcCoveredSlate:
    def test_bc_starters_kept_relievers_excluded(self):
        pool = [
            _p(id="s1", name="Starter", fppg=18.2, projected_fp=19.0,
               projection_source="SGO_FANTASY_MARKET", roster_position="P"),
            _p(id="r1", name="Reliever", fppg=None, projected_fp=14.0,
               projection_source="SGO_FANTASY_MARKET", roster_position="P",
               eligible_positions=["P", "RP"], salary=4000),
            _p(id="h1", name="Hitter", position="OF", roster_position="OF",
               eligible_positions=["OF"], projected_fp=8.0, fppg=7.0, salary=5000),
        ]
        assert has_bc_pitcher_coverage(pool)
        elig = resolve_eligible_pitcher_ids(pool)
        assert "s1" in elig
        assert "r1" not in elig
        out = apply_projection_policy(pool)
        assert count_projected_players(out) == 2  # starter + hitter, not reliever

    def test_sgo_fantasyscore_alone_does_not_make_reliever_eligible(self):
        pool = [
            _p(id="s1", name="Starter", fppg=20.0, projected_fp=0.0, team="PHI"),
            _p(id="r1", name="Reliever", fppg=None, projected_fp=22.0,
               projection_source="SGO_FANTASY_MARKET", team="PHI", salary=3500),
        ]
        elig = resolve_eligible_pitcher_ids(pool)
        assert elig == {"s1"}


class TestBcUnavailable:
    def test_does_not_wipe_all_pitchers(self):
        pool = [
            _p(id="s1", name="SP Ace", roster_position="SP", eligible_positions=["SP", "P"],
               projected_fp=18.0, projection_source="SGO_FANTASY_MARKET", fppg=None, team="TEX"),
            _p(id="s2", name="SP Two", roster_position="SP", eligible_positions=["SP", "P"],
               projected_fp=15.0, projection_source="SGO_FANTASY_MARKET", fppg=None, team="LAD",
               salary=8500),
            _p(id="r1", name="RP", roster_position="RP", eligible_positions=["RP", "P"],
               projected_fp=12.0, projection_source="SGO_FANTASY_MARKET", fppg=None, team="SF",
               salary=6200),
        ]
        assert not has_bc_pitcher_coverage(pool)
        elig = resolve_eligible_pitcher_ids(pool)
        assert "s1" in elig and "s2" in elig
        assert "r1" not in elig
        out = apply_projection_policy(pool)
        assert count_projected_players(out) == 2
        opt = MLBOptimizer(out, platform="draftkings", strategy="balanced")
        # Not enough hitters to build a lineup; pitcher map must still include SPs.
        assert len(opt.pitchers) == 2


class TestCsvOnlySlate:
    def test_sp_vs_rp_from_csv_tokens(self):
        pool = [
            _p(id="sp", name="Tarik Skubal", roster_position="P", eligible_positions=["SP", "P"],
               projected_fp=22.5, fppg=None, team="DET"),
            _p(id="rp", name="Setup Man", roster_position="P", eligible_positions=["RP", "P"],
               projected_fp=19.8, fppg=None, team="PHI", salary=5000),
        ]
        elig = resolve_eligible_pitcher_ids(pool)
        assert elig == {"sp"}

    def test_highest_salary_per_team_when_all_labeled_p(self):
        pool = [
            _p(id="ace", name="Ace", team="NYY", salary=10000, projected_fp=20.0,
               projection_source="SGO_FANTASY_MARKET", fppg=None),
            _p(id="bullpen", name="Bullpen", team="NYY", salary=4000, projected_fp=16.0,
               projection_source="SGO_FANTASY_MARKET", fppg=None),
            _p(id="ace2", name="Other Ace", team="BOS", salary=9000, projected_fp=18.0,
               projection_source="SGO_FANTASY_MARKET", fppg=None),
        ]
        elig = resolve_eligible_pitcher_ids(pool)
        assert elig == {"ace", "ace2"}
        assert "bullpen" not in elig


class TestRelieverExclusion:
    def test_prop_based_preferred_over_fantasyscore_when_no_bc_no_split(self):
        pool = [
            _p(id="start", name="Starter props", projected_fp=17.0,
               projection_source="PROP_BASED", fppg=None, salary=9000, team="CHC"),
            _p(id="rel", name="Reliever market", projected_fp=21.0,
               projection_source="SGO_FANTASY_MARKET", fppg=None, salary=9500, team="CHC"),
        ]
        elig = resolve_eligible_pitcher_ids(pool)
        assert elig == {"start"}


class TestTeamAliases:
    def test_ath_oak_and_chw_cws(self):
        assert normalize_team_abbr("ATH") == "OAK"
        assert teams_equivalent("ATH", "OAK")
        assert teams_equivalent("CHW", "CWS")
        assert not teams_equivalent("NYY", "BOS")

    def test_reconcile_ath_vs_oak(self):
        dp = DFSContestPlayer(
            platform="draftkings", player_id="1",
            player_name="Brent Rooker", team="ATH",
        )
        sgo = [{"playerID": "sgo-1", "name": "Brent Rooker", "team": "OAK"}]
        assert reconcile_player(dp, sgo) == "sgo-1"

    def test_reconcile_does_not_force_ambiguous(self):
        dp = DFSContestPlayer(
            platform="draftkings", player_id="1",
            player_name="John Smith", team="NYY",
        )
        sgo = [
            {"playerID": "a", "name": "Jon Smith", "team": "NYY"},
            {"playerID": "b", "name": "John Smyth", "team": "NYY"},
        ]
        result = reconcile_player(dp, sgo)
        # Either a high-confidence unique match or None — never a low-confidence force.
        if result:
            assert dp.sbme_confidence >= 0.85
        else:
            assert dp.sbme_confidence == 0.0
