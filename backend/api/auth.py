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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.domain import User, Subscription
from models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
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

@router.post("/register", response_model=TokenResponse)
async def register(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    # Check for duplicate email
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Validate password length
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    # bcrypt has a hard limit of 72 bytes — validate based on UTF-8 byte
    # length (not character count) so multibyte passwords are measured
    # correctly, and reject early with a 422 instead of letting bcrypt
    # raise a ValueError that would otherwise surface as a 500.
    password_byte_length = len(body.password.encode("utf-8"))
    if password_byte_length > 72:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must not exceed 72 bytes when UTF-8 encoded",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_pro=False,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        plan="Starter",
        email=user.email,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()

    if user is None or not verify_password(body.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})

    # Determine plan name
    plan = "Starter"
    if user.active_subscription_id:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.id == user.active_subscription_id)
        )
        sub = sub_result.scalars().first()
        if sub:
            plan = sub.plan_name

    return TokenResponse(
        access_token=token,
        plan=plan,
        email=user.email,
        role=user.role,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return user