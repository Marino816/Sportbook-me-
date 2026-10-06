"""Authenticated account deletion for the current JWT user only."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from models.database import get_db
from models.domain import User
from models.schemas import DeleteAccountRequest, DeleteAccountResponse
from services.account_deletion import delete_authenticated_user_account

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Account"])


@router.delete("/account", response_model=DeleteAccountResponse)
async def delete_account(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the authenticated user's Sportbook Me account.

    The deletion target is always `user` from the Bearer token. Fields such as
    user_id or email in the JSON body are ignored (extra=ignore).
    """
    if (body.confirm or "").strip() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirmation must be DELETE",
        )

    uid = user.id
    try:
        await delete_authenticated_user_account(db, user)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        logger.exception("account_deletion_failed user_id=%s", uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed",
        )

    return DeleteAccountResponse(
        deleted=True,
        message="Your Sportbook Me account was deleted.",
    )
