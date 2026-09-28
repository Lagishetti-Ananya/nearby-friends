from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import Friendship, User
from app.services.user_service import get_user

settings = get_settings()


async def friend_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(Friendship).where(Friendship.user_id == user_id)
    )
    return int(result.scalar_one())


async def list_friends(session: AsyncSession, user_id: uuid.UUID) -> list[User]:
    await get_user(session, user_id)
    result = await session.execute(
        select(User)
        .join(Friendship, Friendship.friend_id == User.id)
        .where(Friendship.user_id == user_id)
        .order_by(User.name)
    )
    return list(result.scalars().all())


async def friend_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.execute(select(Friendship.friend_id).where(Friendship.user_id == user_id))
    return list(result.scalars().all())


async def add_friend(session: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID) -> None:
    if user_id == friend_id:
        raise HTTPException(status_code=400, detail="Cannot friend yourself")
    await get_user(session, user_id)
    await get_user(session, friend_id)
    existing = await session.get(Friendship, (user_id, friend_id))
    if existing:
        return
    if await friend_count(session, user_id) >= settings.max_friends:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"MVP max friends is {settings.max_friends}",
        )
    if await friend_count(session, friend_id) >= settings.max_friends:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Target user is at the MVP friend cap ({settings.max_friends})",
        )
    session.add(Friendship(user_id=user_id, friend_id=friend_id))
    session.add(Friendship(user_id=friend_id, friend_id=user_id))
    await session.commit()


async def remove_friend(session: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID) -> None:
    await get_user(session, user_id)
    a = await session.get(Friendship, (user_id, friend_id))
    b = await session.get(Friendship, (friend_id, user_id))
    if a:
        await session.delete(a)
    if b:
        await session.delete(b)
    await session.commit()
