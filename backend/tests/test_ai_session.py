"""Structured SB ME Intelligence session-state tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models.database import Base
from dfs.db import DFSSlate, DFSPlayer
from assistant.session_state import (
    ConversationContext,
    PlayerRef,
    classify_action,
    extract_player_names,
    is_optimizer_commit,
    merge_conversation_context,
    extract_slate_id,
    render_session_note,
    fill_tool_arguments,
    build_optimizer_handoff_href,
)
from assistant.tools import TOOL_HANDLERS

TEST_DB_URL = "sqlite+aiosqlite://"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _reset_db():
    async with _engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
async def setup_db():
    await _reset_db()
    yield
    await _reset_db()


def _main_start():
    # 7:10 PM Eastern (EDT) stored as UTC so SQLite naive round-trip still converts.
    return datetime(2026, 8, 29, 23, 10, tzinfo=timezone.utc)


async def _seed_slate(player_name="Yordan Alvarez", locked=False, platform="draftkings"):
    start = datetime.now(timezone.utc) - timedelta(days=2) if locked else _main_start()
    async with _TestSession() as db:
        db.add(DFSSlate(
            id=42,
            platform=platform,
            sport="MLB",
            slate_name="7:10 PM ET Main",
            start_time=start,
            status="PUBLISHED",
            player_count=1107,
        ))
        db.add(DFSPlayer(
            slate_id=42,
            provider_player_id="yordan-1",
            sbme_player_id="sgo-yordan",
            player_name=player_name,
            team="HOU",
            opponent="NYY",
            position="OF",
            salary=5800,
            eligible_positions=["OF"],
        ))
        await db.commit()


class TestParse:
    def test_extract_yordan(self):
        names = extract_player_names("Build me a lineup around YORDAN ALVAREZ")
        assert names == ["YORDAN ALVAREZ"]

    def test_classify_optimizer(self):
        assert classify_action("build me a lineup around Yordan Alvarez") == "optimizer"
        assert classify_action("Build it") == "optimizer"
        assert is_optimizer_commit("Build it")

    def test_classify_metrics(self):
        assert classify_action("SB ME metrics") == "metrics"

    def test_handoff_href_includes_lock(self):
        ctx = ConversationContext(
            sport="MLB",
            platform="draftkings",
            slate_id=42,
            locked_players=[PlayerRef(name="Yordan Alvarez")],
        )
        href = build_optimizer_handoff_href(ctx)
        assert href.startswith("/optimizer?")
        assert "sport=MLB" in href
        assert "platform=draftkings" in href
        assert "slate=42" in href
        assert "Yordan" in href

    def test_extract_slate_id(self):
        assert extract_slate_id("Use slate id 29") == 29
        assert extract_slate_id("id 42") == 42
        assert extract_slate_id("Use slate 6:40PM ET (Turbo)") is None
        assert extract_slate_id("slate 29 please") == 29


class TestMergeConversation:
    async def test_incremental_context_and_no_reask_note(self):
        await _seed_slate()
        async with _TestSession() as db:
            ctx = ConversationContext()
            ctx = await merge_conversation_context(ctx, "Build me a lineup around Yordan Alvarez", db)
            assert ctx.requested_action == "optimizer"
            assert ctx.locked_players[0].name.lower() == "yordan alvarez"
            assert ctx.missing_fields() == ["sport", "platform", "slate_id"]
            note = render_session_note(ctx)
            assert "Ask ONLY for missing" in note or "MISSING (ask only these)" in note
            assert "sport" in note

            ctx = await merge_conversation_context(ctx, "ON DRAFTKINGS", db)
            assert ctx.platform == "draftkings"
            assert ctx.sport is None
            assert ctx.locked_players[0].name.lower() == "yordan alvarez"
            assert ctx.missing_fields() == ["sport", "slate_id"]

            ctx = await merge_conversation_context(ctx, "MLB", db)
            assert ctx.sport == "MLB"
            assert ctx.platform == "draftkings"
            assert ctx.missing_fields() == ["slate_id"]
            note = render_session_note(ctx)
            assert "Do not re-ask" in note
            assert "sport = MLB" in note

            ctx = await merge_conversation_context(
                ctx, "7:10PM ET Main 12 Games – 1,107 players – UNLOCKED", db
            )
            assert ctx.slate_id == 42
            assert ctx.slate_name == "7:10 PM ET Main"
            assert ctx.slate_status == "UNLOCKED"
            assert ctx.locked_players[0].found_on_slate is True
            assert ctx.locked_players[0].player_id == "sgo-yordan"
            assert ctx.missing_fields() == []
            note = render_session_note(ctx)
            assert "MISSING: none" in note
            assert "Do not ask for sport, platform, or slate" in note

            ctx = await merge_conversation_context(ctx, "SB ME metrics", db)
            assert ctx.requested_action == "metrics"
            assert ctx.slate_id == 42
            assert ctx.sport == "MLB"
            assert "projection" in ctx.requested_metrics

            ctx = await merge_conversation_context(ctx, "Build it", db)
            assert ctx.requested_action == "optimizer"
            assert ctx.slate_id == 42
            assert ctx.platform == "draftkings"
            assert ctx.locked_players[0].name.lower().startswith("yordan")

    async def test_explicit_slate_id_persists(self):
        await _seed_slate()
        async with _TestSession() as db:
            ctx = ConversationContext(sport="MLB", platform="draftkings")
            ctx = await merge_conversation_context(ctx, "Use slate id 42", db)
            assert ctx.slate_id == 42
            href = build_optimizer_handoff_href(ctx)
            assert "slate=42" in href

    async def test_platform_change_keeps_sport_and_player(self):
        await _seed_slate()
        async with _TestSession() as db:
            ctx = ConversationContext(
                sport="MLB",
                platform="draftkings",
                slate_id=42,
                locked_players=[PlayerRef(name="Yordan Alvarez")],
            )
            ctx = await merge_conversation_context(ctx, "Actually use FanDuel", db)
            assert ctx.platform == "fanduel"
            assert ctx.sport == "MLB"
            assert ctx.locked_players[0].name == "Yordan Alvarez"
            assert ctx.salary_cap == 35000

    async def test_player_not_on_slate(self):
        await _seed_slate(player_name="Someone Else")
        async with _TestSession() as db:
            ctx = ConversationContext(
                sport="MLB",
                platform="draftkings",
                locked_players=[PlayerRef(name="Yordan Alvarez")],
            )
            ctx = await merge_conversation_context(
                ctx, "7:10 PM ET Main 12 Games", db
            )
            assert ctx.slate_id == 42
            assert ctx.locked_players[0].found_on_slate is False
            note = render_session_note(ctx)
            assert "NOT on slate" in note

    async def test_locked_slate_status(self):
        await _seed_slate(locked=True)
        async with _TestSession() as db:
            ctx = ConversationContext(sport="MLB", platform="draftkings")
            ctx = await merge_conversation_context(ctx, "7:10 PM ET Main", db)
            assert ctx.slate_status == "LOCKED"

    def test_fill_tool_args_injects_slate(self):
        ctx = ConversationContext(sport="MLB", platform="draftkings", slate_id=42)
        args = fill_tool_arguments("get_player_sb_metrics", {}, ctx)
        assert args["slate_id"] == 42
        assert args["platform"] == "draftkings"


class TestResolveAndOptimizeTools:
    async def test_resolve_found_and_missing(self):
        await _seed_slate()
        async with _TestSession() as db:
            found = await TOOL_HANDLERS["resolve_player_on_slate"](
                db, slate_id=42, player_name="Yordan Alvarez"
            )
            assert found["found"] is True
            assert found["player_id"] == "sgo-yordan"
            missing = await TOOL_HANDLERS["resolve_player_on_slate"](
                db, slate_id=42, player_name="Not A Player"
            )
            assert missing["found"] is False
            assert missing["message"] == "Not A Player is not in this selected slate."

    async def test_optimizer_locked_slate_does_not_build(self):
        await _seed_slate(locked=True)
        async with _TestSession() as db:
            result = await TOOL_HANDLERS["build_optimizer_lineup"](
                db, slate_id=42, platform="draftkings", sport="MLB",
                locked_player_ids=["Yordan Alvarez"],
            )
            assert result["can_optimize"] is False
            assert result["slate_status"] == "LOCKED"
            assert "no longer be useful" in result["note"]

    async def test_optimizer_missing_player(self):
        await _seed_slate(player_name="Someone Else")
        async with _TestSession() as db:
            result = await TOOL_HANDLERS["build_optimizer_lineup"](
                db, slate_id=42, platform="draftkings", sport="MLB",
                locked_player_ids=["Yordan Alvarez"],
            )
            assert result["ok"] is False
            assert result["message"] == "Yordan Alvarez is not in this selected slate."
