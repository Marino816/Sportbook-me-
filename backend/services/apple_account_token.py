"""Stable Apple appAccountToken binding.

Apple StoreKit 2 ``appAccountToken`` must be a UUID. Sequential ``users.id``
is not a UUID and must not be sent to Apple.

Generation
----------
``uuid.uuid4()`` is generated once per Sportbook Me user and persisted in
``apple_account_bindings``. It is random, not derived from ``users.id``.
The same UUID is reused for every subsequent purchase/restore for that user.

Storage
-------
Table ``apple_account_bindings``:
- ``user_id`` UNIQUE FK → ``users.id``
- ``token`` UNIQUE UUID string (canonical 36-char form)

Validation
----------
- Token must parse as a UUID.
- For an authenticated purchase/verify call, the token on the Apple
  transaction must equal the stored token for that JWT user.
- For App Store Server Notifications, look up ``user_id`` by token.
  If no row exists, fail closed — do not invent a user binding.

This module does not grant entitlements.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import AppleAccountBinding, User


def normalize_apple_account_token(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return None


async def get_or_create_apple_account_token(db: AsyncSession, user: User) -> str:
    """Return the stable UUID appAccountToken for this user, creating it once."""
    existing = (
        await db.execute(
            select(AppleAccountBinding).where(AppleAccountBinding.user_id == user.id)
        )
    ).scalars().first()
    if existing is not None:
        return existing.token
    token = str(uuid.uuid4())
    row = AppleAccountBinding(
        user_id=user.id,
        token=token,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return token


async def lookup_user_id_for_apple_account_token(
    db: AsyncSession, token: object,
) -> Optional[int]:
    normalized = normalize_apple_account_token(token)
    if normalized is None:
        return None
    row = (
        await db.execute(
            select(AppleAccountBinding).where(AppleAccountBinding.token == normalized)
        )
    ).scalars().first()
    return row.user_id if row is not None else None


async def apple_account_token_matches_user(
    db: AsyncSession, user: User, token: object,
) -> bool:
    normalized = normalize_apple_account_token(token)
    if normalized is None:
        return False
    stored = (
        await db.execute(
            select(AppleAccountBinding).where(AppleAccountBinding.user_id == user.id)
        )
    ).scalars().first()
    return stored is not None and stored.token == normalized
