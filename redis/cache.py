"""Redis current-location cache with TTL and geohash cell indexes.

Why Redis for "now":
- Locations change every ~30s; a durable row per update would hammer Postgres.
- TTL automatically drops inactive users from discovery (default 10 minutes).
- O(1) get/set and cheap geo-cell sets for candidate pruning.

LOCAL DEMO: one Redis process.
PRODUCTION: Redis Cluster / sharded by geohash prefix or user_id via consistent hashing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

LOC_PREFIX = "loc:"
GEO_PREFIX = "geo:"
DEFAULT_GEO_PRECISION = 5


def loc_key(user_id: str) -> str:
    return f"{LOC_PREFIX}{user_id}"


def geo_key(cell: str) -> str:
    return f"{GEO_PREFIX}{cell}"


def parse_location(raw: str | bytes | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    return data


class LocationCache:
    def __init__(self, redis: Redis, ttl_seconds: int = 600, geo_precision: int = DEFAULT_GEO_PRECISION) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.geo_precision = geo_precision

    async def set_location(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
        geohash: str,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": ts.isoformat(),
            "geohash": geohash,
        }
        key = loc_key(user_id)
        previous = parse_location(await self.redis.get(key))
        pipe = self.redis.pipeline()
        pipe.set(key, json.dumps(payload), ex=self.ttl_seconds)
        if previous and previous.get("geohash") and previous["geohash"] != geohash:
            pipe.srem(geo_key(previous["geohash"]), user_id)
        pipe.sadd(geo_key(geohash), user_id)
        pipe.expire(geo_key(geohash), self.ttl_seconds)
        await pipe.execute()
        return payload

    async def get_location(self, user_id: str) -> dict[str, Any] | None:
        return parse_location(await self.redis.get(loc_key(user_id)))

    async def get_locations(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not user_ids:
            return {}
        keys = [loc_key(uid) for uid in user_ids]
        values = await self.redis.mget(keys)
        out: dict[str, dict[str, Any]] = {}
        for uid, raw in zip(user_ids, values):
            parsed = parse_location(raw)
            if parsed:
                out[uid] = parsed
        return out

    async def users_in_cells(self, cells: list[str]) -> set[str]:
        if not cells:
            return set()
        pipe = self.redis.pipeline()
        for cell in cells:
            pipe.smembers(geo_key(cell))
        results = await pipe.execute()
        users: set[str] = set()
        for members in results:
            for member in members or []:
                users.add(member.decode("utf-8") if isinstance(member, bytes) else str(member))
        return users

    async def delete_location(self, user_id: str) -> None:
        previous = parse_location(await self.redis.get(loc_key(user_id)))
        pipe = self.redis.pipeline()
        pipe.delete(loc_key(user_id))
        if previous and previous.get("geohash"):
            pipe.srem(geo_key(previous["geohash"]), user_id)
        await pipe.execute()

    async def refresh_ttl(self, user_id: str) -> bool:
        key = loc_key(user_id)
        exists = await self.redis.exists(key)
        if not exists:
            return False
        await self.redis.expire(key, self.ttl_seconds)
        loc = parse_location(await self.redis.get(key))
        if loc and loc.get("geohash"):
            await self.redis.expire(geo_key(loc["geohash"]), self.ttl_seconds)
        return True
