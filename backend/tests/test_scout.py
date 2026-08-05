"""
SB-Me Scout tests.

Run isolated: pytest tests/test_scout.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from scout.providers.base import (
    ProviderCategory, DataFreshness, ProviderStatus, ProviderResult,
    list_providers, list_provider_statuses,
)
from scout.event_detector import EventDetector
from scout.freshness import FreshnessTracker, RefreshPipeline
from scout.models import ScoutEvent, ScoutProvider, ScoutAlert

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


# ── PROVIDER TESTS ───────────────────────────────────────────

class TestProviderAbstraction:
    """Verify the pluggable provider layer."""

    def test_all_seven_providers_registered(self):
        providers = list_providers()
        assert len(providers) == 7
        categories = set()
        for key in providers:
            cat, name = key.split(":", 1)
            categories.add(cat)
        expected = {"injury", "lineups", "schedule", "weather", "odds", "salary", "status"}
        assert categories == expected

    def test_provider_statuses_all_returned(self):
        statuses = list_provider_statuses()
        assert len(statuses) == 7
        categories = {s.category.value for s in statuses}
        assert "injury" in categories
        assert "odds" in categories
        assert "salary" in categories

    def test_provider_fetch_returns_result(self):
        from scout.providers.adapters import InjuryProvider
        import asyncio
        provider = InjuryProvider()
        result = asyncio.run(provider.fetch("nba"))
        assert result.success
        assert result.data["source"] == "demo_injury_feed"

    def test_provider_freshness_starts_unknown(self):
        from scout.providers.adapters import InjuryProvider
        provider = InjuryProvider()
        assert provider.freshness() == DataFreshness.UNKNOWN

    def test_provider_freshness_after_fetch(self):
        from scout.providers.adapters import InjuryProvider
        import asyncio
        provider = InjuryProvider()
        asyncio.run(provider.fetch("nba"))
        assert provider.freshness() == DataFreshness.FRESH

    def test_health_check_returns_true(self):
        from scout.providers.adapters import InjuryProvider
        import asyncio
        provider = InjuryProvider()
        assert asyncio.run(provider.health_check()) == True


# ── EVENT DETECTOR TESTS ────────────────────────────────────

class TestEventDetector:
    """Verify event detection and creation."""

    async def test_create_injury_event(self, setup_db):
        async with _TestSession() as db:
            detector = EventDetector(db)
            event = await detector.detect_injury_change(42, "Questionable", "Out")
            assert event is not None
            assert event.event_type == "injury_update"
            assert event.severity == "critical"
            assert event.refresh_required == True
            assert len(event.affected_entities) == 1

    async def test_create_lineup_event(self, setup_db):
        async with _TestSession() as db:
            detector = EventDetector(db)
            event = await detector.detect_lineup_change("LAL", [{"player": "LeBron"}])
            assert event.event_type == "lineup_confirmation"
            assert event.refresh_required

    async def test_create_odds_event(self, setup_db):
        async with _TestSession() as db:
            detector = EventDetector(db)
            event = await detector.detect_odds_movement(1, "spread", -4.5, -6.5)
            assert event.event_type == "odds_movement"
            assert event.severity == "warning"
            assert event.refresh_required

    async def test_duplicate_event_idempotent(self, setup_db):
        """Duplicate detection within 60 seconds should return existing."""
        async with _TestSession() as db:
            detector = EventDetector(db)
            e1 = await detector.detect_injury_change(99, "Probable", "Out")
            e2 = await detector.detect_injury_change(99, "Probable", "Out")
            # Same title + source + type → second should return first
            assert e1.event_id == e2.event_id


# ── FRESHNESS TESTS ─────────────────────────────────────────

class TestFreshness:
    """Verify freshness tracking."""

    def test_freshness_report_has_providers(self):
        report = FreshnessTracker.get_freshness_report()
        assert "providers" in report
        assert "overall_freshness" in report
        assert "stale_providers" in report
        # All providers were just synced in adapter tests, so freshness may vary
        assert len(report["providers"]) > 0

    def test_freshness_enum_values(self):
        assert DataFreshness.FRESH.value == "fresh"
        assert DataFreshness.STALE.value == "stale"
        assert DataFreshness.EXPIRED.value == "expired"


# ── REFRESH PIPELINE TESTS ──────────────────────────────────

class TestRefreshPipeline:
    """Verify refresh pipeline."""

    async def test_refresh_entities_returns_queued(self):
        result = await RefreshPipeline.refresh_projections_for_entities(
            [{"type": "player", "id": 1}], reason="test"
        )
        assert result["status"] == "queued"

    async def test_refresh_slate_returns_queued(self):
        result = await RefreshPipeline.refresh_slate(1, reason="test")
        assert result["status"] == "queued"
        assert result["slate_id"] == 1


# ── API ENDPOINT TESTS ──────────────────────────────────────

class TestScoutAPI:
    """Verify Scout API endpoints."""

    async def test_events_requires_auth(self, client):
        res = await client.get("/scout/events")
        assert res.status_code == 401

    async def test_events_with_auth(self, client):
        token = await _register_and_login(client, "scout@test.com")
        res = await client.get("/scout/events", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "events" in data
        assert "total" in data

    async def test_providers_with_auth(self, client):
        token = await _register_and_login(client, "prov@test.com")
        res = await client.get("/scout/providers", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "providers" in data
        assert len(data["providers"]) == 7

    async def test_freshness_with_auth(self, client):
        token = await _register_and_login(client, "fresh@test.com")
        res = await client.get("/scout/freshness", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "overall_freshness" in data

    async def test_refresh_with_auth(self, client):
        token = await _register_and_login(client, "refr@test.com")
        res = await client.post("/scout/refresh?sport=nba", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert "event" in data
        assert "refresh" in data

    async def test_alerts_requires_pro(self, client):
        token = await _register_and_login(client, "freealert@test.com")
        res = await client.get("/scout/alerts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    async def test_alerts_with_pro(self, client):
        token = await _register_and_login(client, "proalert@test.com")
        from sqlalchemy import select as sa_select
        from models.domain import User
        async with _TestSession() as db:
            result = await db.execute(sa_select(User).where(User.email == "proalert@test.com"))
            user = result.scalars().first()
            user.is_pro = True
            await db.commit()
        res = await client.get("/scout/alerts", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    async def test_create_alert_with_pro(self, client):
        token = await _register_and_login(client, "createalert@test.com")
        from sqlalchemy import select as sa_select
        from models.domain import User
        async with _TestSession() as db:
            result = await db.execute(sa_select(User).where(User.email == "createalert@test.com"))
            user = result.scalars().first()
            user.is_pro = True
            await db.commit()
        res = await client.post("/scout/alerts?alert_type=injury_update&sport=nba", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "created"

    async def test_event_detail_not_found(self, client):
        token = await _register_and_login(client, "detail@test.com")
        res = await client.get("/scout/events/nonexistent-id", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404


# ── DATA ENUM TESTS ─────────────────────────────────────────

class TestEnums:
    """Verify Scout enums are well-formed."""

    def test_event_types(self):
        from scout.models import ScoutEventType
        types = [e.value for e in ScoutEventType]
        assert "injury_update" in types
        assert "odds_movement" in types
        assert "manual_refresh" in types

    def test_severity_levels(self):
        from scout.models import ScoutEventSeverity
        levels = [e.value for e in ScoutEventSeverity]
        assert "info" in levels
        assert "warning" in levels
        assert "critical" in levels

    def test_provider_categories(self):
        assert ProviderCategory.INJURY.value == "injury"
        assert ProviderCategory.ODDS.value == "odds"
        assert ProviderCategory.SALARY.value == "salary"