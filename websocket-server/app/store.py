from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from distance import haversine_miles
from geohash import encode

from app.database import SessionLocal
from app.models import Friendship, LocationHistory, User


async def load_user(session: AsyncSession, user_id: str) -> User | None:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None
    return await session.get(User, uid)


async def load_friend_ids(session: AsyncSession, user_id: str) -> list[str]:
    uid = uuid.UUID(user_id)
    result = await session.execute(select(Friendship.friend_id).where(Friendship.user_id == uid))
    return [str(x) for x in result.scalars().all()]


async def is_friend(session: AsyncSession, user_id: str, friend_id: str) -> bool:
    try:
        a = uuid.UUID(user_id)
        b = uuid.UUID(friend_id)
    except ValueError:
        return False
    row = await session.get(Friendship, (a, b))
    return row is not None


async def append_history(user_id: str, latitude: float, longitude: float) -> None:
    async with SessionLocal() as session:
        session.add(
            LocationHistory(
                user_id=uuid.UUID(user_id),
                latitude=latitude,
                longitude=longitude,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


def friend_payload(
    friend_id: str,
    name: str,
    lat: float,
    lon: float,
    origin_lat: float,
    origin_lon: float,
    updated_at: str,
) -> dict:
    return {
        "user_id": friend_id,
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "distance_miles": round(haversine_miles(origin_lat, origin_lon, lat, lon), 3),
        "updated_at": updated_at,
        "active": True,
    }


def geohash_for(lat: float, lon: float) -> str:
    return encode(lat, lon, 5)
