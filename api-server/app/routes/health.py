from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from metrics_store import MetricsStore

from app.config import get_settings
from app.database.session import get_session
from app.schemas.user import HealthOut

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthOut)
async def health(request: Request, session: AsyncSession = Depends(get_session)):
    pg = "ok"
    rd = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        pg = "error"
    redis: Redis = request.app.state.redis
    try:
        pong = await redis.ping()
        if not pong:
            rd = "error"
    except Exception:
        rd = "error"
    status = "ok" if pg == "ok" and rd == "ok" else "degraded"
    return HealthOut(
        status=status,
        service=settings.service_name,
        instance_id=settings.instance_id,
        postgres=pg,
        redis=rd,
    )


@router.get("/metrics")
async def metrics(request: Request):
    store: MetricsStore = request.app.state.metrics
    snap = await store.snapshot()
    snap["instance_id"] = settings.instance_id
    snap["service"] = settings.service_name
    return snap
