from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cache import LocationCache
from pubsub import LocationPubSub

from app.database.session import get_session
from app.schemas.user import LocationSharingIn, RadiusIn, UserCreate, UserOut
from app.services import user_service

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserOut)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_session)):
    return await user_service.create_user(session, body.name)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await user_service.get_user(session, user_id)


@router.post("/users/{user_id}/location-sharing", response_model=UserOut)
async def set_sharing(
    user_id: uuid.UUID,
    body: LocationSharingIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.set_sharing(session, user_id, body.enabled)
    cache: LocationCache = request.app.state.location_cache
    if not body.enabled:
        await cache.delete_location(str(user_id))
        pub = LocationPubSub(request.app.state.redis)
        await pub.publish(
            str(user_id),
            {"type": "presence", "user_id": str(user_id), "active": False},
        )
        await request.app.state.metrics.incr("pubsub_published")
    return user


@router.post("/users/{user_id}/radius", response_model=UserOut)
async def set_radius(
    user_id: uuid.UUID,
    body: RadiusIn,
    session: AsyncSession = Depends(get_session),
):
    return await user_service.set_radius(session, user_id, body.nearby_radius)
