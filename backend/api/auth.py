"""
Authentication module for Sportsbook Me DFS AI.

Provides:
  - Password hashing (bcrypt via passlib)
  - JWT token creation and verification (python-jose)
  - get_current_user dependency for protected routes
  - Registration, login, and current-user endpoints
"""

import os
from datetime import datetime, timedelta, timezone

from collections import defaultdict
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity import (
    INVALID_LOGIN,
    assign_username,
    find_user_by_email,
    find_user_for_login,
    normalize_email,
    username_format_ok,
    username_is_taken,
    validate_username,
)
from models.database import get_db
from models.domain import User, Subscription
from models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UsernameClaimRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)

# ── Configuration ───────────────────────────────────────────

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Password utilities ──────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT utilities ───────────────────────────────────────────

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── Dependency: get current user ────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from a JWT bearer token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user_id = int(raw_sub)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the admin role — returns 403 for non-admin users."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ── Endpoints ────────────────────────────────────────────────

def _password_byte_errors(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must not exceed 72 bytes when UTF-8 encoded",
        )


async def _plan_for_user(db: AsyncSession, user: User) -> str:
    plan = "Starter"
    if user.active_subscription_id:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.id == user.active_subscription_id)
        )
        sub = sub_result.scalars().first()
        if sub and sub.plan_name:
            plan = sub.plan_name
    return plan


def token_response(user: User, plan: str) -> TokenResponse:
    token = create_access_token({"sub": str(user.id), "role": user.role or "user"})
    return TokenResponse(
        access_token=token,
        plan=plan,
        email=user.email,
        role=user.role or "user",
        username=user.username,
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account. Username, email, and password are required."""
    username = validate_username(body.username)
    email = normalize_email(body.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A valid email is required")

    if await find_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    if await username_is_taken(db, username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is taken.")

    _password_byte_errors(body.password)

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(body.password),
        is_pro=False,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return token_response(user, "Starter")


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username or email + password."""
    identifier = (body.identifier or body.email or "").strip()
    user = await find_user_for_login(db, identifier)
    stored_hash = user.hashed_password if user is not None else None
    if user is None or stored_hash is None or stored_hash == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN,
        )
    if not verify_password(body.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return token_response(user, await _plan_for_user(db, user))


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current authenticated user's profile, including plan."""
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role or "user",
        is_pro=bool(user.is_pro),
        is_active=bool(user.is_active),
        created_at=user.created_at or datetime.now(timezone.utc),
        plan=await _plan_for_user(db, user),
    )


@router.post("/username", response_model=UserResponse)
async def claim_username(
    body: UsernameClaimRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """One-time username creation for existing or OAuth accounts."""
    await assign_username(db, user, body.username)
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role or "user",
        is_pro=bool(user.is_pro),
        is_active=bool(user.is_active),
        created_at=user.created_at or datetime.now(timezone.utc),
        plan=await _plan_for_user(db, user),
    )


_username_checks: dict[str, list[float]] = defaultdict(list)


@router.get("/username/available")
async def username_available(
    request: Request,
    u: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Rate-limited single-username check. Not a bulk enumeration endpoint."""
    ip = request.client.host if request.client else "unknown"
    now = time()
    hits = [t for t in _username_checks[ip] if now - t < 60]
    hits.append(now)
    _username_checks[ip] = hits
    if len(hits) > 20:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many username checks. Try again shortly.")

    if not username_format_ok(u):
        return {"available": False, "reason": "invalid"}
    taken = await username_is_taken(db, u)
    return {"available": not taken}


def google_oauth_configured() -> bool:
    return bool(
        (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
        and (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
        and (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
    )


def apple_oauth_configured() -> bool:
    return bool(
        (os.getenv("APPLE_OAUTH_CLIENT_ID") or "").strip()
        and (os.getenv("APPLE_OAUTH_TEAM_ID") or "").strip()
        and (os.getenv("APPLE_OAUTH_KEY_ID") or "").strip()
        and (os.getenv("APPLE_OAUTH_PRIVATE_KEY") or "").strip()
        and (os.getenv("APPLE_OAUTH_REDIRECT_URI") or "").strip()
    )


def _oauth_provider_status() -> dict:
    google_ready = google_oauth_configured()
    apple_ready = apple_oauth_configured()
    return {
        "google": {
            "enabled": google_ready,
            "configured": google_ready,
            "status": "ready" if google_ready else "pending",
            "reason": None if google_ready else (
                "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and "
                "GOOGLE_OAUTH_REDIRECT_URI are not configured."
            ),
        },
        "apple": {
            "enabled": apple_ready,
            "configured": apple_ready,
            "status": "ready" if apple_ready else "pending",
            "reason": None if apple_ready else (
                "APPLE_OAUTH_CLIENT_ID, APPLE_OAUTH_TEAM_ID, APPLE_OAUTH_KEY_ID, "
                "APPLE_OAUTH_PRIVATE_KEY, and APPLE_OAUTH_REDIRECT_URI are not configured."
            ),
        },
        "password": {"enabled": True, "configured": True, "status": "ready"},
        "username_login": {"enabled": True, "configured": True, "status": "ready"},
        "password_reset": {
            "enabled": False,
            "configured": False,
            "status": "pending",
            "reason": "Forgot-password mailer is not configured.",
        },
    }


@router.get("/providers")
async def auth_providers():
    """Public: which sign-in methods are actually available."""
    return _oauth_provider_status()
