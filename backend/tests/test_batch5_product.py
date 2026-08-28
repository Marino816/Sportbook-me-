"""Repair Batch 5 — customer-facing product surface tests."""

from unittest.mock import patch

import pytest

from assistant.tools import get_sgo_current_events, get_sgo_current_odds
from providers.sgo_platforms import catalog_count, classify_observed_books, load_platform_catalog
from providers.sgo_rookie import (
    ROOKIE_LEAGUE_IDS,
    SOCCER_LEAGUE_IDS,
    normalize_league_id,
    parse_account_usage,
)


def test_fifty_five_platform_catalog():
    catalog = load_platform_catalog()
    assert catalog_count() == 55
    assert len(catalog) == 55
    assert all("id" in row and "name" in row and "sgo_ids" in row for row in catalog)


def test_platform_mapping_categories():
    result = classify_observed_books(["draftkings", "fanduel", "unknownbookxyz"])
    assert result["counts"]["total_existing"] == 55
    assert result["counts"]["mapped_to_sgo"] >= 1
    assert result["counts"]["mapping_needed"] >= 1
    assert "unknownbookxyz" in result["sgo_unlisted"]
    assert "note" in result


def test_seventeen_leagues_and_soccer_aliases():
    assert len(ROOKIE_LEAGUE_IDS) == 17
    assert len(SOCCER_LEAGUE_IDS) == 8
    assert normalize_league_id("UCL") == "UEFA_CHAMPIONS_LEAGUE"
    assert normalize_league_id("EPL") == "EPL"
    assert normalize_league_id("premier league") == "EPL"


def test_account_usage_sanitized_no_secrets():
    raw = {
        "success": True,
        "email": "secret@example.com",
        "keyID": "KEY-SHOULD-NOT-LEAK",
        "customerID": "CUST-SHOULD-NOT-LEAK",
        "data": {
            "tier": "Rookie",
            "isActive": True,
            "email": "also-secret@example.com",
            "keyID": "nested-key",
            "rateLimits": {
                "current-entities": 1200,
                "objects-per-month": 100000,
            },
        },
    }
    parsed = parse_account_usage(raw)
    blob = str(parsed)
    assert parsed["tier"] == "Rookie"
    assert parsed["used"] == 1200
    assert parsed["monthly_limit"] == 100000
    assert parsed["remaining"] == 98800
    assert parsed["percent_used"] == 1.2
    assert "secret@example.com" not in blob
    assert "KEY-SHOULD-NOT-LEAK" not in blob
    assert "CUST-SHOULD-NOT-LEAK" not in blob
    assert "email" not in parsed
    assert "keyID" not in parsed
    assert "customerID" not in parsed
    assert "37394" not in blob


def test_sgo_usage_route_is_admin_only():
    from api.sgo_data import router as sgo_router
    from api.admin import router as admin_router

    sgo_usage = next(
        r for r in sgo_router.routes
        if str(getattr(r, "path", "")).rstrip("/").endswith("/usage")
    )
    admin_usage = next(
        r for r in admin_router.routes
        if str(getattr(r, "path", "")).rstrip("/").endswith("/sgo-usage")
    )
    sgo_dep = " ".join(
        str(d) for d in (sgo_usage.dependant.dependencies if hasattr(sgo_usage, "dependant") else [])
    )
    admin_dep = " ".join(
        str(d) for d in (admin_usage.dependant.dependencies if hasattr(admin_usage, "dependant") else [])
    )
    assert "require_admin" in sgo_dep
    assert "require_admin" in admin_dep


@pytest.mark.asyncio
async def test_ai_unavailable_when_cache_empty():
    with patch("providers.nested_events.load_cached_events", return_value=[]):
        events = await get_sgo_current_events(None, sport="EPL")
        odds = await get_sgo_current_odds(None, sport="UEFA_CHAMPIONS_LEAGUE")
    assert events["available"] is False
    assert odds["available"] is False
    assert "unavailable" in (odds["note"] or "").lower()
    assert "do not substitute" in (odds["note"] or "").lower()


def test_protected_market_tools_prefix_documented():
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "web" / "src" / "components" / "auth" / "ProtectedRoute.tsx"
    text = src.read_text()
    assert '"/market-tools"' in text
    assert '"/admin"' in text
    assert '"/dashboard"' in text
