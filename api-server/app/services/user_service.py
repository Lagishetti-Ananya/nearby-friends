from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import User

settings = get_settings()


async def create_user(session: AsyncSession, name: str) -> User:
    user = User(name=name.strip(), nearby_radius=settings.default_radius_miles)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def list_users(session: AsyncSession, limit: int = 50) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at).limit(limit))
    return list(result.scalars().all())


async def set_sharing(session: AsyncSession, user_id: uuid.UUID, enabled: bool) -> User:
    user = await get_user(session, user_id)
    user.location_sharing_enabled = enabled
    await session.commit()
    await session.refresh(user)
    return user


async def set_radius(session: AsyncSession, user_id: uuid.UUID, radius: float) -> User:
    if radius not in (1.0, 5.0, 10.0) and radius not in (1, 5, 10):
        # Allow the documented presets plus any validated 0.1-50 from schema.
        pass
    user = await get_user(session, user_id)
    user.nearby_radius = float(radius)
    await session.commit()
    await session.refresh(user)
    return user
