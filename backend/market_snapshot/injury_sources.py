"""Injury source permission record. No live collection. No secrets."""

from __future__ import annotations

# Existing in-repo Scout InjuryProvider is a demo placeholder ("demo_injury_feed"),
# not an official league report and not connected to Market Tools.

NFL_TERMS = {
    "url": "https://www.nfl.com/legal/terms/",
    "retrieved": "2026-09-30",
    "classification": "source_link_only",
    "automated_collection_commercial_display": False,
    "summary": (
        "NFL.com Terms (updated 16 May 2024) §1.3: use is limited to individual "
        "non-commercial informational purposes. Any other use, including commercial "
        "purposes, is prohibited without express prior written consent. Systematic "
        "retrieval of data to create a collection, compilation, database, or directory "
        "is prohibited without that consent."
    ),
}

NBA_TERMS = {
    "url": "https://www.nba.com/termsofuse",
    "retrieved": "2026-09-30",
    "classification": "source_link_only",
    "automated_collection_commercial_display": False,
    "summary": (
        "NBA.com Terms of Use: Basketball Content (including statistics) may not be "
        "reproduced, republished, publicly displayed, or used for public or commercial "
        "purposes without written permission. Personal noncommercial download to a "
        "single computer is the stated exception. Official commercial NBA data, "
        "including injury feeds, is licensed through Sportradar; this assignment does "
        "not purchase that feed."
    ),
}

OFFICIAL_LINKS = {
    "nfl": [
        {
            "label": "NFL official injury report",
            "url": "https://www.nfl.com/injuries/",
            "kind": "official_html_report",
            "note": "Game status vs practice participation are separate NFL products. This app does not import either.",
        }
    ],
    "nba": [
        {
            "label": "NBA official injury report",
            "url": "https://official.nba.com/nba-injury-report-2025-26-season/",
            "kind": "official_report_page",
            "note": "Season landing page published by NBA Official. This app does not import the PDF or HTML tables.",
        }
    ],
}

INJURIES = {
    "status": "source_link_only",
    "live_http": False,
    "live_feed_connected": False,
    "automated_import": False,
    "public_source_downloads_this_assignment": 0,
    "existing_integration": (
        "backend/scout/providers/adapters.py InjuryProvider returns demo_injury_feed with empty players. Not used here."
    ),
    "nfl": NFL_TERMS,
    "nba": NBA_TERMS,
    "official_links": OFFICIAL_LINKS,
    "practice_vs_availability": (
        "NFL practice participation reports are not game-status reports. "
        "Missing reports remain unknown. Projections are not changed."
    ),
    "reason": (
        "Automated collection and commercial display of NFL.com and NBA.com injury "
        "content is not permitted under the published terms without written consent "
        "or a paid official data license. Market Tools therefore links to official "
        "reports and does not ingest player rows."
    ),
    "fixture_only": True,
    "fixtures_are_not_live_coverage": True,
}


def injury_board_for_selector(selector: str | None) -> dict | None:
    key = (selector or "").strip().lower()
    if key not in OFFICIAL_LINKS:
        return None
    return {
        "live_feed_connected": False,
        "message": "Live injury feed not connected",
        "practice_note": INJURIES["practice_vs_availability"],
        "unknown_when_missing": True,
        "projection_adjustment": "not_applied",
        "official_links": OFFICIAL_LINKS[key],
        "reports": [],
    }
