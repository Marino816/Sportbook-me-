"""
Historical fantasy-scoring tests — MLB DraftKings only.

Verifies the official DK scoring formula, partial/exact labelling,
missing-field handling, and complete separation from the projection
approximation.
"""

import pytest
from datetime import datetime, timedelta, timezone

from scoring import MLBScorekeeper, build_game_log
from scoring.models import (
    ScoringPlatform, ScoringMode, Sport, PlayerRole, ScoringResult,
)


# ── Helpers ───────────────────────────────────────────────────

def _sgo_hitter(**overrides):
    """Build a realistic SGO hitter stat dict with all fields present.

    Accepts both short names (singles, runsScored) and SGO field names
    (batting_singles, batting_runsScored).  Short names are mapped to
    their SGO equivalents automatically.
    """
    _SHORT_TO_SGO = {
        "singles": "batting_singles",
        "doubles": "batting_doubles",
        "triples": "batting_triples",
        "homeRuns": "batting_homeRuns",
        "hits": "batting_hits",
        "totalBases": "batting_totalBases",
        "RBI": "batting_RBI",
        "runsScored": "batting_runsScored",
        "basesOnBalls": "batting_basesOnBalls",
        "stolenBases": "batting_stolenBases",
        "hitByPitch": "batting_hitByPitch",
        "strikeouts": "batting_strikeouts",
        "atBats": "batting_atBats",
    }
    base = {
        "batting_singles": 1,
        "batting_doubles": 0,
        "batting_triples": 0,
        "batting_homeRuns": 0,
        "batting_RBI": 0,
        "batting_runsScored": 1,
        "batting_basesOnBalls": 0,
        "batting_stolenBases": 0,
        "batting_hitByPitch": 0,
        "batting_strikeouts": 1,
        "batting_atBats": 4,
        "batting_hits": 1,
        "batting_totalBases": 1,
    }
    for k, v in overrides.items():
        target = _SHORT_TO_SGO.get(k, k)
        base[target] = v
    return base


def _sgo_pitcher(**overrides):
    """Build a realistic SGO pitcher stat dict with all fields present."""
    _SHORT_TO_SGO = {
        "outs": "pitching_outs",
        "strikeouts": "pitching_strikeouts",
        "win": "pitching_win",
        "earnedRuns": "pitching_earnedRuns",
        "hits": "pitching_hits",
        "basesOnBalls": "pitching_basesOnBalls",
        "hitBatters": "pitching_hitBatters",
    }
    base = {
        "pitching_outs": 18,
        "pitching_strikeouts": 6,
        "pitching_win": 1,
        "pitching_earnedRuns": 2,
        "pitching_hits": 5,
        "pitching_basesOnBalls": 1,
        "pitching_hitBatters": 0,
        "pitching_battersFaced": 24,
    }
    for k, v in overrides.items():
        target = _SHORT_TO_SGO.get(k, k)
        base[target] = v
    return base


# ── Unit Tests: MLBScorekeeper ────────────────────────────────

class TestMLBDKScoring:
    """Official DK formula tests — no approximation."""

    def test_single_only(self):
        keeper = MLBScorekeeper()
        r = keeper.score_hitter(_sgo_hitter(singles=1, runsScored=0))
        assert r.fantasy_points == 3.0 - 0.5  # 1B=3, K=-0.5
        assert r.is_exact is True

    def test_home_run_with_rbi(self):
        """HR=10, RBI=2, R=2 (if run scored)"""
        keeper = MLBScorekeeper()
        r = keeper.score_hitter(_sgo_hitter(
            singles=0, homeRuns=1, RBI=2, runsScored=1, hits=1, totalBases=4,
        ))
        assert r.fantasy_points == 10 + 4 + 2 - 0.5  # HR=10, RBI=2×2=4, R=2, K=-0.5
        assert r.is_exact is True

    def test_pitcher_with_win(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(), {})
        # IP=6.0×2.25=13.5, K=6×2=12, W=4, ER=2×-2=-4, H=5×-0.6=-3, BB=1×-0.6=-0.6, HB=0
        expected = round(13.5 + 12 + 4 - 4 - 3 - 0.6 + 0, 1)
        assert r.fantasy_points == expected
        assert r.is_exact is True

    def test_pitcher_no_win(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(win=0), {})
        expected = round(13.5 + 12 + 0 - 4 - 3 - 0.6 + 0, 1)
        assert r.fantasy_points == expected
        assert r.is_exact is True

    def test_pitcher_ip_partial(self):
        """IP is computed from outs / 3."""
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(outs=7), {})
        ip = 7 / 3.0 * 2.25  # 5.25
        assert "inningPitched" in r.calculated_from


class TestPartialScores:
    """Missing required fields → historical_partial, never exact."""

    def test_missing_runs_is_partial(self):
        keeper = MLBScorekeeper()
        s = _sgo_hitter(singles=1)
        del s["batting_runsScored"]
        r = keeper.score_hitter(s)
        assert r.is_exact is False
        assert r.scoring_mode == ScoringMode.HISTORICAL_PARTIAL
        assert "run" in r.missing_fields
        assert r.fantasy_points == 3.0 - 0.5  # still computes what's available

    def test_partial_cannot_claim_exact(self):
        """A partial result must never carry is_exact=True."""
        keeper = MLBScorekeeper()
        s = _sgo_hitter(singles=1)
        del s["batting_runsScored"]
        r = keeper.score_hitter(s)
        assert not r.is_exact
        assert "historical_partial" in r.scoring_mode.value

    def test_missing_hb_is_partial(self):
        keeper = MLBScorekeeper()
        s = _sgo_pitcher()
        del s["pitching_hitBatters"]
        r = keeper.score_pitcher(s, {})
        assert r.is_exact is False
        assert "hitBatter" in r.missing_fields

    def test_missing_multiple_fields(self):
        keeper = MLBScorekeeper()
        s = _sgo_hitter(singles=1)
        del s["batting_runsScored"]
        del s["batting_hitByPitch"]
        r = keeper.score_hitter(s)
        assert not r.is_exact
        assert "run" in r.missing_fields
        assert "hitByPitch" in r.missing_fields
        assert len(r.missing_fields) == 2

    def test_fantasy_points_still_computed_for_partial(self):
        """Missing runs-scored does NOT zero the total — it omits
        that category while scoring everything else."""
        keeper = MLBScorekeeper()
        s = _sgo_hitter(singles=1, homeRuns=1, RBI=2, hits=2, totalBases=5)
        del s["batting_runsScored"]
        r = keeper.score_hitter(s)
        # 1B=3, HR=10, 2×RBI=4, K=-0.5 = 16.5 (run is omitted, not zeroed)
        assert r.fantasy_points == 16.5

    def test_all_available_categories_scored(self):
        keeper = MLBScorekeeper()
        s = _sgo_pitcher()
        del s["pitching_hitBatters"]
        r = keeper.score_pitcher(s, {})
        for cat in ["inningPitched", "strikeout", "win", "earnedRun",
                     "hitAllowed", "walkAllowed"]:
            assert cat in r.calculated_from, f"{cat} missing from calculated_from"
        assert "hitBatter" not in r.calculated_from
        assert "hitBatter" in r.missing_fields


class TestFanduelStub:
    def test_fd_raises(self):
        with pytest.raises(NotImplementedError, match="FanDuel"):
            MLBScorekeeper(platform=ScoringPlatform.FANDUEL)


class TestRoleDetection:
    def test_detects_hitter(self):
        from scoring.mlb import _detect_role
        assert _detect_role({"batting_hits": 1}) == PlayerRole.HITTER

    def test_detects_pitcher(self):
        from scoring.mlb import _detect_role
        assert _detect_role({"pitching_strikeouts": 5}) == PlayerRole.PITCHER


class TestRawStatsAuditability:
    def test_raw_stats_present(self):
        keeper = MLBScorekeeper()
        r = keeper.score_hitter(_sgo_hitter(singles=2, runsScored=0))
        assert "batting_singles" in r.raw_stats
        assert "batting_runsScored" in r.raw_stats

    def test_missing_field_null_in_raw(self):
        keeper = MLBScorekeeper()
        s = _sgo_hitter(singles=1)
        del s["batting_runsScored"]
        r = keeper.score_hitter(s)
        assert r.raw_stats.get("batting_runsScored") is None


# ── Projection Separation ─────────────────────────────────────

class TestProjectionSeparation:
    """Verify historical scoring ≠ projection approximation."""

    def test_not_same_as_approximation(self):
        """An actual 2-HR game from SGO gives different results:
        Official: 1B=0, 2B=1, HR=2, RBI=4 → 0+5+20+8-0.5 = 32.5
        Approx:  H=3, HR=2, TB=10 → 9+20+8+12-0.5 = 48.5
        The difference is +16.0 — the approximation inflates HRs."""
        keeper = MLBScorekeeper()
        s = {
            "batting_singles": 0, "batting_doubles": 1, "batting_triples": 0,
            "batting_homeRuns": 2, "batting_RBI": 4, "batting_runsScored": 0,
            "batting_basesOnBalls": 0, "batting_stolenBases": 0,
            "batting_hitByPitch": 0, "batting_strikeouts": 1,
            "batting_atBats": 5, "batting_hits": 3, "batting_totalBases": 10,
        }
        r = keeper.score_hitter(s)
        # Official: 2B=5, 2×HR=20, 4×RBI=8, K=-0.5 = 32.5
        assert r.fantasy_points == 32.5
        # Approximation would be 48.5 — prove they differ
        approx = 3*3 + 2*10 + 4*2 + 10*1.2 + 0 + 0 + (-0.5)
        assert approx == 48.5  # the approximation
        assert r.fantasy_points != approx
        assert abs(r.fantasy_points - approx) > 10  # significant gap


# ── Special Achievements ──────────────────────────────────────

class TestSpecialAchievements:
    def test_cg_derived(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(outs=27), {"displayShort": "F"})
        assert "completeGame" in r.calculated_from
        assert r.calculated_from["completeGame"] == 2.5

    def test_cg_not_awarded_if_not_final(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(outs=27), {"displayShort": "9i"})
        assert "completeGame" not in r.calculated_from

    def test_cg_not_awarded_under_27_outs(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(_sgo_pitcher(outs=18), {"displayShort": "F"})
        assert "completeGame" not in r.calculated_from

    def test_no_hitter_derived(self):
        keeper = MLBScorekeeper()
        r = keeper.score_pitcher(
            _sgo_pitcher(outs=27, hits=0, earnedRuns=0),
            {"displayShort": "F"},
        )
        assert "noHitter" in r.calculated_from
        assert r.calculated_from["noHitter"] == 5.0


# ── build_game_log ────────────────────────────────────────────

@pytest.mark.asyncio
class TestBuildGameLog:
    async def test_build_returns_game_log(self):
        """Minimal integration: a mocked event with 1 game produces
        a valid PlayerGameLog."""
        player_id = "TEST_PLAYER_1_MLB"
        events = [
            {
                "eventID": "ev1",
                "status": {
                    "startsAt": "2026-08-15T19:00:00Z",
                    "displayShort": "F",
                },
                "teams": {
                    "home": {"names": {"short": "NYY"}, "teamID": "NY_YANKS", "score": 3},
                    "away": {"names": {"short": "BOS"}, "teamID": "BOS_SOX", "score": 1},
                },
                "players": {
                    player_id: {"name": "Test Player", "teamID": "NY_YANKS"},
                },
                "results": {
                    "game": {
                        player_id: _sgo_hitter(singles=1, runsScored=0),
                    }
                },
            }
        ]

        log = await build_game_log(events, player_id, n=5)
        assert log is not None
        assert log.player_id == player_id
        assert len(log.games) == 1
        assert log.games[0].opponent == "BOS"
        assert log.games[0].home_away == "home"
        assert log.average_fp == log.games[0].result.fantasy_points
        assert log.scoring_mode == ScoringMode.HISTORICAL_EXACT.value

    async def test_build_partial_when_runs_missing(self):
        """When runs are missing, the game log scoring_mode is
        historical_partial."""
        player_id = "TEST_PLAYER_2_MLB"
        s = _sgo_hitter(singles=1)
        del s["batting_runsScored"]
        events = [
            {
                "eventID": "ev1",
                "status": {"startsAt": "2026-08-15T19:00:00Z", "displayShort": "F"},
                "teams": {
                    "home": {"names": {"short": "NYY"}, "teamID": "NY_YANKS", "score": 3},
                    "away": {"names": {"short": "BOS"}, "teamID": "BOS_SOX", "score": 1},
                },
                "players": {player_id: {"name": "T2", "teamID": "NY_YANKS"}},
                "results": {"game": {player_id: s}},
            }
        ]
        log = await build_game_log(events, player_id, n=5)
        assert log is not None
        assert log.scoring_mode == ScoringMode.HISTORICAL_PARTIAL.value
        assert "run" in log.global_missing_fields
        assert log.average_is_exact is False

    async def test_player_not_found_returns_none(self):
        log = await build_game_log([], "NOBODY_1_MLB")
        assert log is None