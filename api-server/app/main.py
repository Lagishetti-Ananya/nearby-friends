from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from cache import LocationCache
from metrics_store import MetricsStore

from app.config import get_settings
from app.routes import demo, friends, health, nearby, users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.location_cache = LocationCache(app.state.redis, ttl_seconds=settings.location_ttl_seconds)
    app.state.metrics = MetricsStore(app.state.redis)
    yield
    await app.state.redis.aclose()


app = FastAPI(
    title="Nearby Friends API",
    description="Stateless REST API for users, friendships, and nearby discovery.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(friends.router)
app.include_router(nearby.router)
app.include_router(demo.router)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    metrics: MetricsStore | None = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        await metrics.incr("http_requests")
        await metrics.observe_latency("http", elapsed)
    response.headers["X-Instance-Id"] = settings.instance_id
    return response
