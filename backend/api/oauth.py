"""Google and Apple OAuth (authorization-code). Live only when credentials exist."""

from __future__ import annotations  # noqa: I001

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    ALGORITHM,
    SECRET_KEY,
    apple_oauth_configured,
    google_oauth_configured,
    token_response,
)
from identity import resolve_oauth_account
from models.database import get_db

router = APIRouter(prefix="/auth/oauth", tags=["Authentication"])

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
APPLE_AUTH = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN = "https://appleid.apple.com/auth/token"
APPLE_ISSUER = "https://appleid.apple.com"
OAUTH_COOKIE = "sbme_oauth"
OAUTH_SCOPES_GOOGLE = "openid email profile"


@dataclass
class ProviderIdentity:
    provider: str
    subject: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str] = None


def frontend_app_url() -> str:
    return (
        (os.getenv("PUBLIC_APP_URL") or os.getenv("FRONTEND_URL") or "https://sbmedfsai.com")
        .split(",")[0]
        .strip()
        .rstrip("/")
    )


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def create_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def sign_oauth_state(payload: dict) -> str:
    data = dict(payload)
    data["exp"] = int(time.time()) + 600
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def read_oauth_state(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state.")


def validate_oauth_state(cookie_token: Optional[str], returned_state: Optional[str]) -> dict:
    if not cookie_token or not returned_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth state.")
    payload = read_oauth_state(cookie_token)
    if payload.get("state") != returned_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state mismatch.")
    return payload


def apple_private_key() -> str:
    raw = (os.getenv("APPLE_OAUTH_PRIVATE_KEY") or "").strip()
    return raw.replace("\\n", "\n")


def build_apple_client_secret(
    *,
    team_id: Optional[str] = None,
    client_id: Optional[str] = None,
    key_id: Optional[str] = None,
    private_key: Optional[str] = None,
    now: Optional[int] = None,
) -> str:
    """Apple requires a short-lived ES256 client-secret JWT. Not a static secret."""
    team_id = team_id or (os.getenv("APPLE_OAUTH_TEAM_ID") or "").strip()
    client_id = client_id or (os.getenv("APPLE_OAUTH_CLIENT_ID") or "").strip()
    key_id = key_id or (os.getenv("APPLE_OAUTH_KEY_ID") or "").strip()
    private_key = private_key or apple_private_key()
    issued = now if now is not None else int(time.time())
    payload = {
        "iss": team_id,
        "iat": issued,
        "exp": issued + 86400 * 180,
        "aud": APPLE_ISSUER,
        "sub": client_id,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_id})


def _http_json(url: str, data: Optional[dict] = None, method: str = "POST") -> dict:
    body = urllib.parse.urlencode(data or {}).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider token exchange failed.") from exc


def _unverified_claims(id_token: str) -> dict:
    try:
        return jwt.get_unverified_claims(id_token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identity token.") from exc


def validate_google_identity(id_token: str, *, client_id: str) -> ProviderIdentity:
    claims = _unverified_claims(id_token)
    iss = claims.get("iss")
    aud = claims.get("aud")
    sub = claims.get("sub")
    if iss not in GOOGLE_ISSUERS or aud != client_id or not sub:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google identity token was rejected.")
    email = claims.get("email")
    verified = bool(claims.get("email_verified"))
    return ProviderIdentity(
        provider="google",
        subject=str(sub),
        email=email,
        email_verified=verified,
        name=claims.get("name"),
    )


def validate_apple_identity(id_token: str, *, client_id: str, nonce: Optional[str]) -> ProviderIdentity:
    claims = _unverified_claims(id_token)
    if claims.get("iss") != APPLE_ISSUER or claims.get("aud") != client_id or not claims.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Apple identity token was rejected.")
    if nonce and claims.get("nonce") and claims.get("nonce") != nonce:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Apple nonce mismatch.")
    email = claims.get("email")
    verified = bool(claims.get("email_verified")) if "email_verified" in claims else bool(email)
    return ProviderIdentity(
        provider="apple",
        subject=str(claims["sub"]),
        email=email,
        email_verified=verified,
        name=None,
    )


def exchange_google_code(code: str, verifier: str) -> ProviderIdentity:
    client_id = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    payload = _http_json(GOOGLE_TOKEN, {
        "code": code,
        "client_id": client_id,
        "client_secret": (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip(),
        "redirect_uri": (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip(),
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    })
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google did not return an identity token.")
    return validate_google_identity(id_token, client_id=client_id)


def exchange_apple_code(code: str, nonce: Optional[str]) -> ProviderIdentity:
    client_id = (os.getenv("APPLE_OAUTH_CLIENT_ID") or "").strip()
    payload = _http_json(APPLE_TOKEN, {
        "code": code,
        "client_id": client_id,
        "client_secret": build_apple_client_secret(),
        "redirect_uri": (os.getenv("APPLE_OAUTH_REDIRECT_URI") or "").strip(),
        "grant_type": "authorization_code",
    })
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Apple did not return an identity token.")
    return validate_apple_identity(id_token, client_id=client_id, nonce=nonce)


async def _finish_redirect(db: AsyncSession, user) -> RedirectResponse:
    from api.auth import _plan_for_user
    tokens = token_response(user, await _plan_for_user(db, user))
    dest = frontend_app_url()
    needs = "1" if not user.username else "0"
    url = f"{dest}/auth/callback?token={urllib.parse.quote(tokens.access_token)}&needs_username={needs}"
    response = RedirectResponse(url, status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path="/")
    return response


def _set_state_cookie(response: RedirectResponse, signed: str) -> None:
    secure = os.getenv("NODE_ENV") == "production"
    response.set_cookie(
        OAUTH_COOKIE,
        signed,
        max_age=600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.get("/google/start")
async def google_oauth_start():
    if not google_oauth_configured():
        raise HTTPException(
            status_code=501,
            detail="Google sign-in is not configured.",
        )
    state = secrets.token_urlsafe(24)
    verifier, challenge = create_pkce_pair()
    signed = sign_oauth_state({"state": state, "verifier": verifier, "provider": "google"})
    params = {
        "client_id": (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip(),
        "redirect_uri": (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip(),
        "response_type": "code",
        "scope": OAUTH_SCOPES_GOOGLE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{GOOGLE_AUTH}?{urllib.parse.urlencode(params)}", status_code=302)
    _set_state_cookie(response, signed)
    return response


@router.get("/apple/start")
async def apple_oauth_start():
    if not apple_oauth_configured():
        raise HTTPException(
            status_code=501,
            detail="Apple sign-in is not configured.",
        )
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    signed = sign_oauth_state({"state": state, "nonce": nonce, "provider": "apple"})
    params = {
        "client_id": (os.getenv("APPLE_OAUTH_CLIENT_ID") or "").strip(),
        "redirect_uri": (os.getenv("APPLE_OAUTH_REDIRECT_URI") or "").strip(),
        "response_type": "code",
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
        "nonce": nonce,
    }
    response = RedirectResponse(f"{APPLE_AUTH}?{urllib.parse.urlencode(params)}", status_code=302)
    _set_state_cookie(response, signed)
    return response


async def _complete(db: AsyncSession, request: Request, *, provider: str, code: Optional[str], state: Optional[str]):
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code.")
    payload = validate_oauth_state(request.cookies.get(OAUTH_COOKIE), state)
    if payload.get("provider") != provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state mismatch.")
    if provider == "google":
        identity = exchange_google_code(code, payload.get("verifier") or "")
    else:
        identity = exchange_apple_code(code, payload.get("nonce"))
    user, _created = await resolve_oauth_account(
        db,
        provider=identity.provider,
        subject=identity.subject,
        email=identity.email,
        email_verified=identity.email_verified,
    )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return await _finish_redirect(db, user)


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not google_oauth_configured():
        raise HTTPException(status_code=501, detail="Google OAuth callback is not enabled.")
    return await _complete(db, request, provider="google", code=code, state=state)


@router.api_route("/apple/callback", methods=["GET", "POST"])
async def apple_oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not apple_oauth_configured():
        raise HTTPException(status_code=501, detail="Apple OAuth callback is not enabled.")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if request.method == "POST":
        form = await request.form()
        code = str(form.get("code") or code or "") or None
        state = str(form.get("state") or state or "") or None
    return await _complete(db, request, provider="apple", code=code, state=state)
