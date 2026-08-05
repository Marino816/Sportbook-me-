"""
SB-Me Analyst tests.

Run isolated: pytest tests/test_analyst.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User
from analyst.engine import (
    MatchupEngine, RiskEngine, EdgeEngine,
    ProjectionChangeAnalyzer, ConfidenceDecomposer,
)

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TestSession() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db


async def _reset_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
async def setup_db():
    await _reset_db()
    yield
    await _reset_db()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_login(client, email):
    await client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    res = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return res.json()["access_token"]


async def _promote_to_pro(email):
    from sqlalchemy import select as sa_select
    async with _TestSession() as db:
        result = await db.execute(sa_select(User).where(User.email == email))
        user = result.scalars().first()
        user.is_pro = True
        await db.commit()


# ── MATCHUP ENGINE TESTS ─────────────────────────────────────

class TestMatchupEngine:
    def test_analyze_with_full_data(self):
        data = {"pace": 102.5, "usage": 0.35, "rest_days": 2, "injury_status": "Healthy", "is_home": True}
        result = MatchupEngine.analyze(data)
        assert result["available_factors"] >= 4
        assert any(f["factor"] == "pace" for f in result["factors"])

    def test_analyze_with_missing_data(self):
        result = MatchupEngine.analyze({})
        assert result["available_factors"] == 0
        assert len(result["missing_factors"]) > 0

    def test_injury_factor_when_not_healthy(self):
        result = MatchupEngine.analyze({"injury_status": "Questionable"})
        assert any(f["factor"] == "injury" for f in result["factors"])


# ── RISK ENGINE TESTS ────────────────────────────────────────

class TestRiskEngine:
    def test_healthy_player_no_risks(self):
        data = {"injury_status": "Healthy", "starting_status": "Confirmed", "games_played": 20, "avg_fp_last_5": 50, "recent_form": 50.0}
        risks = RiskEngine.assess(data)
        assert len(risks) == 0

    def test_injured_player_has_risk(self):
        data = {"injury_status": "Out", "starting_status": "unknown"}
        risks = RiskEngine.assess(data)
        assert len(risks) >= 1
        assert risks[0]["risk_type"] == "injury_uncertainty"
        assert risks[0]["severity"] > 0.8

    def test_small_sample_has_risk(self):
        data = {"injury_status": "Healthy", "starting_status": "Confirmed", "games_played": 2}
        risks = RiskEngine.assess(data)
        assert any(r["risk_type"] == "small_sample" for r in risks)

    def test_stale_data_has_risk(self):
        risks = RiskEngine.assess({"injury_status": "Healthy", "starting_status": "Confirmed", "games_played": 20}, is_stale=True)
        assert any(r["risk_type"] == "stale_data" for r in risks)

    def test_aggregate_zero_for_no_risks(self):
        score = RiskEngine.aggregate_risk_score([])
        assert score == 0.0

    def test_aggregate_positive_for_risks(self):
        risks = [{"risk_type": "injury_uncertainty", "severity": 0.9}, {"risk_type": "stale_data", "severity": 0.7}]
        score = RiskEngine.aggregate_risk_score(risks)
        assert score > 0.1

    def test_empty_player_no_crash(self):
        risks = RiskEngine.assess({})
        assert isinstance(risks, list)


# ── EDGE ENGINE TESTS ────────────────────────────────────────

class TestEdgeEngine:
    def test_strong_edge(self):
        score, comp = EdgeEngine.calculate(0.9, 0.8, 0.7, 0.6, 0.9, 0.85)
        assert score > 60
        assert EdgeEngine.tier(score) in ["Strong Edge", "Elite Edge"]

    def test_weak_edge(self):
        score, comp = EdgeEngine.calculate(0.3, 0.3, 0.3, 0.3, 0.3, 0.3, risk_count=5)
        assert score < 50

    def test_tier_returns_string(self):
        for s in [90, 75, 60, 45, 30]:
            tier = EdgeEngine.tier(s)
            assert isinstance(tier, str)
            assert len(tier) > 0

    def test_risk_penalty_reduces_score(self):
        s1, _ = EdgeEngine.calculate(0.8, 0.8, 0.8, 0.5, 0.8, 0.8, risk_count=0)
        s2, _ = EdgeEngine.calculate(0.8, 0.8, 0.8, 0.5, 0.8, 0.8, risk_count=10)
        assert s2 < s1


# ── PROJECTION CHANGE TESTS ──────────────────────────────────

class TestProjectionChange:
    def test_change_calculated(self):
        result = ProjectionChangeAnalyzer.analyze(1, "player", 55.4, 52.1)
        assert result["absolute_change"] == 3.3
        assert result["percentage_change"] > 5

    def test_no_previous_returns_none_changes(self):
        result = ProjectionChangeAnalyzer.analyze(1, "player", 55.4, None)
        assert result["absolute_change"] is None
        assert result["previous_projection"] is None

    def test_large_change_recommends_refresh(self):
        result = ProjectionChangeAnalyzer.analyze(1, "player", 55.0, 45.0)
        assert result["optimizer_refresh_recommended"]


# ── CONFIDENCE DECOMPOSER TESTS ──────────────────────────────

class TestConfidenceDecomposer:
    def test_returns_all_components(self):
        c = ConfidenceDecomposer.decompose(0.8, 15, True, True, True)
        assert "data_quality" in c
        assert "sample_size" in c
        assert "market_alignment" in c
        assert "injury_clarity" in c
        assert "recency" in c

    def test_missing_market_lowers_score(self):
        c1 = ConfidenceDecomposer.decompose(0.8, 10, True, True, True)
        c2 = ConfidenceDecomposer.decompose(0.8, 10, False, True, True)
        assert c2["market_alignment"] < c1["market_alignment"]

    def test_stale_data_lowers_recency(self):
        c1 = ConfidenceDecomposer.decompose(0.8, 10, True, True, True)
        c2 = ConfidenceDecomposer.decompose(0.8, 10, True, True, False)
        assert c2["recency"] < c1["recency"]


# ── API ENDPOINT TESTS ───────────────────────────────────────

class TestAnalystAPI:
    async def test_player_auth_required(self, client):
        res = await client.get("/analyst/player/1")
        assert res.status_code == 401

    async def test_player_with_auth(self, client):
        token = await _register_and_login(client, "ap@test.com")
        res = await client.get("/analyst/player/1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "headline" in data
        assert "entity_id" in data
        assert "risk_factors" in data

    async def test_game_with_auth(self, client):
        token = await _register_and_login(client, "ag@test.com")
        res = await client.get("/analyst/game/1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    async def test_slate_with_auth(self, client):
        token = await _register_and_login(client, "as@test.com")
        res = await client.get("/analyst/slate/1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    async def test_projection_change(self, client):
        token = await _register_and_login(client, "apc@test.com")
        res = await client.get("/analyst/projection-change/1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "absolute_change" in data or "current_projection" in data

    async def test_top_edges_requires_pro(self, client):
        token = await _register_and_login(client, "free_edge@test.com")
        res = await client.get("/analyst/top-edges?slate_id=1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    async def test_top_edges_with_pro(self, client):
        token = await _register_and_login(client, "pro_edge@test.com")
        await _promote_to_pro("pro_edge@test.com")
        res = await client.get("/analyst/top-edges?slate_id=1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    async def test_risks_requires_pro(self, client):
        token = await _register_and_login(client, "free_risk@test.com")
        res = await client.get("/analyst/risks?entity_id=1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    async def test_risks_with_pro(self, client):
        token = await _register_and_login(client, "pro_risk@test.com")
        await _promote_to_pro("pro_risk@test.com")
        res = await client.get("/analyst/risks?entity_id=1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "risks" in data
        assert "aggregate_score" in data