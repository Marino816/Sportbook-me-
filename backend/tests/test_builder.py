"""
SB-Me Builder tests.

Run isolated: pytest tests/test_builder.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User
from builder.strategy import (
    get_strategy, list_strategies, builder_objective, STRATEGY_PROFILES,
)
from builder.engine import (
    BuilderValidator, ExposureEngine, PortfolioEngine, ExplanationGenerator,
)

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with _TestSession() as s: yield s
app.dependency_overrides[get_db] = override_get_db

async def _reset_db():
    async with _engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)

@pytest.fixture(autouse=True)
async def setup_db():
    await _reset_db(); yield; await _reset_db()

@pytest.fixture
async def client():
    t = ASGITransport(app=app)
    async with AsyncClient(transport=t, base_url="http://test") as ac: yield ac

async def _login(client, email):
    await client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return r.json()["access_token"]

async def _promote(email):
    from sqlalchemy import select as sa
    async with _TestSession() as db:
        r = await db.execute(sa(User).where(User.email == email))
        u = r.scalars().first(); u.is_pro = True; await db.commit()

NBA_POOL = [{"id":1,"name":"P1","team":"A","salary":5000,"roster_position":"PG","projected_fp":30,"ceiling":40,"edge_score":60,"risk_score":0.1}]

# ── STRATEGY TESTS ───────────────────────────────────────────
class TestStrategies:
    def test_all_12_profiles(self):
        assert len(STRATEGY_PROFILES) == 12
    def test_get_cash(self):
        s = get_strategy("cash"); assert s.name == "Cash"
    def test_get_aggressive(self):
        s = get_strategy("aggressive"); assert s.name == "Aggressive"
    def test_unknown_raises(self):
        with pytest.raises(ValueError): get_strategy("nonexistent")
    def test_objective_positive(self):
        s = get_strategy("balanced")
        assert builder_objective({"projected_fp": 50, "edge_score": 70}, s) > 0

# ── VALIDATION TESTS ─────────────────────────────────────────
class TestValidation:
    def test_valid_platform(self):
        assert BuilderValidator.validate_platform("draftkings") is None
        assert BuilderValidator.validate_platform("fanduel") is None
    def test_invalid_platform(self):
        assert BuilderValidator.validate_platform("yahoo") is not None
    def test_valid_sport(self):
        assert BuilderValidator.validate_sport("nba") is None
    def test_invalid_sport(self):
        assert BuilderValidator.validate_sport("nfl") is not None
    def test_lock_exclude_conflict(self):
        errs = BuilderValidator.validate_constraints([1], [1], NBA_POOL)
        assert len(errs) > 0
    def test_salary_cap_enforcement(self):
        errs = BuilderValidator.validate_roster(
            [{"salary": 60000}], "draftkings", []
        )
        assert any("salary" in e.lower() for e in errs)
    def test_wrong_lineup_size_dk(self):
        errs = BuilderValidator.validate_roster(
            [{"salary": 1000} for _ in range(3)], "draftkings", []
        )
        assert any("8" in e for e in errs)

# ── EXPOSURE TESTS ───────────────────────────────────────────
class TestExposure:
    def test_calculate_basic(self):
        lus = [[{"id": 1, "team": "A"}], [{"id": 1, "team": "A"}], [{"id": 2, "team": "B"}]]
        exp = ExposureEngine.calculate_exposure(lus)
        assert exp["players"][1] == pytest.approx(66.7, 0.1)
    def test_check_rules_satisfied(self):
        exp = {"players": {1: 30}, "teams": {}}
        unsat = ExposureEngine.check_exposure_rules(exp, [{"entity_type":"player","entity_id":1,"max_exposure":50}])
        assert len(unsat) == 0
    def test_max_exposure_violated(self):
        exp = {"players": {1: 80}, "teams": {}}
        unsat = ExposureEngine.check_exposure_rules(exp, [{"entity_type":"player","entity_id":1,"max_exposure":50}])
        assert len(unsat) == 1

# ── PORTFOLIO TESTS ──────────────────────────────────────────
class TestPortfolio:
    def test_build_empty(self):
        p = PortfolioEngine.build_portfolio([], "balanced")
        assert p["lineup_count"] == 0
    def test_build_with_lineups(self):
        lus = [{"projected_score": 300, "total_salary": 48000, "players": [{"id":1,"team":"A"}]}]
        p = PortfolioEngine.build_portfolio(lus, "balanced")
        assert p["lineup_count"] == 1
        assert p["avg_projection"] == 300

# ── EXPLANATION TESTS ────────────────────────────────────────
class TestExplanation:
    def test_explains_lineup(self):
        lu = {"projected_score": 280, "total_salary": 48000, "players": [
            {"id":1,"name":"Star","edge_score":80,"risk_score":0.1},
            {"id":2,"name":"Risk","edge_score":40,"risk_score":0.5},
        ]}
        exp = ExplanationGenerator.explain(lu, "balanced", "7d.0.1", [1], [3])
        assert "Star" in str(exp["top_edge_players"])
        assert "Risk" in exp["main_risks"]
        assert exp["locks_applied"] == [1]

# ── API TESTS ────────────────────────────────────────────────
class TestBuilderAPI:
    async def test_validate(self, client):
        t = await _login(client, "val@test.com")
        r = await client.post("/builder/validate", json={"slate_id":1,"platform":"draftkings"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert r.json()["data"]["valid"]

    async def test_lineups_free(self, client):
        t = await _login(client, "free@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"lineup_count":1,"strategy":"balanced"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert len(r.json()["data"]["lineups"]) == 1

    async def test_free_cannot_use_aggressive(self, client):
        t = await _login(client, "fag@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"strategy":"aggressive"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_free_max_one_lineup(self, client):
        t = await _login(client, "f1@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"lineup_count":5}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_pro_gets_20(self, client):
        t = await _login(client, "pro20@test.com"); await _promote("pro20@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"lineup_count":10,"strategy":"aggressive"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_lock_exclude_conflict_api(self, client):
        t = await _login(client, "lc@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"locked_player_ids":[1],"excluded_player_ids":[1]}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 422

    async def test_portfolios_require_pro(self, client):
        t = await _login(client, "noport@test.com")
        r = await client.post("/builder/portfolios", json={"slate_id":1,"lineup_count":5}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_portfolios_pro(self, client):
        t = await _login(client, "pport@test.com"); await _promote("pport@test.com")
        r = await client.post("/builder/portfolios", json={"slate_id":1,"lineup_count":5,"strategy":"balanced"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert r.json()["data"]["lineup_count"] == 5

    async def test_strategies_list(self, client):
        t = await _login(client, "st@test.com")
        r = await client.get("/builder/strategies", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert len(r.json()["data"]["strategies"]) == 12

    async def test_auth_required(self, client):
        r = await client.post("/builder/lineups", json={"slate_id":1})
        assert r.status_code == 401


# ── FANDUEL NBA TESTS ────────────────────────────────────────

class TestFanDuel:
    """FanDuel NBA validates against correct rules: $60k cap, 9 slots, exact positions."""

    async def test_fanduel_valid_lineup(self, client):
        t = await _login(client, "fdv@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"platform":"fanduel","strategy":"balanced"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        lineups = r.json()["data"]["lineups"]
        assert len(lineups) == 1
        assert lineups[0]["total_salary"] <= 60000

    async def test_fanduel_lineup_count(self, client):
        t = await _login(client, "fdc@test.com"); await _promote("fdc@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"platform":"fanduel","strategy":"balanced","lineup_count":3}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert len(r.json()["data"]["lineups"]) == 3

    async def test_fanduel_validate_platform(self):
        from builder.engine import BuilderValidator
        assert BuilderValidator.validate_platform("fanduel") is None

    async def test_fanduel_salary_cap_enforcement(self):
        from builder.engine import BuilderValidator
        errs = BuilderValidator.validate_roster(
            [{"salary":65000}], "fanduel", []
        )
        assert any("salar" in e.lower() for e in errs)

    async def test_fanduel_roster_size_enforcement(self):
        from builder.engine import BuilderValidator
        errs = BuilderValidator.validate_roster(
            [{"salary":1000} for _ in range(5)], "fanduel", []
        )
        assert any("9" in e for e in errs)

    async def test_fanduel_lock_exclude_conflict(self, client):
        t = await _login(client, "fdlc@test.com")
        r = await client.post("/builder/validate", json={"slate_id":1,"platform":"fanduel","locked_player_ids":[1],"excluded_player_ids":[1]}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert not r.json()["data"]["valid"]

    async def test_fanduel_portfolio(self, client):
        t = await _login(client, "fdport@test.com"); await _promote("fdport@test.com")
        r = await client.post("/builder/portfolios", json={"slate_id":1,"platform":"fanduel","strategy":"cash","lineup_count":3}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert r.json()["data"]["lineup_count"] == 3

    async def test_fanduel_free_limit(self, client):
        t = await _login(client, "fdfree@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"platform":"fanduel","lineup_count":5}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_fanduel_pro_gets_20(self, client):
        t = await _login(client, "fdpro@test.com"); await _promote("fdpro@test.com")
        r = await client.post("/builder/lineups", json={"slate_id":1,"platform":"fanduel","strategy":"aggressive","lineup_count":10}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_fanduel_invalid_sport_rejected(self):
        from builder.engine import BuilderValidator
        err = BuilderValidator.validate_sport("nfl")
        assert err is not None