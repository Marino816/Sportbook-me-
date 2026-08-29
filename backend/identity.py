"""Username rules and OAuth account-linking helpers.

Email remains the private billing / recovery identity. Username is a
public login handle stored in normalized lowercase form.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import User, UserOAuthIdentity

USERNAME_RE = re.compile(r"^[a-z0-9._]{3,24}$")
RESERVED_USERNAMES = frozenset({
    "admin", "administrator", "support", "official", "sbme", "sportbook",
    "root", "api", "null", "undefined", "help", "system",
})
INVALID_LOGIN = "Invalid username/email or password."
USERNAME_TAKEN = "That username is taken."
USERNAME_INVALID = (
    "Username must be 3–24 characters: letters, numbers, underscore, or period. No spaces."
)


def normalize_username(raw: str | None) -> str:
    return (raw or "").strip().lower()


def normalize_email(raw: str | None) -> str:
    return (raw or "").strip().lower()


def looks_like_email(raw: str) -> bool:
    return "@" in (raw or "").strip()


def validate_username(raw: str | None) -> str:
    value = normalize_username(raw)
    if not USERNAME_RE.fullmatch(value) or not re.search(r"[a-z0-9]", value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=USERNAME_INVALID)
    if value in RESERVED_USERNAMES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=USERNAME_INVALID)
    return value


def username_format_ok(raw: str | None) -> bool:
    try:
        validate_username(raw)
        return True
    except HTTPException:
        return False


async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(func.lower(User.email) == normalize_email(email)))
    return result.scalars().first()


async def find_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == normalize_username(username)))
    return result.scalars().first()


async def find_user_for_login(db: AsyncSession, identifier: str) -> Optional[User]:
    ident = (identifier or "").strip()
    if not ident:
        return None
    if looks_like_email(ident):
        return await find_user_by_email(db, ident)
    return await find_user_by_username(db, ident)


async def username_is_taken(db: AsyncSession, username: str, *, exclude_user_id: int | None = None) -> bool:
    stmt = select(User.id).where(User.username == normalize_username(username))
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def assign_username(db: AsyncSession, user: User, raw: str) -> str:
    """One-time username creation. Does not allow later edits."""
    if user.username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already set and cannot be changed.",
        )
    value = validate_username(raw)
    if await username_is_taken(db, value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=USERNAME_TAKEN)
    user.username = value
    await db.commit()
    await db.refresh(user)
    return value


async def find_oauth_identity(
    db: AsyncSession, provider: str, subject: str,
) -> Optional[UserOAuthIdentity]:
    result = await db.execute(
        select(UserOAuthIdentity).where(
            UserOAuthIdentity.provider == provider,
            UserOAuthIdentity.provider_subject == subject,
        )
    )
    return result.scalars().first()


async def resolve_oauth_account(
    db: AsyncSession,
    *,
    provider: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> tuple[User, bool]:
    """Find or create an SB ME user for a verified provider identity.

    Linking uses the durable provider subject first. A verified provider
    email may attach to an existing account. Unverified emails never merge.
    """
    existing = await find_oauth_identity(db, provider, subject)
    if existing is not None:
        user = await db.get(User, existing.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
        if email and email_verified and not existing.provider_email:
            existing.provider_email = normalize_email(email)
            await db.commit()
        return user, False

    if email and email_verified:
        matched = await find_user_by_email(db, email)
        if matched is not None:
            other = await db.execute(
                select(UserOAuthIdentity).where(
                    UserOAuthIdentity.user_id == matched.id,
                    UserOAuthIdentity.provider == provider,
                )
            )
            prior = other.scalars().first()
            if prior is not None and prior.provider_subject != subject:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This account is already linked to a different identity for that provider.",
                )
            db.add(UserOAuthIdentity(
                user_id=matched.id,
                provider=provider,
                provider_subject=subject,
                provider_email=normalize_email(email),
                created_at=datetime.now(timezone.utc),
            ))
            await db.commit()
            await db.refresh(matched)
            return matched, False

    if not email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A verified provider email is required to create an account.",
        )

    if await find_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already linked to a different identity for that provider.",
        )

    user = User(
        email=normalize_email(email),
        hashed_password=None,
        username=None,
        is_pro=False,
        is_active=True,
        role="user",
    )
    db.add(user)
    await db.flush()
    db.add(UserOAuthIdentity(
        user_id=user.id,
        provider=provider,
        provider_subject=subject,
        provider_email=normalize_email(email),
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    await db.refresh(user)
    return user, True
