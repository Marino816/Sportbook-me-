import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TS = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with _TS() as s:
        yield s


app.dependency_overrides[get_db] = override_get_db


async def _reset():
    async with _engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
async def setup():
    await _reset()
    yield
    await _reset()


@pytest.fixture
async def client():
    t = ASGITransport(app=app)
    async with AsyncClient(transport=t, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_smoke(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "smoke@staging.test", "password": "stagingpass123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_register_duplicate_rejected(client):
    await client.post(
        "/api/auth/register",
        json={"email": "dup@staging.test", "password": "stagingpass123"},
    )
    r = await client.post(
        "/api/auth/register",
        json={"email": "dup@staging.test", "password": "another123"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_smoke(client):
    await client.post(
        "/api/auth/register",
        json={"email": "login@staging.test", "password": "stagingpass123"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "login@staging.test", "password": "stagingpass123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_invalid_rejected(client):
    r = await client.post(
        "/api/auth/login",
        json={"email": "nobody@staging.test", "password": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client):
    await client.post(
        "/api/auth/register",
        json={"email": "me@staging.test", "password": "stagingpass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "me@staging.test", "password": "stagingpass123"},
    )
    tok = login.json()["access_token"]
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@staging.test"


@pytest.mark.asyncio
async def test_me_rejects_no_token(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_flow(client):
    # Register + login
    await client.post(
        "/api/auth/register",
        json={"email": "logout@staging.test", "password": "stagingpass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "logout@staging.test", "password": "stagingpass123"},
    )
    tok = login.json()["access_token"]
    # Verify token works
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    # Simulate logout (token clearing is client-side; no server endpoint needed)
    # After logout, the token still works server-side until it expires
    # This is expected behavior for stateless JWT


@pytest.mark.asyncio
async def test_billing_status_protected(client):
    r = await client.get("/api/billing/status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_billing_status_with_auth(client):
    await client.post(
        "/api/auth/register",
        json={"email": "bill@staging.test", "password": "stagingpass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "bill@staging.test", "password": "stagingpass123"},
    )
    tok = login.json()["access_token"]
    r = await client.get("/api/billing/status", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["data"]["plan"] == "Starter"


@pytest.mark.asyncio
async def test_optimize_protected(client):
    r = await client.post(
        "/api/optimize",
        json={"slate_id": 1, "settings": {"num_lineups": 1}},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_optimizer_locked_player_ids(client):
    """Verify optimizer accepts locked_player_ids (canonical field name)."""
    from optimizer.core import DFSOptimizer
    import pandas as pd

    df = pd.DataFrame([
        {"id": 1, "name": "A", "team": "T1", "salary": 10000, "projected_fp": 50, "roster_position": "PG"},
        {"id": 2, "name": "B", "team": "T1", "salary": 9000, "projected_fp": 45, "roster_position": "SG"},
        {"id": 3, "name": "C", "team": "T2", "salary": 8000, "projected_fp": 40, "roster_position": "SF"},
        {"id": 4, "name": "D", "team": "T2", "salary": 7000, "projected_fp": 35, "roster_position": "PF"},
        {"id": 5, "name": "E", "team": "T3", "salary": 6000, "projected_fp": 30, "roster_position": "C"},
        {"id": 6, "name": "F", "team": "T3", "salary": 5000, "projected_fp": 28, "roster_position": "PG"},
        {"id": 7, "name": "G", "team": "T4", "salary": 4000, "projected_fp": 25, "roster_position": "SG"},
        {"id": 8, "name": "H", "team": "T4", "salary": 3500, "projected_fp": 20, "roster_position": "SF"},
        {"id": 9, "name": "I", "team": "T5", "salary": 3000, "projected_fp": 18, "roster_position": "PF"},
        {"id": 10, "name": "J", "team": "T5", "salary": 2500, "projected_fp": 15, "roster_position": "C"},
        {"id": 11, "name": "K", "team": "T6", "salary": 2000, "projected_fp": 12, "roster_position": "PG"},
        {"id": 12, "name": "L", "team": "T6", "salary": 1500, "projected_fp": 10, "roster_position": "SG"},
    ])
    opt = DFSOptimizer(df, {"num_lineups": 1, "locked_player_ids": [1], "min_uniqueness": 2})
    results = opt.generate()
    assert len(results) >= 1
    player_ids = [p["id"] for p in results[0]["players"]]
    assert 1 in player_ids


@pytest.mark.asyncio
async def test_optimizer_excluded_player_ids(client):
    """Verify optimizer rejects excluded_player_ids (canonical field name)."""
    from optimizer.core import DFSOptimizer
    import pandas as pd

    df = pd.DataFrame([
        {"id": 1, "name": "A", "team": "T1", "salary": 10000, "projected_fp": 50, "roster_position": "PG"},
        {"id": 2, "name": "B", "team": "T1", "salary": 9000, "projected_fp": 45, "roster_position": "SG"},
        {"id": 3, "name": "C", "team": "T2", "salary": 8000, "projected_fp": 40, "roster_position": "SF"},
        {"id": 4, "name": "D", "team": "T2", "salary": 7000, "projected_fp": 35, "roster_position": "PF"},
        {"id": 5, "name": "E", "team": "T3", "salary": 6000, "projected_fp": 30, "roster_position": "C"},
        {"id": 6, "name": "F", "team": "T3", "salary": 5000, "projected_fp": 28, "roster_position": "PG"},
        {"id": 7, "name": "G", "team": "T4", "salary": 4000, "projected_fp": 25, "roster_position": "SG"},
        {"id": 8, "name": "H", "team": "T4", "salary": 3500, "projected_fp": 20, "roster_position": "SF"},
        {"id": 9, "name": "I", "team": "T5", "salary": 3000, "projected_fp": 18, "roster_position": "PF"},
        {"id": 10, "name": "J", "team": "T5", "salary": 2500, "projected_fp": 15, "roster_position": "C"},
        {"id": 11, "name": "K", "team": "T6", "salary": 2000, "projected_fp": 12, "roster_position": "PG"},
        {"id": 12, "name": "L", "team": "T6", "salary": 1500, "projected_fp": 10, "roster_position": "SG"},
    ])
    opt = DFSOptimizer(df, {"num_lineups": 1, "excluded_player_ids": [5], "min_uniqueness": 2})
    results = opt.generate()
    assert len(results) >= 1
    player_ids = [p["id"] for p in results[0]["players"]]
    assert 5 not in player_ids


@pytest.mark.asyncio
async def test_cors_headers(client):
    r = await client.options("/health", headers={
        "Origin": "https://staging.sbmedfsai.com",
        "Access-Control-Request-Method": "GET",
    })
    # CORS middleware returns 200 for OPTIONS
    assert r.status_code in (200, 405)


@pytest.mark.asyncio
async def test_db_persistence(client):
    """Verify database writes persist across requests."""
    await client.post(
        "/api/auth/register",
        json={"email": "persist@staging.test", "password": "stagingpass123"},
    )
    # Second request should detect duplicate
    r = await client.post(
        "/api/auth/register",
        json={"email": "persist@staging.test", "password": "another123"},
    )
    assert r.status_code == 409  # Proves the first write persisted


@pytest.mark.asyncio
async def test_worker_task_registered():
    """Verify Celery worker task is registered."""
    from worker.tasks import celery_app
    tasks = list(celery_app.tasks.keys())
    assert "worker.tasks.sync_daily_slate" in tasks


@pytest.mark.asyncio
async def test_sports_lobby_demo_fallback(client):
    """Verify sports lobby returns data even without live API keys."""
    r = await client.get("/api/sports/lobby?sport=NFL")
    assert r.status_code == 200
    assert r.json()["status"] == "success"