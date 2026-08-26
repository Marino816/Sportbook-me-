"""
SB ME AI canonical chat endpoint:  POST /api/ai/chat

The single server-side orchestration point used by both web and mobile.
Auth-enforced, rate-limited, tool-gated, audit-logged, provider-agnostic.

Architecture:
  Client → POST /api/ai/chat → auth → rate check → KB retrieval →
  page-context injection → LLM (tool loop) → audit → response

This endpoint replaces the old canned /assistant/chat for real AI.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User
from api.auth import get_current_user
from api.utils import wrap_data
from assistant.llm import LLMClient, LLMResult, ToolCall, get_llm
from assistant.knowledge import (
    SYSTEM_PROMPT, PRODUCT_KNOWLEDGE_VERSION,
    retrieve_knowledge, render_knowledge,
)
from assistant.tools import TOOLS, execute_tool, ALLOWED_TOOLS
from assistant.limits import RateLimiter, resolve_tier

router = APIRouter(prefix="/api/ai", tags=["SB ME AI"])
logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 20


# ── Schemas ────────────────────────────────────────────────────

class ChatHistoryItem(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    page: Optional[str] = None          # e.g. "optimizer", "parlay", "ai"
    sport: Optional[str] = None
    platform: Optional[str] = None
    slate_id: Optional[int] = None
    history: Optional[list[ChatHistoryItem]] = None


class ChatResponse(BaseModel):
    conversation_id: str
    content: str
    tools_used: list[str] = Field(default_factory=list)
    model: str = ""
    tokens_used: int = 0
    cost_estimate: float = 0.0
    kb_version: str = ""


# ── Prompt-injection guard ─────────────────────────────────────

DANGEROUS_MARKERS = [
    "</system>", "<|im_start|>", "[INST]", "system:", "### Instruction",
    "Ignore previous instructions", "Ignore all previous",
    "DAN:", "You are now",
]


def _is_injection_attempt(text: str) -> bool:
    t = text.lower()
    return any(m.lower() in t for m in DANGEROUS_MARKERS)


# ── Audit helpers ──────────────────────────────────────────────

async def _audit(
    db: AsyncSession,
    user_id: Optional[int],
    request_body: dict,
    response_body: dict,
    model_name: str,
    provider: str,
    total_tokens: int,
    cost: float,
    latency_ms: float,
    success: bool,
    error: Optional[str],
) -> None:
    """Persist an audit record to ai_chat_logs (best-effort, never fails the request)."""
    try:
        from models.ai_models import AIChatLog
        from models.database import SyncSessionLocal

        def _write_sync():
            session = SyncSessionLocal()
            try:
                record = AIChatLog(
                    user_id=user_id,
                    conversation_id=response_body.get("conversation_id"),
                    model=model_name,
                    provider=provider,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=total_tokens,
                    cost_estimate=cost,
                    tools_invoked=response_body.get("tools_used", []),
                    latency_ms=latency_ms,
                    success=success,
                    error=error,
                )
                session.add(record)
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_sync)
    except Exception as e:
        logger.warning(f"Audit log write failed (non-fatal): {e}")


# ── Page context injection ─────────────────────────────────────

def _page_context_note(req: ChatRequest) -> str:
    """Build a short contextual note from the client's page state."""
    parts = []
    if req.page:
        parts.append(f"The customer is on the {req.page} page.")
    if req.sport:
        parts.append(f"Selected sport: {req.sport.upper()}.")
    if req.platform:
        parts.append(f"Selected platform: {req.platform}.")
    if req.slate_id:
        parts.append(f"Selected slate ID: {req.slate_id}.")
    if not parts:
        return ""
    return "Page context: " + " ".join(parts)


# ── Endpoint ───────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    # 1. Injection check
    if _is_injection_attempt(body.message):
        raise HTTPException(400, "Invalid input.")

    # 2. Rate limit — resolve tier via an explicit query (never lazy-load
    #    the subscription relationship, which would raise MissingGreenlet).
    plan_name: Optional[str] = None
    if getattr(user, "is_pro", False) and getattr(user, "active_subscription_id", None):
        from models.domain import Subscription
        from sqlalchemy import select as sa_select
        r = await db.execute(
            sa_select(Subscription.plan_name).where(Subscription.id == user.active_subscription_id)
        )
        plan_name = r.scalar()
    tier = resolve_tier(getattr(user, "is_pro", False), plan_name)

    limiter = RateLimiter()
    usage = limiter.check(user.id, tier)

    # 3. LLM client
    llm = get_llm()
    if not llm.is_configured():
        raise HTTPException(503, "AI engine is not configured. Please contact support.")

    # 4. Assemble messages
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Product knowledge (retrieve relevant entries)
    kb_entries = retrieve_knowledge(body.message, limit=3)
    kb_text = render_knowledge(kb_entries)
    if kb_text:
        messages.append({"role": "system", "content": kb_text})

    # Page context
    ctx_note = _page_context_note(body)
    if ctx_note:
        messages.append({"role": "system", "content": ctx_note})

    # History (bounded)
    if body.history:
        bounded = body.history[-MAX_HISTORY_MESSAGES:]
        for h in bounded:
            if h.role in ("user", "assistant"):
                messages.append({"role": h.role, "content": h.content[:2000]})

    # User message
    messages.append({"role": "user", "content": body.message})

    # 5. Tool loop
    tools_used: list[str] = []
    total_tokens = 0
    final_content = ""
    model_used = ""
    cost_estimate = 0.0
    error_detail: Optional[str] = None
    success = True

    try:
        result: Optional[LLMResult] = None
        result = await llm.chat(messages, tools=TOOLS)

        for _ in range(MAX_TOOL_ROUNDS):
            if not result.tool_calls:
                final_content = result.content
                model_used = result.model
                total_tokens += result.total_tokens
                cost_estimate += result.cost_estimate
                break

            # Execute each allowed tool once, recording the tool message pair.
            assistant_tool_calls = []
            tool_messages = []
            for tc in result.tool_calls:
                if tc.name not in ALLOWED_TOOLS:
                    continue  # never call a tool outside the allow-list
                tools_used.append(tc.name)
                tool_result = await execute_tool(tc.name, tc.arguments, db)
                assistant_tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                })
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, default=str),
                })

            if not assistant_tool_calls:
                # No allowed tools were requested — stop with what we have.
                final_content = result.content
                model_used = result.model
                total_tokens += result.total_tokens
                cost_estimate += result.cost_estimate
                break

            messages.append({
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": assistant_tool_calls,
            })
            messages.extend(tool_messages)

            total_tokens += result.total_tokens
            cost_estimate += result.cost_estimate
            result = await llm.chat(messages, tools=TOOLS)
        else:
            # Exhausted tool rounds — use whatever the model produced last.
            final_content = result.content
            model_used = result.model
            total_tokens += result.total_tokens
            cost_estimate += result.cost_estimate

        if not final_content:
            final_content = "I couldn't find a good answer for that. Please try rephrasing."

    except Exception as e:
        success = False
        error_detail = f"{type(e).__name__}: {e}"
        final_content = "I'm having trouble answering right now. Please try again."
        logger.exception("LLM chat failed")

    latency_ms = (time.time() - t0) * 1000

    # 6. Token accounting
    if total_tokens > 0:
        limiter.record_tokens(user.id, total_tokens)

    # 7. Audit logging
    conv_id = body.conversation_id or f"conv:{hashlib.sha256(str(user.id).encode()).hexdigest()[:12]}"

    resp_body = {
        "conversation_id": conv_id,
        "tools_used": list(dict.fromkeys(tools_used)),  # deduplicated, ordered
    }
    await _audit(
        db=db,
        user_id=user.id,
        request_body={"message": body.message[:200], "page": body.page, "sport": body.sport,
                      "platform": body.platform, "slate_id": body.slate_id},
        response_body=resp_body,
        model_name=model_used,
        provider=getattr(llm, "provider", ""),
        total_tokens=total_tokens,
        cost=cost_estimate,
        latency_ms=latency_ms,
        success=success,
        error=error_detail,
    )

    return ChatResponse(
        conversation_id=conv_id,
        content=final_content,
        tools_used=list(dict.fromkeys(tools_used)),
        model=model_used,
        tokens_used=total_tokens,
        cost_estimate=cost_estimate,
        kb_version=PRODUCT_KNOWLEDGE_VERSION,
    )


# ── ESPN News endpoint ────────────────────────────────────────


class NewsResponse(BaseModel):
    count: int
    sport: Optional[str] = None
    items: list[dict]


@router.get("/news")
async def get_espn_news_endpoint(
    sport: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 15,
    freshness_hours: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return cached ESPN sports news."""
    from services.espn_news import get_news
    from main import _maybe_sync_espn
    await _maybe_sync_espn(db)
    items = await get_news(db, sport=sport, query=query, limit=min(limit, 30),
                           freshness_hours=freshness_hours)
    return wrap_data({"count": len(items), "sport": sport, "items": items})