"""Blue Collar DFS Adapter tests."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from dfs.bcdfs_adapter import (
    BcRateLimiter,
    normalize_team,
    split_eligible_positions,
    parse_slate_date,
    parse_slate_time,
    bc_slate_key,
    _try_int,
    _try_float,
    parse_bc_response,
    fetch_bc_endpoint,
    BcApiError,
    BcRateLimitError,
    BcAuthError,
    BcParseResult,
)
from dfs.models import DFSContestPlayer, DFSSlate


# ══════════════════════════════════════════════════════════════
# Unit: normalisation helpers
# ══════════════════════════════════════════════════════════════

class TestNormalizeTeam:
    def test_ath_to_oak(self):
        assert normalize_team("ATH") == "OAK"
        assert normalize_team("ath") == "OAK"

    def test_chw_to_cws(self):
        assert normalize_team("CHW") == "CWS"
        assert normalize_team("chw") == "CWS"

    def test_passthrough(self):
        assert normalize_team("SEA") == "SEA"
        assert normalize_team("PHI") == "PHI"
        assert normalize_team("CWS") == "CWS"

    def test_empty(self):
        assert normalize_team("") == ""


class TestSplitEligiblePositions:
    def test_single(self):
        assert split_eligible_positions("P") == ["P"]
        assert split_eligible_positions("OF") == ["OF"]
        assert split_eligible_positions("C") == ["C"]

    def test_multi(self):
        assert split_eligible_positions("1B/2B") == ["1B", "2B"]
        assert split_eligible_positions("3B/OF") == ["3B", "OF"]
        assert split_eligible_positions("2B/SS") == ["2B", "SS"]

    def test_triple(self):
        assert split_eligible_positions("1B/2B/OF") == ["1B", "2B", "OF"]

    def test_sp_rp_normalised(self):
        assert split_eligible_positions("SP") == ["P"]
        assert split_eligible_positions("RP") == ["P"]

    def test_whitespace(self):
        assert split_eligible_positions(" 1B / 2B ") == ["1B", "2B"]

    def test_lowercase(self):
        assert split_eligible_positions("1b/2b") == ["1B", "2B"]


class TestParseSlateDate:
    def test_valid(self):
        assert parse_slate_date("08_24_26") == date(2026, 8, 24)

    def test_with_whitespace(self):
        assert parse_slate_date(" 08_24_26 ") == date(2026, 8, 24)

    def test_none(self):
        assert parse_slate_date(None) is None
        assert parse_slate_date("") is None

    def test_bad_format(self):
        assert parse_slate_date("not-a-date") is None


class TestParseSlateTime:
    def test_740pm_et(self):
        dt = parse_slate_time("7:40PM ET Main 7 Games", date(2026, 8, 24))
        assert dt == datetime(2026, 8, 24, 19, 40)

    def test_am(self):
        dt = parse_slate_time("10:05AM ET Early", date(2026, 8, 24))
        assert dt == datetime(2026, 8, 24, 10, 5)

    def test_noon(self):
        dt = parse_slate_time("12:00PM ET", date(2026, 8, 24))
        assert dt == datetime(2026, 8, 24, 12, 0)

    def test_midnight(self):
        dt = parse_slate_time("12:00AM ET", date(2026, 8, 24))
        assert dt == datetime(2026, 8, 24, 0, 0)

    def test_no_time(self):
        dt = parse_slate_time("NoTime Here", date(2026, 8, 24))
        assert dt == datetime(2026, 8, 24, 12, 0)

    def test_none_date(self):
        assert parse_slate_time("7:40PM ET", None) is None


class TestBcSlateKey:
    def test_deterministic(self):
        k1 = bc_slate_key("MLB", "draftkings", "08_24_26", "7:40PM ET Main 7 Games")
        k2 = bc_slate_key("MLB", "draftkings", "08_24_26", "7:40PM ET Main 7 Games")
        assert k1 == k2
        assert len(k1) == 32

    def test_different_platform(self):
        k1 = bc_slate_key("MLB", "draftkings", "08_24_26", "Main")
        k2 = bc_slate_key("MLB", "fanduel", "08_24_26", "Main")
        assert k1 != k2

    def test_different_date(self):
        k1 = bc_slate_key("MLB", "draftkings", "08_24_26", "Main")
        k2 = bc_slate_key("MLB", "draftkings", "08_25_26", "Main")
        assert k1 != k2


class TestTryInt:
    def test_valid(self):
        assert _try_int("9500") == 9500
        assert _try_int("2000") == 2000

    def test_float_string(self):
        assert _try_int("9500.0") == 9500

    def test_bad(self):
        assert _try_int("abc") == 0
        assert _try_int(None) == 0
        assert _try_int("") == 0

    def test_negative(self):
        assert _try_int("-100") == -100


class TestTryFloat:
    def test_valid(self):
        assert _try_float("16.63") == 16.63
        assert _try_float("0.0") == 0.0

    def test_bad(self):
        assert _try_float("abc") == 0.0
        assert _try_float(None) == 0.0


# ══════════════════════════════════════════════════════════════
# BC sample data
# ══════════════════════════════════════════════════════════════

MLB_DK_SAMPLE = {
    "slates": [
        {
            "slate": "7:40PM ET Main 7 Games",
            "date": "08_24_26",
            "updated": "11:16:06 ET",
            "info": [
                {"name": "Zack Wheeler", "salary": "10800", "projection": "20.33",
                 "value": "1.9", "beta_proj": "0.0", "site_id": "43911111",
                 "position": "P", "team": "PHI", "opponent": "SEA"},
                {"name": "Byron Buxton", "salary": "6000", "projection": "11.09",
                 "value": "1.8", "beta_proj": "0.0", "site_id": "43922222",
                 "position": "OF", "team": "MIN", "opponent": "ATH"},
                {"name": "Sal Stewart", "salary": "5200", "projection": "9.65",
                 "value": "1.9", "beta_proj": "0.0", "site_id": "43933333",
                 "position": "1B/2B", "team": "CIN", "opponent": "SF"},
                {"name": "J.T. Realmuto", "salary": "4500", "projection": "0.0",
                 "value": "0.0", "beta_proj": "0.0", "site_id": "43944444",
                 "position": "C", "team": "PHI", "opponent": "SEA"},
                {"name": "Bench Player", "salary": "2000", "projection": "0.0",
                 "value": "0.0", "beta_proj": "0.0", "site_id": "43955555",
                 "position": "3B/SS", "team": "ATH", "opponent": "MIN"},
            ],
        },
        {
            "slate": "6:40PM ET (Turbo) 3 Games",
            "date": "08_24_26",
            "updated": "11:16:06 ET",
            "info": [
                {"name": "Taj Bradley", "salary": "8700", "projection": "17.5",
                 "value": "2.0", "beta_proj": "0.0", "site_id": "43966666",
                 "position": "P", "team": "TB", "opponent": "DET"},
            ],
        },
    ]
}

EMPTY_SLATES = {"slates": []}
EMPTY_SLATES_NO_PLAYERS = {
    "slates": [{"slate": "Empty", "date": "08_24_26", "updated": "00:00:00 ET", "info": []}]
}
MALFORMED = {"slates": "not a list"}


# ══════════════════════════════════════════════════════════════
# Unit: parse_bc_response
# ══════════════════════════════════════════════════════════════

class TestParseBcResponse:
    def test_mlb_dk_parsing(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        assert result.success
        assert len(result.slates) == 2
        assert result.total_players == 6

    def test_slate_identity(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main = result.slates[0]
        assert main.slate_name == "7:40PM ET Main 7 Games"
        assert main.platform == "draftkings"
        assert main.sport == "MLB"
        assert main.data_source == "blue_collar"
        assert main.player_count == 5
        assert main.start_time == datetime(2026, 8, 24, 19, 40)

    def test_player_fields(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main_players = result.players_by_slate[result.slates[0].slate_id]
        wheeler = [p for p in main_players if p.player_name == "Zack Wheeler"][0]
        assert wheeler.player_id == "43911111"
        assert wheeler.team == "PHI"
        assert wheeler.opponent == "SEA"
        assert wheeler.position == "P"
        assert wheeler.eligible_positions == ["P"]
        assert wheeler.salary == 10800
        assert wheeler.data_source == "blue_collar"

    def test_multi_position(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main_players = result.players_by_slate[result.slates[0].slate_id]
        sal = [p for p in main_players if p.player_name == "Sal Stewart"][0]
        assert sal.position == "1B"
        assert sal.eligible_positions == ["1B", "2B"]

    def test_ath_oak_normalization(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main_players = result.players_by_slate[result.slates[0].slate_id]
        bench = [p for p in main_players if p.player_name == "Bench Player"][0]
        # ATH → OAK
        assert bench.team == "OAK"

    def test_empty_slates_list(self):
        result = parse_bc_response(EMPTY_SLATES, "NFL", "draftkings")
        assert not result.errors
        assert len(result.slates) == 0
        assert result.warnings == [
            "No slates with players found in BC NFL draftkings response"
        ]

    def test_empty_players_in_slate(self):
        result = parse_bc_response(EMPTY_SLATES_NO_PLAYERS, "MLB", "draftkings")
        assert len(result.slates) == 0
        assert len(result.warnings) > 0

    def test_malformed_slates(self):
        result = parse_bc_response(MALFORMED, "MLB", "draftkings")
        assert not result.success
        assert len(result.errors) > 0

    def test_deterministic_slate_key(self):
        result1 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        result2 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        assert result1.slates[0].slate_id == result2.slates[0].slate_id

    def test_bc_value_and_beta_preserved_on_player(self):
        """value/beta_proj persist on the contest player for slate metadata sync."""
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main_players = result.players_by_slate[result.slates[0].slate_id]
        wheeler = [p for p in main_players if p.player_name == "Zack Wheeler"][0]
        assert wheeler.salary == 10800
        assert wheeler.fppg == 20.3
        assert wheeler.bc_value == 1.9
        assert wheeler.bc_beta_proj is None  # sample beta_proj is 0.0
        assert not hasattr(wheeler, "projected_fp")

    def test_zero_salary_player_still_included(self):
        """Zero-salary players should still parse (they exist in BC data)."""
        zero_sal_data = {
            "slates": [{
                "slate": "Test", "date": "08_24_26", "updated": "00:00 ET",
                "info": [{"name": "Zero Guy", "salary": "0", "projection": "0",
                          "value": "0", "beta_proj": "0", "site_id": "999",
                          "position": "P", "team": "SEA", "opponent": "PHI"}]
            }]
        }
        result = parse_bc_response(zero_sal_data, "MLB", "draftkings")
        assert result.total_players == 1

    def test_invalid_slate_in_list(self):
        """Non-dict slate entries should be skipped with a warning."""
        broken = {"slates": ["not a dict", MLB_DK_SAMPLE["slates"][0]]}
        result = parse_bc_response(broken, "MLB", "draftkings")
        assert len(result.warnings) > 0
        assert len(result.slates) >= 1  # the valid one should still parse

    def test_game_info_derived(self):
        result = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        main_players = result.players_by_slate[result.slates[0].slate_id]
        wheeler = [p for p in main_players if p.player_name == "Zack Wheeler"][0]
        assert "@" in wheeler.game_info
        assert "PHI" in wheeler.game_info
        assert "SEA" in wheeler.game_info


# ══════════════════════════════════════════════════════════════
# Rate Limiter tests
# ══════════════════════════════════════════════════════════════

class TestBcRateLimiter:
    def test_can_request_initially(self):
        rl = BcRateLimiter()
        assert rl.can_request()
        assert rl.remaining() > 0

    def test_remaining_decreases(self):
        rl = BcRateLimiter()
        before = rl.remaining()
        rl.record()
        assert rl.remaining() == before - 1

    def test_exhaustion(self):
        rl = BcRateLimiter()
        for _ in range(rl.remaining()):
            rl.record()
        assert not rl.can_request()

    def test_keyed_records(self):
        rl = BcRateLimiter()
        rl.record("MLB_draftkings")
        rl.record("MLB_draftkings")
        rl.record("MLB_fanduel")
        # total should be 3
        assert rl.remaining() == 190 - 3

    def test_reset_on_new_day(self):
        rl = BcRateLimiter()
        # Force yesterday's reset
        rl._reset_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert rl.can_request()
        assert rl.remaining() == 190  # reset


# ══════════════════════════════════════════════════════════════
# API error handling tests
# ══════════════════════════════════════════════════════════════

class TestFetchErrors:
    def test_auth_error_401(self, monkeypatch):
        monkeypatch.setenv("BCDFS_API_KEY", "test-key-123")
        with patch("dfs.bcdfs_adapter.urllib.request.urlopen") as mock_open:
            from urllib.error import HTTPError
            mock_open.side_effect = HTTPError(
                "http://x", 401, "Unauthorized", {}, None
            )
            with pytest.raises(BcAuthError):
                fetch_bc_endpoint("MLB", "draftkings")

    def test_rate_limit_429(self, monkeypatch):
        monkeypatch.setenv("BCDFS_API_KEY", "test-key-123")
        with patch("dfs.bcdfs_adapter.urllib.request.urlopen") as mock_open:
            from urllib.error import HTTPError
            mock_open.side_effect = HTTPError(
                "http://x", 429, "Too Many", {}, None
            )
            with pytest.raises(BcRateLimitError):
                fetch_bc_endpoint("MLB", "draftkings")

    def test_5xx(self, monkeypatch):
        monkeypatch.setenv("BCDFS_API_KEY", "test-key-123")
        with patch("dfs.bcdfs_adapter.urllib.request.urlopen") as mock_open:
            from urllib.error import HTTPError
            mock_open.side_effect = HTTPError(
                "http://x", 500, "Error", {}, None
            )
            with pytest.raises(BcApiError) as exc_info:
                fetch_bc_endpoint("MLB", "draftkings")
            assert exc_info.value.status == 500

    def test_no_key_raises(self, monkeypatch):
        monkeypatch.delenv("BCDFS_API_KEY", raising=False)
        with pytest.raises(BcAuthError):
            fetch_bc_endpoint("MLB", "draftkings")

    def test_unknown_sport_platform(self, monkeypatch):
        monkeypatch.setenv("BCDFS_API_KEY", "test-key-123")
        with pytest.raises(ValueError):
            fetch_bc_endpoint("NHL", "draftkings")

    def test_rate_limiter_exhausted(self, monkeypatch):
        monkeypatch.setenv("BCDFS_API_KEY", "test-key-123")
        rl = BcRateLimiter()
        for _ in range(rl.remaining()):
            rl.record()
        with pytest.raises(BcRateLimitError):
            fetch_bc_endpoint("MLB", "draftkings", rate_limiter=rl)

    def test_api_key_not_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("BCDFS_API_KEY", "super-secret-key-abc123")
        with patch("dfs.bcdfs_adapter.urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(EMPTY_SLATES).encode()
            mock_open.return_value = mock_resp
            import logging
            with caplog.at_level(logging.INFO):
                fetch_bc_endpoint("NBA", "draftkings")
            log_text = " ".join(r.message for r in caplog.records if r.message)
            assert "super-secret-key-abc123" not in log_text


# ══════════════════════════════════════════════════════════════
# Existing CSV importer regression guard (sanity check)
# ══════════════════════════════════════════════════════════════

class TestCsvImporterStillWorks:
    """Verify the existing CSV parser is not broken by our changes."""
    def test_dk_csv_imports(self):
        from dfs.parsers import parse_draftkings_csv
        csv_text = (
            "Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame\n"
            "P,Tarik Skubal (12345),Tarik Skubal,12345,SP,10500,DET@CLE 08/11/2026 07:10PM ET,DET,22.5\n"
            "C,J.T. Realmuto (11111),J.T. Realmuto,11111,C,4500,PHI@ATL 08/11/2026 07:20PM ET,PHI,8.2\n"
        )
        slate_obj, players = parse_draftkings_csv(csv_text, slate_name="Test")
        assert len(players) == 2
        assert players[0].platform == "draftkings"
        assert players[0].salary == 10500

    def test_fd_csv_imports(self):
        from dfs.parsers import parse_fanduel_csv
        csv_text = (
            "Id,First Name,Last Name,Position,FPPG,Played,Salary,Game,Team,Opponent,Injury\n"
            "12345,Tarik,Skubal,SP,22.5,1,10500,DET@CLE,DET,CLE,\n"
        )
        slate_obj, players = parse_fanduel_csv(csv_text, slate_name="Test")
        assert len(players) == 1
        assert players[0].platform == "fanduel"


# ══════════════════════════════════════════════════════════════
# Idempotency tests (unit: same parse → same slate key)
# ══════════════════════════════════════════════════════════════

class TestParseIdempotency:
    def test_same_input_same_keys(self):
        r1 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        r2 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        assert [s.slate_id for s in r1.slates] == [s.slate_id for s in r2.slates]

    def test_different_platform_different_keys(self):
        r1 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        r2 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "fanduel")
        assert r1.slates[0].slate_id != r2.slates[0].slate_id

    def test_date_change_changes_key(self):
        modified = json.loads(json.dumps(MLB_DK_SAMPLE))
        modified["slates"][0]["date"] = "08_25_26"
        r1 = parse_bc_response(MLB_DK_SAMPLE, "MLB", "draftkings")
        r2 = parse_bc_response(modified, "MLB", "draftkings")
        assert r1.slates[0].slate_id != r2.slates[0].slate_id