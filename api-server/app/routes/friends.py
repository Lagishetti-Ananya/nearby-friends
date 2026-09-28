from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.schemas.user import UserOut
from app.services import friend_service

router = APIRouter(tags=["friends"])


@router.get("/users/{user_id}/friends", response_model=list[UserOut])
async def list_friends(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await friend_service.list_friends(session, user_id)


@router.post("/users/{user_id}/friends/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_friend(
    user_id: uuid.UUID,
    friend_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await friend_service.add_friend(session, user_id, friend_id)


@router.delete("/users/{user_id}/friends/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    user_id: uuid.UUID,
    friend_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await friend_service.remove_friend(session, user_id, friend_id)
