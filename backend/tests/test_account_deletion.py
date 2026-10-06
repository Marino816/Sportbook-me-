"""Authenticated permanent account deletion."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistant.models import AssistantConversation, AssistantMessage
from models.ai_models import AIAuditLog, AIChatLog
from models.domain import Lineup, LineupHistory, Player, RevenueLog, Slate, StripeEvent, Subscription, User
from account_app import TestSession, account_app as app, reset_account_db
from api.auth import decode_access_token


async def _reset_db():
    await reset_account_db()


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


async def _register(client, email: str, password: str = "securepass123"):
    res = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _user_id(email: str) -> int:
    async with TestSession() as session:
        uid = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        return int(uid)


async def _seed_owned_and_shared(user_id: int, other_id: int) -> None:
    now = datetime.now(timezone.utc)
    async with TestSession() as session:
        session.add(Player(sport="NBA", name="Shared Star", team="BOS", active=True))
        session.add(Slate(sport="NBA", site="DraftKings", date=now, is_main_slate=True))
        await session.flush()
        slate_id = (await session.execute(select(Slate.id))).scalar_one()
        session.add(
            Lineup(
                user_id=user_id,
                slate_id=slate_id,
                projected_score=120.0,
                total_salary=50000,
                players_json=[{"id": 1, "pos": "PG"}],
            )
        )
        session.add(
            LineupHistory(
                user_id=user_id,
                sport="nba",
                platform="draftkings",
                slate_id=slate_id,
                strategy="balanced",
                player_count=8,
                total_salary=50000,
                projected_score=120.0,
                lineups_json=[],
            )
        )
        session.add(
            Subscription(
                user_id=user_id,
                stripe_subscription_id="sub_owner_retain",
                plan_name="Pro Arena",
                status="canceled",
                mrr_value=29.99,
            )
        )
        session.add(
            RevenueLog(
                user_id=user_id,
                amount=29.99,
                stripe_invoice_id="in_owner_retain",
                status="paid",
            )
        )
        session.add(StripeEvent(event_id="evt_shared_ledger", event_type="invoice.paid"))
        session.add(
            LineupHistory(
                user_id=other_id,
                sport="nba",
                platform="draftkings",
                slate_id=slate_id,
                strategy="balanced",
                player_count=8,
                total_salary=49000,
                projected_score=110.0,
                lineups_json=[],
            )
        )
        await session.execute(
            text("INSERT INTO user_oauth_identities (user_id, provider, provider_subject) VALUES (:uid, 'google', 'sub-owner')"),
            {"uid": user_id},
        )
        await session.execute(
            text("INSERT INTO billing_checkouts (user_id, checkout_reference) VALUES (:uid, 'chk-owner')"),
            {"uid": user_id},
        )
        session.add(
            AssistantConversation(
                conversation_id="conv-owner-pii",
                user_id=user_id,
                strategy_mode="balanced",
            )
        )
        session.add(
            AssistantMessage(
                conversation_id="conv-owner-pii",
                role="user",
                content="My email is owner@example.com and I play DFS.",
            )
        )
        session.add(
            AIChatLog(
                user_id=user_id,
                conversation_id="conv-owner-pii",
                model="gpt-test",
                provider="test",
                tools_invoked=["lookup owner@example.com"],
                error="tool failed for owner@example.com",
                success=False,
            )
        )
        session.add(
            AIAuditLog(
                user_id=user_id,
                action="chat",
                endpoint="/api/assistant/chat",
                input_hash="abc123hashprefix",
                response_hash="def456hashprefix",
                error="prompt contained owner@example.com",
                success=False,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_unauthenticated_deletion_rejected(client):
    res = await client.request("DELETE", "/api/account", json={"confirm": "DELETE"})
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_missing_confirm_rejected(client):
    tokens = await _register(client, "noconfirm@example.com")
    res = await client.request(
        "DELETE",
        "/api/account",
        headers=_auth(tokens["access_token"]),
        json={"confirm": "please"},
    )
    assert res.status_code == 422
    async with TestSession() as session:
        assert (await session.execute(select(func.count()).select_from(User))).scalar_one() == 1


@pytest.mark.asyncio
async def test_authenticated_user_deletes_own_account_and_records(client):
    owner = await _register(client, "owner@example.com")
    other = await _register(client, "other@example.com")
    owner_id = await _user_id("owner@example.com")
    other_id = await _user_id("other@example.com")
    await _seed_owned_and_shared(owner_id, other_id)

    res = await client.request(
        "DELETE",
        "/api/account",
        headers=_auth(owner["access_token"]),
        json={"confirm": "DELETE", "user_id": other_id, "email": "other@example.com"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] is True
    assert "deleted" in body["message"].lower()

    async with TestSession() as session:
        assert (await session.execute(select(User).where(User.id == owner_id))).scalar_one_or_none() is None
        remaining = (await session.execute(select(User).where(User.id == other_id))).scalar_one()
        assert remaining.email == "other@example.com"
        assert (await session.execute(select(Lineup).where(Lineup.user_id == owner_id))).scalars().first() is None
        assert (
            await session.execute(select(LineupHistory).where(LineupHistory.user_id == owner_id))
        ).scalars().first() is None
        other_history = (
            await session.execute(select(LineupHistory).where(LineupHistory.user_id == other_id))
        ).scalar_one()
        assert other_history.player_count == 8
        player = (await session.execute(select(Player))).scalar_one()
        assert player.name == "Shared Star"
        stripe_evt = (
            await session.execute(select(StripeEvent).where(StripeEvent.event_id == "evt_shared_ledger"))
        ).scalar_one()
        assert stripe_evt.event_type == "invoice.paid"
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == "sub_owner_retain")
            )
        ).scalar_one()
        assert sub.user_id is None
        rev = (
            await session.execute(select(RevenueLog).where(RevenueLog.stripe_invoice_id == "in_owner_retain"))
        ).scalar_one()
        assert rev.user_id is None
        oauth_left = (await session.execute(text("SELECT COUNT(*) FROM user_oauth_identities"))).scalar_one()
        assert oauth_left == 0
        checkout_uid = (
            await session.execute(
                text("SELECT user_id FROM billing_checkouts WHERE checkout_reference = 'chk-owner'")
            )
        ).scalar_one()
        assert checkout_uid is None
        assert (
            await session.execute(
                select(AssistantMessage).where(AssistantMessage.conversation_id == "conv-owner-pii")
            )
        ).scalars().first() is None
        assert (
            await session.execute(select(AIChatLog).where(AIChatLog.conversation_id == "conv-owner-pii"))
        ).scalars().first() is None
        audit = (
            await session.execute(
                select(AIAuditLog).where(AIAuditLog.input_hash == "abc123hashprefix")
            )
        ).scalar_one()
        assert audit.user_id is None
        assert audit.error is None
        assert audit.endpoint == "/api/assistant/chat"


@pytest.mark.asyncio
async def test_deleted_credentials_cannot_authenticate(client):
    tokens = await _register(client, "gone@example.com")
    token = tokens["access_token"]
    uid = await _user_id("gone@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)

    res = await client.request(
        "DELETE",
        "/api/account",
        headers=_auth(token),
        json={"confirm": "DELETE"},
    )
    assert res.status_code == 200

    still_signed = decode_access_token(token)
    assert still_signed["sub"] == str(uid)

    me = await client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 401
    billing = await client.get("/api/billing/status", headers=_auth(token))
    assert billing.status_code == 401
    login = await client.post(
        "/api/auth/login",
        json={"email": "gone@example.com", "password": "securepass123"},
    )
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_no_idor_path_and_other_user_login_still_works(client):
    owner = await _register(client, "alpha@example.com")
    other = await _register(client, "beta@example.com")
    owner_id = await _user_id("alpha@example.com")

    missing = await client.request(
        "DELETE",
        f"/api/account/{owner_id}",
        headers=_auth(owner["access_token"]),
        json={"confirm": "DELETE"},
    )
    assert missing.status_code in (404, 405, 422)

    res = await client.request(
        "DELETE",
        "/api/account",
        headers=_auth(owner["access_token"]),
        json={"confirm": "DELETE"},
    )
    assert res.status_code == 200
    login = await client.post(
        "/api/auth/login",
        json={"email": "beta@example.com", "password": "securepass123"},
    )
    assert login.status_code == 200
    me = await client.get("/api/auth/me", headers=_auth(other["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "beta@example.com"
