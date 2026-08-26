"""
SB ME AI — Redis-backed rate / cost limits.

Replaces the old per-process in-memory limiter.  Limits are shared across
all gunicorn workers via Redis so one user cannot bypass caps by hitting a
different worker, and cannot drive uncontrolled LLM expense.

Tier limits are configurable via env (defaults below).  A hard backend
safety ceiling applies regardless of tier.

FAIL-CLOSED: if Redis is unreachable we cannot enforce limits safely, so
the request is rejected with 503 rather than running an unlimited LLM call.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    try:
        return int(__import__("os").getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ── Configurable limits ────────────────────────────────────────
AI_BURST_LIMIT = _int_env("AI_BURST_LIMIT", 10)            # requests / 60s per user
FREE_AI_DAILY_LIMIT = _int_env("FREE_AI_DAILY_LIMIT", 20)
PRO_AI_DAILY_LIMIT = _int_env("PRO_AI_DAILY_LIMIT", 200)
ELITE_AI_DAILY_LIMIT = _int_env("ELITE_AI_DAILY_LIMIT", 2000)
AI_HARD_DAILY_LIMIT = _int_env("AI_HARD_DAILY_LIMIT", 2000)      # hard ceiling (all tiers)
AI_DAILY_TOKEN_BUDGET = _int_env("AI_DAILY_TOKEN_BUDGET", 200_000)  # tokens/user/day


def _tier(user) -> str:
    if getattr(user, "is_pro", False):
        sub = getattr(user, "subscription", None)
        if sub is not None and getattr(sub, "plan_name", "") == "Elite Stack":
            return "elite_stack"
        return "pro_arena"
    return "free"


def _daily_limit_for(tier: str) -> int:
    return {
        "free": FREE_AI_DAILY_LIMIT,
        "pro_arena": PRO_AI_DAILY_LIMIT,
        "elite_stack": ELITE_AI_DAILY_LIMIT,
    }.get(tier, FREE_AI_DAILY_LIMIT)


def _redis():
    from providers.redis_client import get_redis_client
    client = get_redis_client()
    if client is None:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable (rate limiter offline)")
    return client


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


class RateLimiter:
    """Redis-backed per-user burst + daily + token-budget enforcement."""

    def __init__(self):
        self._redis = _redis()

    # ── Burst ──────────────────────────────────────────────────
    def _burst_key(self, user_id: int) -> str:
        return f"ai:rl:burst:{user_id}"

    # ── Daily message ──────────────────────────────────────────
    def _daily_key(self, user_id: int) -> str:
        return f"ai:rl:daily:{user_id}:{_today()}"

    # ── Token budget ───────────────────────────────────────────
    def _token_key(self, user_id: int) -> str:
        return f"ai:rl:tokens:{user_id}:{_today()}"

    def check(self, user) -> dict:
        """Enforce burst + daily + hard ceiling + token budget.

        Returns a dict of current usage/limits on success.
        Raises HTTPException(429) when any limit is exceeded.
        Raises HTTPException(503) when Redis is unavailable.
        """
        r = self._redis
        user_id = user.id
        tier = _tier(user)

        # Token budget (hard cost ceiling) — checked first.
        tokens = self._get_int(r, self._token_key(user_id))
        if tokens >= AI_DAILY_TOKEN_BUDGET:
            raise HTTPException(status_code=429, detail="Daily AI token budget reached. Please try again tomorrow.")

        # Burst
        burst_key = self._burst_key(user_id)
        burst = r.incr(burst_key)
        if burst == 1:
            r.expire(burst_key, 60)
        if burst > AI_BURST_LIMIT:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

        # Daily (tier + hard ceiling)
        daily_key = self._daily_key(user_id)
        daily = r.incr(daily_key)
        if daily == 1:
            r.expire(daily_key, 48 * 3600)
        tier_limit = _daily_limit_for(tier)
        effective_limit = min(tier_limit, AI_HARD_DAILY_LIMIT)
        if daily > effective_limit:
            raise HTTPException(status_code=429, detail=f"Daily AI message limit ({effective_limit}) reached.")

        return {
            "tier": tier,
            "burst_used": burst,
            "burst_limit": AI_BURST_LIMIT,
            "daily_used": daily,
            "daily_limit": effective_limit,
            "tokens_used": tokens,
            "token_budget": AI_DAILY_TOKEN_BUDGET,
        }

    def record_tokens(self, user, total_tokens: int) -> None:
        """Add completed request tokens to the daily budget counter (best-effort)."""
        try:
            self._redis.incrby(self._token_key(user.id), int(total_tokens or 0))
        except Exception as e:  # non-fatal; logging only
            logger.warning(f"Token accounting failed: {e}")

    @staticmethod
    def _get_int(r, key: str) -> int:
        try:
            raw = r.get(key)
            return int(raw) if raw else 0
        except Exception:
            return 0
