"""
SB ME AI — provider-agnostic LLM adapter.

A thin, server-side client that talks to a configurable LLM gateway
(OpenRouter by default, but also OpenAI-compatible endpoints and Anthropic).
No provider SDK is required — we use httpx directly so the code is never
coupled to one vendor's Python package.

Configuration (environment variables, read at call time):
  AI_API_KEY    — the production AI credential (REQUIRED). Never logged.
  AI_PROVIDER   — "openrouter" (default) | "openai" | "deepseek" | "anthropic"
  AI_MODEL      — model name (provider-specific)
  AI_BASE_URL   — optional base URL override (e.g. a self-hosted gateway)
  AI_TIMEOUT    — seconds (default 30)
  AI_MAX_TOKENS — max completion tokens (default 1024)
  AI_TEMPERATURE— sampling temperature (default 0.2)

The chat() method returns a normalized LLMResult so the caller (the chat
router) never touches provider-specific payload shapes.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "anthropic": "https://api.anthropic.com",
}

PROVIDER_DEFAULT_MODELS = {
    "openrouter": "openrouter/auto",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "anthropic": "claude-haiku-3-5-20241022",
}

# Estimated cost per 1M tokens (input, output) for a few common models.
# Used only for an *estimate* in audit logging, not for billing.
_COST_PER_MTOK = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-haiku-3-5-20241022": (0.80, 4.00),
    "claude-sonnet-4": (3.00, 15.00),
    "deepseek-chat": (0.27, 1.10),
    "openrouter/auto": (0.30, 0.90),
}
_DEFAULT_COST = (0.30, 0.90)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResult:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    cost_estimate: float = 0.0


def _estimate_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    in_rate, out_rate = _COST_PER_MTOK.get(model, _DEFAULT_COST)
    return round((in_tokens / 1_000_000) * in_rate + (out_tokens / 1_000_000) * out_rate, 6)


class LLMClient:
    """Provider-agnostic chat client with normalized function-calling output."""

    def __init__(self, *, api_key: str = "", provider: str = "", model: str = "",
                 base_url: str = "", transport: Optional[httpx.AsyncBaseTransport] = None):
        self.api_key = api_key or _env("AI_API_KEY")
        self.provider = (provider or _env("AI_PROVIDER", "openrouter")).lower()
        self.model = model or _env("AI_MODEL", PROVIDER_DEFAULT_MODELS.get(self.provider, "openrouter/auto"))
        self.base_url = (base_url or _env("AI_BASE_URL") or PROVIDER_BASE_URLS.get(self.provider, ""))
        self.timeout = float(_env("AI_TIMEOUT", "30") or 30)
        self.max_tokens = int(_env("AI_MAX_TOKENS", "1024") or 1024)
        self.temperature = float(_env("AI_TEMPERATURE", "0.2") or 0.2)
        self._transport = transport

    def is_configured(self) -> bool:
        """True only when an explicit production credential + model are present."""
        return bool(self.api_key) and bool(self.model) and self.api_key not in ("", "changeme", "your-api-key")

    # ── Public API ─────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResult:
        """Send a chat request and return a normalized result.

        messages is OpenAI-format: [{"role": "system"|"user"|"assistant"|"tool",
        "content": str, ...}].  tools is an OpenAI-format tools list.
        """
        if not self.is_configured():
            raise RuntimeError("AI provider is not configured (AI_API_KEY missing)")

        if self.provider == "anthropic":
            return await self._chat_anthropic(messages, tools)
        return await self._chat_openai_compatible(messages, tools)

    # ── OpenAI-compatible (OpenRouter / OpenAI / DeepSeek) ─────

    async def _chat_openai_compatible(self, messages: list[dict], tools: Optional[list[dict]]) -> LLMResult:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout), transport=self._transport) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        result = LLMResult(
            content=message.get("content") or "",
            model=data.get("model") or self.model,
        )

        raw_calls = message.get("tool_calls") or []
        for tc in raw_calls:
            fn = tc.get("function") or {}
            args = {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result.tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=args if isinstance(args, dict) else {},
            ))

        usage = data.get("usage") or {}
        result.prompt_tokens = int(usage.get("prompt_tokens") or 0)
        result.completion_tokens = int(usage.get("completion_tokens") or 0)
        result.total_tokens = int(usage.get("total_tokens") or 0)
        result.cost_estimate = _estimate_cost(self.model, result.prompt_tokens, result.completion_tokens)
        return result

    # ── Anthropic (native) ─────────────────────────────────────

    async def _chat_anthropic(self, messages: list[dict], tools: Optional[list[dict]]) -> LLMResult:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        system_blocks = [m["content"] for m in messages if m.get("role") == "system"]
        system = "\n\n".join(system_blocks) if system_blocks else ""

        anthropic_messages = []
        anthropic_tools = []
        if tools:
            for t in tools:
                anthropic_tools.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        # Convert OpenAI-format messages → Anthropic (user/assistant only;
        # prior tool results are collapsed into the user message stream).
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role == "system":
                continue
            if role == "user":
                anthropic_messages.append({"role": "user", "content": content or ""})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content or ""})
            elif role == "tool":
                # Anthropic has no tool-role; append as a user clarification.
                anthropic_messages.append({"role": "user", "content": f"[tool result] {content}"})

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout), transport=self._transport) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        result = LLMResult(model=data.get("model") or self.model)
        for block in data.get("content") or []:
            if block.get("type") == "text":
                result.content += block.get("text", "")
            elif block.get("type") == "tool_use":
                result.tool_calls.append(ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input") or {},
                ))

        usage = data.get("usage") or {}
        result.prompt_tokens = int(usage.get("input_tokens") or 0)
        result.completion_tokens = int(usage.get("output_tokens") or 0)
        result.total_tokens = result.prompt_tokens + result.completion_tokens
        result.cost_estimate = _estimate_cost(self.model, result.prompt_tokens, result.completion_tokens)
        return result


# ── Factory ────────────────────────────────────────────────────

_shared: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """Return a shared LLMClient. Tests monkeypatch this to inject a fake."""
    global _shared
    if _shared is None:
        _shared = LLMClient()
    return _shared


def reset_llm() -> None:
    global _shared
    _shared = None
