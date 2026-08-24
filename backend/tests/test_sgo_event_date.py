"""Tests for SGO intelligence date-safe event matching."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest

from projection.sgo_intelligence import _event_date_matches, _safe_str


# ══════════════════════════════════════════════════════════════
# _safe_str
# ══════════════════════════════════════════════════════════════

class TestSafeStr:
    def test_string(self):
        assert _safe_str("hello") == "hello"

    def test_none(self):
        assert _safe_str(None) == "None"

    def test_int(self):
        assert _safe_str(42) == "42"

    def test_float(self):
        assert _safe_str(3.14) == "3.14"

    def test_datetime(self):
        dt = datetime(2026, 8, 24, 19, 40)
        assert "2026" in _safe_str(dt)


# ══════════════════════════════════════════════════════════════
# _event_date_matches — datetime objects (live SDK path)
# ══════════════════════════════════════════════════════════════

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


class TestDatetimeStartTime:
    """start_time is a Python datetime (fresh from SGO SDK)."""

    def test_tz_aware_eastern_matches(self):
        """7:40 PM ET on Aug 24 should match '2026-08-24'."""
        dt = datetime(2026, 8, 24, 19, 40, tzinfo=ET)
        assert _event_date_matches(dt, "2026-08-24")

    def test_tz_aware_eastern_different_date(self):
        """7:40 PM ET on Aug 25 should NOT match '2026-08-24'."""
        dt = datetime(2026, 8, 25, 19, 40, tzinfo=ET)
        assert not _event_date_matches(dt, "2026-08-24")

    def test_tz_aware_utc_matches_eastern_date(self):
        """11:40 PM UTC Aug 24 = 7:40 PM ET Aug 24 — matches."""
        dt = datetime(2026, 8, 24, 23, 40, tzinfo=UTC)
        assert _event_date_matches(dt, "2026-08-24")

    def test_tz_aware_utc_past_midnight(self):
        """01:00 AM UTC Aug 25 = 9:00 PM ET Aug 24 — still Aug 24 ET."""
        dt = datetime(2026, 8, 25, 1, 0, tzinfo=UTC)
        assert _event_date_matches(dt, "2026-08-24")

    def test_naive_datetime_treated_as_eastern(self):
        """Naive datetime is interpreted as Eastern time."""
        dt = datetime(2026, 8, 24, 19, 40)  # naive
        assert _event_date_matches(dt, "2026-08-24")

    def test_naive_datetime_midnight_edge(self):
        """Naive 11:59 PM Aug 23 → next day UTC, but same day ET."""
        dt = datetime(2026, 8, 23, 23, 59)
        assert _event_date_matches(dt, "2026-08-23")


# ══════════════════════════════════════════════════════════════
# _event_date_matches — ISO-8601 strings (Redis cache path)
# ══════════════════════════════════════════════════════════════

class TestIsoStringStartTime:
    """start_time is an ISO string (deserialised from Redis JSON cache)."""

    def test_iso_with_tz(self):
        assert _event_date_matches("2026-08-24T19:40:00-04:00", "2026-08-24")

    def test_iso_without_tz(self):
        assert _event_date_matches("2026-08-24T19:40:00", "2026-08-24")

    def test_iso_space_separator(self):
        assert _event_date_matches("2026-08-24 19:40:00", "2026-08-24")

    def test_date_only_string(self):
        assert _event_date_matches("2026-08-24", "2026-08-24")

    def test_iso_different_date(self):
        assert not _event_date_matches("2026-08-25T19:40:00", "2026-08-24")

    def test_iso_with_utc_tz(self):
        dt = "2026-08-24T23:40:00+00:00"
        assert _event_date_matches(dt, "2026-08-24")

    def test_iso_with_utc_past_midnight_et(self):
        """01:00Z Aug 25 = 9:00 PM ET Aug 24."""
        dt = "2026-08-25T01:00:00+00:00"
        assert _event_date_matches(dt, "2026-08-24")


# ══════════════════════════════════════════════════════════════
# _event_date_matches — edge / missing cases
# ══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_none_start_time(self):
        assert not _event_date_matches(None, "2026-08-24")

    def test_empty_string_start_time(self):
        assert not _event_date_matches("", "2026-08-24")

    def test_none_event_date(self):
        dt = datetime(2026, 8, 24, tzinfo=ET)
        assert not _event_date_matches(dt, None)

    def test_empty_event_date(self):
        dt = datetime(2026, 8, 24, tzinfo=ET)
        assert not _event_date_matches(dt, "")

    def test_dict_start_time(self):
        """SGO v2 nested dict (status, period) — should not match."""
        assert not _event_date_matches({"points": 7, "name": "Final"}, "2026-08-24")

    def test_malformed_string(self):
        assert not _event_date_matches("not-a-date", "2026-08-24")

    def test_int_start_time(self):
        # unix timestamp — should not crash, may or may not match
        result = _event_date_matches(1724534400, "2026-08-24")
        assert isinstance(result, bool)  # never raises

    def test_bool_start_time(self):
        assert not _event_date_matches(True, "2026-08-24")
        assert not _event_date_matches(False, "2026-08-24")


# ══════════════════════════════════════════════════════════════
# _event_date_matches — timezone edge near midnight ET
# ══════════════════════════════════════════════════════════════

class TestMidnightEdge:
    def test_759pm_et(self):
        """7:59 PM ET Aug 24 → should match Aug 24."""
        dt = datetime(2026, 8, 24, 19, 59, tzinfo=ET)
        assert _event_date_matches(dt, "2026-08-24")

    def test_800pm_et(self):
        """8:00 PM ET Aug 24 → should match Aug 24."""
        dt = datetime(2026, 8, 24, 20, 0, tzinfo=ET)
        assert _event_date_matches(dt, "2026-08-24")

    def test_midnight_et_is_next_day(self):
        """12:00 AM ET Aug 25 → should match Aug 25, not Aug 24."""
        dt = datetime(2026, 8, 25, 0, 0, tzinfo=ET)
        assert _event_date_matches(dt, "2026-08-25")
        assert not _event_date_matches(dt, "2026-08-24")

    def test_11pm_utc_is_7pm_et(self):
        """11:00 PM UTC Aug 24 = 7:00 PM ET Aug 24 → matches Aug 24."""
        dt = datetime(2026, 8, 24, 23, 0, tzinfo=UTC)
        assert _event_date_matches(dt, "2026-08-24")

    def test_4am_utc_is_midnight_et(self):
        """4:00 AM UTC Aug 25 = 12:00 AM ET Aug 25 → matches Aug 25."""
        dt = datetime(2026, 8, 25, 4, 0, tzinfo=UTC)
        assert _event_date_matches(dt, "2026-08-25")
        assert not _event_date_matches(dt, "2026-08-24")