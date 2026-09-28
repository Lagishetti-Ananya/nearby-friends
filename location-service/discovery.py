"""Service discovery abstraction.

LOCAL MVP: static configuration (Docker Compose DNS names).
PRODUCTION: a coordination system (etcd or ZooKeeper) would hold:
  - live WebSocket instance IDs and addresses
  - Redis shard / Pub/Sub partition owners
  - health leases so dead nodes drop out of the consistent-hash ring

This module is the configuration point. The MVP does not deploy etcd/ZooKeeper.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceEndpoint:
    id: str
    host: str
    port: int
    kind: str


class StaticRegistry:
    """Compose/dev registry: operators pass node lists via env/config."""

    def __init__(self, nodes: list[ServiceEndpoint] | None = None) -> None:
        self._nodes = list(nodes or [])

    def register(self, node: ServiceEndpoint) -> None:
        self._nodes = [n for n in self._nodes if n.id != node.id] + [node]

    def unregister(self, node_id: str) -> None:
        self._nodes = [n for n in self._nodes if n.id != node_id]

    def list(self, kind: str | None = None) -> list[ServiceEndpoint]:
        if kind is None:
            return list(self._nodes)
        return [n for n in self._nodes if n.kind == kind]


def default_local_registry() -> StaticRegistry:
    return StaticRegistry(
        [
            ServiceEndpoint("ws-1", "websocket-server", 8001, "websocket"),
            ServiceEndpoint("api-1", "api-server", 8000, "api"),
            ServiceEndpoint("redis-1", "redis", 6379, "redis"),
        ]
    )
