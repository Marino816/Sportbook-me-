"""Projection integrity: consensus cap, unmatched slate-source, no synthetic FP."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from projection.native import (
    apply_projection_policy,
    build_projection_integrity_report,
    identity_verified,
    lineup_projection_total,
)
from dfs.freshness import is_optimizer_eligible_status, is_stale_slate, slate_freshness


def test_matched_alcantara_sgo_vs_bc_is_capped_raws_preserved():
    pool = [{
        "id": "SANDY_ALCANTARA_1_MLB",
        "name": "Sandy Alcantara",
        "position": "P",
        "roster_position": "P",
        "projected_fp": 30.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 30.5,
        "fppg": 12.8,
        "salary": 8500,
        "team": "MIA",
        "mapping_status": "MATCHED",
        "game_info": "MIA@NYM 09_08_26",
    }]
    out = apply_projection_policy(pool)
    p = out[0]
    assert p["sgo_fp"] == 30.5
    assert p["bc_fp"] == 12.8
    assert p["fppg"] == 12.8
    assert p["projected_fp"] == 17.3
    assert p["projection_source"] == "CONSENSUS_CAPPED"
    assert p["identity_verified"] is True
    assert identity_verified(p)


def test_matched_sandoval_sgo_vs_bc_is_capped_raws_preserved():
    pool = [{
        "id": "PATRICK_SANDOVAL_1_MLB",
        "name": "Patrick Sandoval",
        "position": "P",
        "roster_position": "P",
        "projected_fp": 29.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 29.5,
        "fppg": 13.5,
        "salary": 7000,
        "team": "BOS",
        "mapping_status": "MATCHED",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["sgo_fp"] == 29.5
    assert p["fppg"] == 13.5
    assert p["projected_fp"] == 18.2
    assert p["projection_source"] == "CONSENSUS_CAPPED"


def test_matched_ramirez_sgo_below_bc_is_capped_raws_preserved():
    pool = [{
        "id": "JOSE_RAMIREZ_1_MLB",
        "name": "Jose Ramirez",
        "position": "3B",
        "projected_fp": 6.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 6.5,
        "fppg": 9.9,
        "salary": 5500,
        "team": "CLE",
        "mapping_status": "MATCHED",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["sgo_fp"] == 6.5
    assert p["fppg"] == 9.9
    assert p["projected_fp"] == 8.8
    assert p["projection_source"] == "CONSENSUS_CAPPED"


def test_unmatched_does_not_use_sgo_uses_slate_fppg_only():
    pool = [{
        "id": "44062819",
        "name": "Adley Rutschman",
        "position": "C",
        "projected_fp": 30.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 30.5,
        "fppg": 8.0,
        "salary": 3600,
        "team": "BOS",
        "mapping_status": "UNMATCHED",
        "game_info": "BOS@LAA 09_08_26",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["sgo_fp"] == 30.5
    assert p["fppg"] == 8.0
    assert p["projected_fp"] == 8.0
    assert p["projection_source"] == "SLATE_SOURCE"
    assert p["identity_verified"] is False


def test_review_required_is_not_a_verified_match():
    pool = [{
        "id": "x",
        "name": "Unknown",
        "position": "OF",
        "projected_fp": 22.0,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 22.0,
        "fppg": 7.1,
        "mapping_status": "REVIEW_REQUIRED",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["projected_fp"] == 7.1
    assert p["projection_source"] == "SLATE_SOURCE"
    assert p["sgo_fp"] == 22.0


def test_unmatched_sgo_only_is_unavailable_not_synthetic():
    pool = [{
        "id": "ghost",
        "name": "No Slate Proj",
        "position": "P",
        "roster_position": "P",
        "projected_fp": 30.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 30.5,
        "fppg": None,
        "mapping_status": "UNMATCHED",
        "salary": 8500,
        "team": "MIA",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["sgo_fp"] == 30.5
    assert p["projected_fp"] == 0.0
    assert p["projection_source"] == "UNAVAILABLE"
    assert p["identity_verified"] is False


def test_missing_mapping_status_is_unmatched():
    pool = [{
        "id": "1",
        "name": "No Status",
        "position": "OF",
        "projected_fp": 11.1,
        "projection_source": "SGO_FANTASY_MARKET",
        "fppg": 7.0,
    }]
    p = apply_projection_policy(pool)[0]
    assert p["projected_fp"] == 7.0
    assert p["projection_source"] == "SLATE_SOURCE"
    assert p["sgo_fp"] == 11.1


def test_lineup_77_policy_total_and_integrity_report():
    """Same 10 stored players under the new identity-gated policy."""
    players = [
        {"id": "SANDY_ALCANTARA_1_MLB", "name": "Sandy Alcantara", "team": "MIA", "salary": 8500, "position": "P", "roster_position": "P", "projected_fp": 30.5, "projection_source": "SGO_FANTASY_MARKET", "sgo_fp": 30.5, "fppg": 12.8, "mapping_status": "MATCHED", "game_info": "MIA@NYM 09_08_26"},
        {"id": "PATRICK_SANDOVAL_1_MLB", "name": "Patrick Sandoval", "team": "BOS", "salary": 7000, "position": "P", "roster_position": "P", "projected_fp": 29.5, "projection_source": "SGO_FANTASY_MARKET", "sgo_fp": 29.5, "fppg": 13.5, "mapping_status": "MATCHED", "game_info": "BOS@LAA 09_08_26"},
        {"id": "44062819", "name": "Adley Rutschman", "team": "BOS", "salary": 3600, "position": "C", "projected_fp": 8.0, "projection_source": "BC_PROJ_FALLBACK", "fppg": 8.0, "mapping_status": "UNMATCHED", "game_info": "BOS@LAA 09_08_26"},
        {"id": "44062836", "name": "Nathaniel Lowe", "team": "CLE", "salary": 3300, "position": "1B", "projected_fp": 8.2, "projection_source": "BC_PROJ_FALLBACK", "fppg": 8.2, "mapping_status": "UNMATCHED", "game_info": "CLE@BAL 09_08_26"},
        {"id": "44062846", "name": "Hao-Yu Lee", "team": "DET", "salary": 3200, "position": "2B", "projected_fp": 7.0, "projection_source": "BC_PROJ_FALLBACK", "fppg": 7.0, "mapping_status": "UNMATCHED", "game_info": "DET@MIN 09_08_26"},
        {"id": "JOSE_RAMIREZ_1_MLB", "name": "Jose Ramirez", "team": "CLE", "salary": 5500, "position": "3B", "projected_fp": 6.5, "projection_source": "SGO_FANTASY_MARKET", "sgo_fp": 6.5, "fppg": 9.9, "mapping_status": "MATCHED", "game_info": "CLE@BAL 09_08_26"},
        {"id": "TREVOR_STORY_1_MLB", "name": "Trevor Story", "team": "BOS", "salary": 3300, "position": "SS", "projected_fp": 7.9, "projection_source": "BC_PROJ_FALLBACK", "fppg": 7.9, "mapping_status": "MATCHED", "game_info": "BOS@LAA 09_08_26"},
        {"id": "44062802", "name": "Jo Adell", "team": "CLE", "salary": 4100, "position": "OF", "projected_fp": 8.3, "projection_source": "BC_PROJ_FALLBACK", "fppg": 8.3, "mapping_status": "UNMATCHED", "game_info": "CLE@BAL 09_08_26"},
        {"id": "44062830", "name": "Daulton Varsho", "team": "HOU", "salary": 3400, "position": "OF", "projected_fp": 8.4, "projection_source": "BC_PROJ_FALLBACK", "fppg": 8.4, "mapping_status": "UNMATCHED", "game_info": "HOU@PHI 09_08_26"},
        {"id": "JAKOB_MARSEE_1_MLB", "name": "Jakob Marsee", "team": "MIA", "salary": 3200, "position": "OF", "projected_fp": 7.8, "projection_source": "BC_PROJ_FALLBACK", "fppg": 7.8, "mapping_status": "MATCHED", "game_info": "MIA@NYM 09_08_26"},
    ]
    before = lineup_projection_total(players)
    assert before == 122.1
    out = apply_projection_policy(players)
    after = lineup_projection_total(out)
    by_name = {p["name"]: p for p in out}
    assert by_name["Sandy Alcantara"]["projected_fp"] == 17.3
    assert by_name["Patrick Sandoval"]["projected_fp"] == 18.2
    assert by_name["Jose Ramirez"]["projected_fp"] == 8.8
    assert by_name["Adley Rutschman"]["projected_fp"] == 8.0
    assert by_name["Adley Rutschman"]["projection_source"] == "SLATE_SOURCE"
    assert after == 99.9
    report = build_projection_integrity_report(
        out,
        slate_id=98,
        slate_name="6:35PM ET (Turbo) 5 Games",
        salary_source="blue_collar",
        freshness="CURRENT",
        uploaded_at="2026-09-08 12:54:47+00:00",
    )
    assert report["matched_count"] == 5
    assert report["unmatched_count"] == 5
    assert report["salary_source"] == "stored_contest_salaries"
    assert report["freshness"] == "CURRENT"
    alc = next(r for r in report["players"] if r["name"] == "Sandy Alcantara")
    assert alc["identity_verified"] is True
    assert alc["raw_sgo_fp"] == 30.5
    assert alc["raw_bc_fp"] == 12.8
    assert alc["optimizer_projected_fp"] == 17.3
    assert alc["slate_member"] is True
    assert "09_08_26" in (alc["game_info"] or "")


def test_policy_is_idempotent_on_raw_sources():
    pool = [{
        "id": "SANDY_ALCANTARA_1_MLB",
        "name": "Sandy Alcantara",
        "position": "P",
        "roster_position": "P",
        "projected_fp": 30.5,
        "projection_source": "SGO_FANTASY_MARKET",
        "sgo_fp": 30.5,
        "fppg": 12.8,
        "mapping_status": "MATCHED",
    }]
    once = apply_projection_policy(pool)
    twice = apply_projection_policy(once)
    assert twice[0]["sgo_fp"] == 30.5
    assert twice[0]["fppg"] == 12.8
    assert twice[0]["projected_fp"] == 17.3


def test_my_proj_not_replaced():
    pool = [{
        "id": "1",
        "name": "Override",
        "position": "OF",
        "projected_fp": 12.0,
        "projection_source": "MY_PROJ",
        "sgo_fp": 20.0,
        "fppg": 10.0,
        "mapping_status": "MATCHED",
    }]
    p = apply_projection_policy(pool)[0]
    assert p["projected_fp"] == 12.0
    assert p["projection_source"] == "MY_PROJ"
    assert p["sgo_fp"] == 20.0
    assert p["fppg"] == 10.0


def test_stale_published_slate_still_not_optimizer_eligible():
    past = datetime.now(ZoneInfo("America/New_York")) - timedelta(days=5)
    assert is_stale_slate(past) is True
    assert slate_freshness(past) == "STALE"
    assert is_optimizer_eligible_status("PUBLISHED", past, "MLB") is False


def test_current_published_slate_remains_eligible():
    today = datetime.now(ZoneInfo("America/New_York"))
    assert slate_freshness(today) == "CURRENT"
    assert is_optimizer_eligible_status("PUBLISHED", today, "MLB") is True
