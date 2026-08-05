"""
SB-Me Mission Control tests.

Run isolated: pytest tests/test_mission_control.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from models.domain import User
from mission_control.engine import (
    WIDGETS, widget_payload, briefing, AlertPriority, HealthAggregator,
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

# ── WIDGET TESTS ────────────────────────────────────────────

class TestWidgetEngine:
    def test_all_12_widgets(self):
        assert len(WIDGETS) == 12

    def test_widget_payload_free(self):
        p = widget_payload("daily_briefing", "free")
        assert "widget_id" in p
        assert "sport" in p

    def test_widget_payload_pro(self):
        p = widget_payload("coach_summary", "pro_arena")
        assert "roi" in p

    def test_briefing_includes_alerts(self):
        b = briefing("pro_arena")
        assert b["critical_alerts"] == 0
        assert b["high_alerts"] == 1

    def test_free_briefing_restricts_edges(self):
        b = briefing("free")
        assert b["top_opportunity"] is None


# ── ALERT PRIORITY TESTS ────────────────────────────────────

class TestAlertPriority:
    def test_critical_events(self):
        assert AlertPriority.determine("player_ruled_out") == "critical"
        assert AlertPriority.determine("starting_change") == "critical"

    def test_high_events(self):
        assert AlertPriority.determine("odds_movement") == "high"

    def test_unknown_defaults_low(self):
        assert AlertPriority.determine("garbage_event") == "low"

    def test_ordering(self):
        alerts = [{"severity":"low"}, {"severity":"critical"}, {"severity":"high"}]
        ordered = AlertPriority.order(alerts)
        assert ordered[0]["severity"] == "critical"
        assert ordered[-1]["severity"] == "low"


# ── HEALTH TESTS ────────────────────────────────────────────

class TestHealth:
    def test_health_report(self):
        h = HealthAggregator.aggregate()
        assert "models" in h
        assert "providers" in h
        assert h["failed_providers"] == 0


# ── API TESTS ───────────────────────────────────────────────

class TestMCAPI:
    async def test_dashboard_free(self, client):
        t = await _login(client, "mcfree@test.com")
        r = await client.get("/mission-control", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        widgets = r.json()["data"]["widgets"]
        assert len(widgets) >= 4  # free gets 6

    async def test_dashboard_pro(self, client):
        t = await _login(client, "mcpro@test.com"); await _promote("mcpro@test.com")
        r = await client.get("/mission-control", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        widgets = r.json()["data"]["widgets"]
        assert len(widgets) == 12

    async def test_widget_list(self, client):
        t = await _login(client, "mcwl@test.com")
        r = await client.get("/mission-control/widgets", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert len(r.json()["data"]["widgets"]) == 12

    async def test_briefing(self, client):
        t = await _login(client, "mcb@test.com")
        r = await client.get("/mission-control/briefing", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        assert r.json()["data"]["sport"] == "nba"

    async def test_alerts(self, client):
        t = await _login(client, "mca@test.com")
        r = await client.get("/mission-control/alerts", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_system_health(self, client):
        t = await _login(client, "mch@test.com")
        r = await client.get("/mission-control/system-health", headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_preferences(self, client):
        t = await _login(client, "mcp@test.com")
        r = await client.post("/mission-control/preferences", json={"favorite_sport":"nba"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200

    async def test_auth_required(self, client):
        r = await client.get("/mission-control")
        assert r.status_code == 401