from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from cache import LocationCache
from geohash import candidate_cells, encode
from nearby import LocatedUser, select_nearby

from app.models.entities import User
from app.services import friend_service, user_service


async def nearby_friends(
    session: AsyncSession,
    cache: LocationCache,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list, int, float, bool]:
    user = await user_service.get_user(session, user_id)
    origin = await cache.get_location(str(user_id))
    if origin is None:
        return [], 0, user.nearby_radius, True

    ids = await friend_service.friend_ids(session, user_id)
    if not ids:
        return [], 0, user.nearby_radius, True

    # Scalable path: geohash cells -> Redis sets -> intersect friends.
    cells = candidate_cells(origin["latitude"], origin["longitude"], user.nearby_radius)
    in_cells = await cache.users_in_cells(cells)
    friend_id_strs = {str(i) for i in ids}
    candidate_ids = list(in_cells & friend_id_strs)

    # If geo sets are empty (TTL/index race), fall back to friend MGET then prune.
    if not candidate_ids:
        candidate_ids = list(friend_id_strs)

    locations = await cache.get_locations(candidate_ids)
    friends_by_id: dict[str, User] = {}
    remaining = [uuid.UUID(cid) for cid in candidate_ids if cid in locations]
    if remaining:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.id.in_(remaining)))
        for row in result.scalars():
            friends_by_id[str(row.id)] = row

    located: list[LocatedUser] = []
    for fid, loc in locations.items():
        profile = friends_by_id.get(fid)
        if profile is None or not profile.location_sharing_enabled:
            continue
        ts = datetime.fromisoformat(loc["timestamp"])
        located.append(
            LocatedUser(
                user_id=fid,
                name=profile.name,
                latitude=float(loc["latitude"]),
                longitude=float(loc["longitude"]),
                updated_at=ts,
                geohash=loc.get("geohash") or encode(float(loc["latitude"]), float(loc["longitude"])),
                active=True,
            )
        )

    page_rows, total = select_nearby(
        origin["latitude"],
        origin["longitude"],
        str(user_id),
        located,
        user.nearby_radius,
        page=page,
        page_size=page_size,
    )
    return page_rows, total, user.nearby_radius, True
