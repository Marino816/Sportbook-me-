"""
SB-Me AI Assistant tests.

Run isolated: pytest tests/test_assistant.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User
from assistant.engine import (
    IntentClassifier, ToolRouter, StrategyModeEngine, ResponseComposer,
    STRATEGY_MODES,
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

# ── INTENT CLASSIFIER TESTS ──────────────────────────────────

class TestIntentClassifier:
    def test_build_lineups(self):
        assert IntentClassifier.classify("build me a lineup") == "build_lineups"

    def test_injury_news(self):
        assert IntentClassifier.classify("is lebron out") == "injury_news"

    def test_matchup(self):
        assert IntentClassifier.classify("analyze the lakers matchup") == "matchup_analysis"

    def test_performance(self):
        assert IntentClassifier.classify("what is my roi") == "contest_performance"

    def test_general_fallback(self):
        assert IntentClassifier.classify("hello") == "general"

    def test_confidence(self):
        c = IntentClassifier.confidence("build_lineups", "generate my lineup")
        assert c > 0.3


# ── TOOL ROUTER TESTS ───────────────────────────────────────

class TestToolRouter:
    def test_build_routes_to_builder_coach(self):
        r = ToolRouter.route("build_lineups")
        assert "builder" in r

    def test_injury_routes_to_scout(self):
        r = ToolRouter.route("injury_news")
        assert "scout" in r

    def test_general_routes_to_mission_control(self):
        r = ToolRouter.route("general")
        assert "mission_control" in r

    def test_describe_modules(self):
        d = ToolRouter.describe_modules(["scout", "analyst"], "injury_news")
        assert "Scout" in d
        assert "Analyst" in d


# ── STRATEGY MODE TESTS ─────────────────────────────────────

class TestStrategyModes:
    def test_five_modes(self):
        assert len(STRATEGY_MODES) == 5

    def test_list_modes(self):
        modes = StrategyModeEngine.list_modes()
        assert len(modes) == 5

    def test_apply_mode_adds_note(self):
        result = StrategyModeEngine.apply_mode({"rec": "test"}, "nuclear")
        assert result["strategy_mode"] == "nuclear"
        assert "Maximum ceiling" in result["strategy_note"]


# ── RESPONSE COMPOSER TESTS ─────────────────────────────────

class TestResponseComposer:
    def test_compose_structure(self):
        r = ResponseComposer.compose("test task", "general", ["mc"], {"summary": "ok"}, "rec", 0.5, "fresh")
        assert "task" in r
        assert "modules_consulted" in r
        assert "recommendation" in r

    def test_compose_war_room(self):
        wr = ResponseComposer.compose_war_room("cash")
        assert wr["strategy_mode"] == "cash"
        assert "active_alerts" in wr


# ── API TESTS ───────────────────────────────────────────────

class TestAssistantAPI:
    async def test_chat_free(self, client):
        t = await _login(client, "acf@test.com")
        r = await client.post("/assistant/chat", json={"message":"build lineup"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert "conversation_id" in data
        assert data["response"]["intent"] == "build_lineups"

    async def test_chat_injury(self, client):
        t = await _login(client, "aci@test.com")
        r = await client.post("/assistant/chat", json={"message":"is giannis hurt"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert r.json()["data"]["response"]["intent"] == "injury_news"

    async def test_strategy_modes_free(self, client):
        t = await _login(client, "asmf@test.com")
        r = await client.get("/assistant/strategy-modes", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        modes = [m["mode"] for m in r.json()["data"]["modes"]]
        assert "nuclear" not in modes

    async def test_strategy_modes_pro(self, client):
        t = await _login(client, "asmp@test.com"); await _promote("asmp@test.com")
        r = await client.get("/assistant/strategy-modes", headers={"Authorization":f"Bearer {t}"})
        assert len(r.json()["data"]["modes"]) == 5

    async def test_set_strategy_mode(self, client):
        t = await _login(client, "asm@test.com")
        r = await client.post("/assistant/strategy-mode", json={"mode":"cash"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_war_room_free_denied(self, client):
        t = await _login(client, "awrf@test.com")
        r = await client.get("/assistant/war-room", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 403

    async def test_war_room_pro(self, client):
        t = await _login(client, "awrp@test.com"); await _promote("awrp@test.com")
        r = await client.get("/assistant/war-room", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_preferences(self, client):
        t = await _login(client, "apref@test.com")
        r = await client.post("/assistant/preferences", json={"default_sport":"nba"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_auth_required(self, client):
        r = await client.post("/assistant/chat", json={"message":"hi"})
        assert r.status_code == 401