from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cache import LocationCache
from metrics_store import MetricsStore

from app.config import get_settings
from app.database.session import get_session
from app.schemas.user import NearbyFriendOut, NearbyPageOut
from app.services import nearby_service

router = APIRouter(tags=["nearby"])
settings = get_settings()


@router.get("/users/{user_id}/nearby", response_model=NearbyPageOut)
async def nearby(
    user_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
):
    size = page_size or settings.nearby_page_size
    cache: LocationCache = request.app.state.location_cache
    metrics: MetricsStore = request.app.state.metrics
    started = time.perf_counter()
    redis_ok = True
    try:
        rows, total, radius, redis_ok = await nearby_service.nearby_friends(
            session, cache, user_id, page, size
        )
    except Exception:
        await metrics.incr("errors")
        raise
    await metrics.incr("nearby_queries")
    await metrics.observe_latency("nearby", time.perf_counter() - started)
    await metrics.incr("redis_ops")
    return NearbyPageOut(
        origin_user_id=user_id,
        radius_miles=radius,
        page=page,
        page_size=size,
        total=total,
        friends=[
            NearbyFriendOut(
                user_id=uuid.UUID(r.user_id),
                name=r.name,
                latitude=r.latitude,
                longitude=r.longitude,
                distance_miles=r.distance_miles,
                updated_at=r.updated_at,
                active=r.active,
            )
            for r in rows
        ],
        redis_available=redis_ok,
    )
