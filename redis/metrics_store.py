"""Shared Redis-backed counters so metrics survive multiple API/WS replicas."""

from __future__ import annotations

import time
from typing import Any

from redis.asyncio import Redis

PREFIX = "metrics:"


class MetricsStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def incr(self, name: str, amount: int = 1) -> int:
        return int(await self.redis.incrby(f"{PREFIX}{name}", amount))

    async def observe_latency(self, name: str, seconds: float) -> None:
        ms = max(0.0, seconds * 1000.0)
        key = f"{PREFIX}lat:{name}"
        await self.redis.lpush(key, f"{ms:.3f}")
        await self.redis.ltrim(key, 0, 1999)

    async def snapshot(self) -> dict[str, Any]:
        keys = [
            "http_requests",
            "location_updates",
            "location_updates_failed",
            "ws_connections",
            "ws_connections_opened",
            "ws_connections_closed",
            "redis_ops",
            "pubsub_published",
            "pubsub_received",
            "errors",
            "nearby_queries",
        ]
        pipe = self.redis.pipeline()
        for name in keys:
            pipe.get(f"{PREFIX}{name}")
        pipe.lrange(f"{PREFIX}lat:location_update", 0, 1999)
        pipe.lrange(f"{PREFIX}lat:nearby", 0, 1999)
        pipe.lrange(f"{PREFIX}lat:http", 0, 1999)
        values = await pipe.execute()
        counts = {}
        for name, raw in zip(keys, values[: len(keys)]):
            counts[name] = int(raw or 0)
        lat_update = _to_floats(values[len(keys)])
        lat_nearby = _to_floats(values[len(keys) + 1])
        lat_http = _to_floats(values[len(keys) + 2])
        return {
            "counts": counts,
            "latency_ms": {
                "location_update": _summary(lat_update),
                "nearby": _summary(lat_nearby),
                "http": _summary(lat_http),
            },
            "captured_at": time.time(),
        }


def _to_floats(raw_list: list[Any] | None) -> list[float]:
    out: list[float] = []
    for item in raw_list or []:
        try:
            text = item.decode("utf-8") if isinstance(item, bytes) else str(item)
            out.append(float(text))
        except (TypeError, ValueError):
            continue
    return out


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "avg": None, "p50": None, "p95": None, "p99": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "avg": round(sum(ordered) / len(ordered), 3),
        "p50": round(_percentile(ordered, 50) or 0.0, 3),
        "p95": round(_percentile(ordered, 95) or 0.0, 3),
        "p99": round(_percentile(ordered, 99) or 0.0, 3),
    }
