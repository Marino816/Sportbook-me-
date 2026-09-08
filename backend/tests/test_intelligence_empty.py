"""Intelligence payload helpers — DFS vs legacy IDs must not mix."""

from pathlib import Path

from api.intelligence_routes import empty_intelligence_payload, finalize_intelligence_payload

ROUTES = Path(__file__).resolve().parents[1] / "api" / "intelligence_routes.py"


def test_missing_slate_is_structured_empty_not_an_exception():
    payload = empty_intelligence_payload(99, "slate_not_found")
    assert payload["empty"] is True
    assert payload["available"] is False
    assert payload["reason"] == "slate_not_found"
    assert payload["players"] == []
    assert payload["games"] == []


def test_dfs_empty_pool_is_truthful_empty():
    payload = finalize_intelligence_payload(
        slate_id=12,
        sport="MLB",
        platform="draftkings",
        dfs_mode="blue_collar",
        players=[],
        games={},
        sgo_available=False,
        build_ms=1,
    )
    assert payload["empty"] is True
    assert payload["available"] is False
    assert payload["reason"] == "no_player_intelligence"
    assert payload["platform"] == "draftkings"
    assert payload["provider"]["dfs"] == "blue_collar"


def test_dfs_slate_is_resolved_before_legacy_slate():
    src = ROUTES.read_text()
    dfs_lookup = src.find("select(DFSSlate).where(DFSSlate.id == slate_id)")
    legacy_lookup = src.find("select(DBSlate).where(DBSlate.id == slate_id)")
    assert dfs_lookup != -1
    assert legacy_lookup != -1
    assert dfs_lookup < legacy_lookup
    assert "HTTPException" not in src
    assert 'empty_intelligence_payload(slate_id, "slate_not_found")' in src
    dfs_branch = src.find("if dfs_slate:")
    dfs_return = src.find("return wrap_data(finalize_intelligence_payload", dfs_branch)
    assert dfs_branch != -1
    assert dfs_lookup < dfs_return < legacy_lookup
