"""
Google / Apple OAuth architecture (not live).

Required environment (do not invent credentials; do not change production
provider secrets as part of this repair batch):

  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  GOOGLE_OAUTH_REDIRECT_URI   # e.g. https://sbmedfsai.com/api/auth/oauth/google/callback

  APPLE_OAUTH_CLIENT_ID
  APPLE_OAUTH_CLIENT_SECRET   # Apple .p8 / JWT client secret
  APPLE_OAUTH_REDIRECT_URI

Intended flow (when credentials exist):
  1. GET  /api/auth/providers          → { google.enabled, apple.enabled }
  2. GET  /api/auth/oauth/{google|apple}/start → 302 to provider
  3. GET  /api/auth/oauth/{google|apple}/callback → verify code, upsert User by
     verified email, issue SB ME JWT. Email stays private for billing/recovery.
  4. Username is a future identity column, not part of OAuth.

These start/callback routes return 501 until credentials are configured so
the UI cannot fake a successful Google/Apple login.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/auth/oauth", tags=["Authentication"])


def _google_configured() -> bool:
    return bool((os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip() and (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip())


def _apple_configured() -> bool:
    return bool((os.getenv("APPLE_OAUTH_CLIENT_ID") or "").strip() and (os.getenv("APPLE_OAUTH_CLIENT_SECRET") or "").strip())


@router.get("/google/start")
async def google_oauth_start():
    if not _google_configured():
        raise HTTPException(
            status_code=501,
            detail="Google sign-in is not configured. GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET are required.",
        )
    raise HTTPException(
        status_code=501,
        detail="Google OAuth redirect is architected but the live authorization-code exchange is not enabled yet.",
    )


@router.get("/apple/start")
async def apple_oauth_start():
    if not _apple_configured():
        raise HTTPException(
            status_code=501,
            detail="Apple sign-in is not configured. APPLE_OAUTH_CLIENT_ID / APPLE_OAUTH_CLIENT_SECRET are required.",
        )
    raise HTTPException(
        status_code=501,
        detail="Apple OAuth redirect is architected but the live authorization-code exchange is not enabled yet.",
    )


@router.get("/google/callback")
async def google_oauth_callback():
    raise HTTPException(status_code=501, detail="Google OAuth callback is not enabled.")


@router.get("/apple/callback")
async def apple_oauth_callback():
    raise HTTPException(status_code=501, detail="Apple OAuth callback is not enabled.")
