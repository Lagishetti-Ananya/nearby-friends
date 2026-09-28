from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text

from cache import LocationCache
from metrics_store import MetricsStore
from pubsub import LocationPubSub

from app.config import get_settings
from app.connection_manager import ConnectionManager
from app.database import engine
from app.handlers import fanout_event, handle_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
# Do not log coordinates.
logger = logging.getLogger("websocket-server")
settings = get_settings()
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url)
    pubsub_redis = Redis.from_url(settings.redis_url)
    expire_redis = Redis.from_url(settings.redis_url)
    app.state.redis = redis
    app.state.location_cache = LocationCache(redis, ttl_seconds=settings.location_ttl_seconds)
    app.state.metrics = MetricsStore(redis)
    app.state.pubsub = LocationPubSub(pubsub_redis)
    app.state.manager = manager
    listener = asyncio.create_task(_pubsub_loop(app))
    expiry = asyncio.create_task(_expiry_loop(expire_redis, app))
    logger.info("WebSocket server starting instance=%s", settings.instance_id)
    yield
    listener.cancel()
    expiry.cancel()
    await app.state.pubsub.close()
    await pubsub_redis.aclose()
    await expire_redis.aclose()
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="Nearby Friends WebSocket", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    pg = "ok"
    rd = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pg = "error"
    try:
        if not await app.state.redis.ping():
            rd = "error"
    except Exception:
        rd = "error"
    status = "ok" if pg == "ok" and rd == "ok" else "degraded"
    return {
        "status": status,
        "service": settings.service_name,
        "instance_id": settings.instance_id,
        "postgres": pg,
        "redis": rd,
        "local_connections": len(manager.sockets),
    }


@app.get("/metrics")
async def metrics():
    snap = await app.state.metrics.snapshot()
    snap["instance_id"] = settings.instance_id
    snap["local_connections"] = len(manager.sockets)
    return snap


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    user_id: str | None = None
    try:
        while True:
            try:
                message = await ws.receive_json()
            except ValueError:
                await ws.send_json({"event": "error", "message": "Invalid JSON"})
                continue
            if not isinstance(message, dict):
                await ws.send_json({"event": "error", "message": "JSON object required"})
                continue
            user_id = await handle_message(
                ws,
                user_id,
                message,
                manager,
                app.state.location_cache,
                app.state.pubsub,
                app.state.metrics,
                settings.instance_id,
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket error instance=%s user=%s", settings.instance_id, user_id)
        await app.state.metrics.incr("errors")
    finally:
        if user_id:
            dropped = await manager.disconnect(user_id, ws)
            for fid in dropped:
                await app.state.pubsub.unsubscribe(fid)
            await app.state.metrics.incr("ws_connections_closed")
            await app.state.metrics.incr("ws_connections", -1)


async def _pubsub_loop(app: FastAPI) -> None:
    pubsub: LocationPubSub = app.state.pubsub
    try:
        await pubsub.listen(lambda event: fanout_event(event, manager, app.state.location_cache, app.state.metrics))
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("pubsub listener crashed")
        await app.state.metrics.incr("errors")


async def _expiry_loop(redis: Redis, app: FastAPI) -> None:
    """When Redis TTL expires loc:{user_id}, notify local watchers (inactive discovery)."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("__keyevent@0__:expired")
    try:
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if not isinstance(data, str) or not data.startswith("loc:"):
                continue
            expired_user = data[4:]
            logger.info("location ttl expired user=%s", expired_user)
            await fanout_event(
                {"type": "presence", "user_id": expired_user, "active": False},
                manager,
                app.state.location_cache,
                app.state.metrics,
            )
    except asyncio.CancelledError:
        await pubsub.close()
        return
