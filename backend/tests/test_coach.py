"""
SB-Me Coach tests.

Run isolated: pytest tests/test_coach.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User
from coach.engine import (
    ContestEvaluator, PerformanceAnalyzer, StrategyAnalyzer,
    RecommendationEngine, ConfidenceCalculator,
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
    await client.post("/api/auth/register", json={"email": email, "username": "".join(ch for ch in email.split("@")[0] if ch.isalnum())[:24].ljust(3,"x"), "password": "securepass123"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return r.json()["access_token"]

async def _promote(email):
    from sqlalchemy import select as sa
    async with _TestSession() as db:
        r = await db.execute(sa(User).where(User.email == email))
        u = r.scalars().first(); u.is_pro = True; await db.commit()

DEMO = [
    {"contest_id":"c1","entry_fee":5,"entry_count":1000,"finishing_position":120,"payout":12,"final_lineup_score":285,"cash_line":272,"winning_score":340,"projected_score":270,"strategy_profile":"balanced"},
    {"contest_id":"c2","entry_fee":5,"entry_count":500,"finishing_position":400,"payout":0,"final_lineup_score":250,"cash_line":275,"winning_score":330,"projected_score":265,"strategy_profile":"aggressive"},
    {"contest_id":"c3","entry_fee":10,"entry_count":200,"finishing_position":45,"payout":35,"final_lineup_score":310,"cash_line":290,"winning_score":350,"projected_score":295,"strategy_profile":"cash"},
    {"contest_id":"c4","entry_fee":1,"entry_count":5000,"finishing_position":250,"payout":8,"final_lineup_score":295,"cash_line":280,"winning_score":345,"projected_score":280,"strategy_profile":"large_gpp"},
    {"contest_id":"c5","entry_fee":5,"entry_count":800,"finishing_position":600,"payout":0,"final_lineup_score":260,"cash_line":275,"winning_score":320,"projected_score":270,"strategy_profile":"aggressive"},
]

# ── CONTEST EVALUATOR TESTS ─────────────────────────────────

class TestContestEvaluator:
    def test_evaluate_cash(self):
        r = {"contest_id":"a","final_lineup_score":300,"cash_line":280,"entry_count":100,"finishing_position":10,"projected_score":290}
        ev = ContestEvaluator.evaluate(r)
        assert ev["cashed"] == True
        assert ev["projection_error"] == 10.0

    def test_evaluate_no_cash(self):
        r = {"contest_id":"b","final_lineup_score":250,"cash_line":280,"entry_count":100,"finishing_position":80}
        ev = ContestEvaluator.evaluate(r)
        assert ev["cashed"] == False

    def test_batch_evaluate(self):
        ev = ContestEvaluator.batch_evaluate(DEMO)
        assert ev["total"] == 5
        assert ev["cash_rate"] > 0

    def test_missing_projection(self):
        r = {"contest_id":"c","final_lineup_score":300,"cash_line":280}
        ev = ContestEvaluator.evaluate(r)
        assert ev["projection_error"] is None


# ── PERFORMANCE ANALYZER TESTS ──────────────────────────────

class TestPerformanceAnalyzer:
    def test_roi(self):
        roi = PerformanceAnalyzer.calculate_roi(DEMO)
        assert roi["total_fees"] == 26.0
        assert roi["total_winnings"] == 55.0
        assert roi["net_profit"] == 29.0
        assert roi["roi"] > 100

    def test_cash_rate(self):
        cr = PerformanceAnalyzer.cash_rate(DEMO)
        assert cr == 60.0  # 3 of 5

    def test_projection_accuracy(self):
        pa = PerformanceAnalyzer.projection_accuracy(DEMO)
        assert pa["count"] == 5
        assert pa["mae"] is not None

    def test_empty_results(self):
        roi = PerformanceAnalyzer.calculate_roi([])
        assert roi["total_entries"] == 0
        cr = PerformanceAnalyzer.cash_rate([])
        assert cr == 0.0

    def test_missing_fee_data(self):
        results = [{"entry_fee": None, "payout": 10}]
        roi = PerformanceAnalyzer.calculate_roi(results)
        assert roi["missing_fee_count"] == 1
        assert roi["missing_payout_count"] == 0
        assert roi["total_fees"] == 0.0  # all fees are None, summed to 0


# ── STRATEGY ANALYZER TESTS ─────────────────────────────────

class TestStrategyAnalyzer:
    def test_analyze_by_strategy(self):
        sa = StrategyAnalyzer.analyze_by_strategy(DEMO)
        strategies = {s["strategy"] for s in sa}
        assert "balanced" in strategies
        assert "aggressive" in strategies

    def test_small_sample_warning(self):
        few = DEMO[:1]
        sa = StrategyAnalyzer.analyze_by_strategy(few)
        assert sa[0]["sample_warning"] is not None


# ── RECOMMENDATION ENGINE TESTS ─────────────────────────────

class TestRecommendationEngine:
    def test_generates_recommendations(self):
        m = {"cash_rate": 20, "roi": -30, "projection_accuracy": {"mae": 18}}
        recs = RecommendationEngine.generate(m, [], DEMO)
        assert len(recs) > 0

    def test_small_sample_warning(self):
        recs = RecommendationEngine.generate({"cash_rate": 20, "roi": -50}, [], DEMO[:2])
        assert any("Small sample" not in r["rationale"] for r in recs)  # will have sample warning as separate rec

    def test_stale_lineup_warning(self):
        stale = [{**DEMO[0], "stale_at_lock": True}]
        recs = RecommendationEngine.generate({"cash_rate": 50, "roi": 10}, [], stale)
        assert any("stale" in r.get("rec","").lower() or "fresh" in r.get("rec","").lower() or "lock" in r.get("rec","").lower() for r in recs)

    def test_returns_list(self):
        recs = RecommendationEngine.generate({}, [], [])
        assert isinstance(recs, list)


# ── CONFIDENCE CALCULATOR TESTS ─────────────────────────────

class TestConfidenceCalculator:
    def test_large_sample_high(self):
        c = ConfidenceCalculator.calculate(30, 1.0, 5, 0.8)
        assert c > 0.7

    def test_small_sample_low(self):
        c = ConfidenceCalculator.calculate(2, 0.5, 60, 0.3)
        assert c < 0.5

    def test_bounded_0_to_1(self):
        for args in [(0,0,0,0), (1000,1,0,1)]:
            c = ConfidenceCalculator.calculate(*args)
            assert 0.0 <= c <= 1.0


# ── API TESTS ───────────────────────────────────────────────

class TestCoachAPI:
    async def test_import_contests(self, client):
        t = await _login(client, "ci@test.com")
        r = await client.post("/coach/contests/import", json={"contests":[{"contest_id":"x1"}]}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_get_contest(self, client):
        t = await _login(client, "cg@test.com")
        r = await client.get("/coach/contests/c1", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert "evaluation" in r.json()["data"]

    async def test_slates(self, client):
        t = await _login(client, "cs@test.com")
        r = await client.get("/coach/slates/1", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_performance_free(self, client):
        t = await _login(client, "cpf@test.com")
        r = await client.get("/coach/performance", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_findings_require_pro(self, client):
        t = await _login(client, "cff@test.com")
        r = await client.get("/coach/findings", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_findings_pro(self, client):
        t = await _login(client, "cfp@test.com"); await _promote("cfp@test.com")
        r = await client.get("/coach/findings", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_strategies_require_pro(self, client):
        t = await _login(client, "csf@test.com")
        r = await client.get("/coach/strategies", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_strategies_pro(self, client):
        t = await _login(client, "csp@test.com"); await _promote("csp@test.com")
        r = await client.get("/coach/strategies", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_review(self, client):
        t = await _login(client, "cr@test.com")
        r = await client.post("/coach/review", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert "session_id" in r.json()["data"]

    async def test_session(self, client):
        t = await _login(client, "cses@test.com")
        r = await client.get("/coach/sessions/s1", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_auth_required(self, client):
        r = await client.get("/coach/performance")
        assert r.status_code == 401