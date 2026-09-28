"""Redis Pub/Sub for location events.

Channel strategy: one logical channel per user (`user:{user_id}`).
A location update is published only on the updater's channel.

WebSocket servers subscribe to channels for friends of locally connected clients.
They do NOT subscribe to the entire user population.

This keeps fan-out proportional to (active friends of connected users),
not (all users) * (all friends).

LOCAL DEMO: Redis Pub/Sub on one node (not durable; lost if no subscriber).
PRODUCTION: sharded Pub/Sub / Redis Cluster + service discovery for channel ownership.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

LOCATION_CHANNEL_PREFIX = "user:"


def user_channel(user_id: str) -> str:
    return f"{LOCATION_CHANNEL_PREFIX}{user_id}"


class LocationPubSub:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._pubsub: PubSub | None = None

    async def publish(self, user_id: str, event: dict[str, Any]) -> int:
        payload = json.dumps(event)
        return int(await self.redis.publish(user_channel(user_id), payload))

    async def subscribe(self, user_id: str) -> None:
        pubsub = await self._ensure_pubsub()
        await pubsub.subscribe(user_channel(user_id))

    async def unsubscribe(self, user_id: str) -> None:
        if self._pubsub is None:
            return
        await self._pubsub.unsubscribe(user_channel(user_id))

    async def listen(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        pubsub = await self._ensure_pubsub()
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            try:
                event = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                continue
            await handler(event)

    async def close(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None

    async def _ensure_pubsub(self) -> PubSub:
        if self._pubsub is None:
            self._pubsub = self.redis.pubsub()
        return self._pubsub
