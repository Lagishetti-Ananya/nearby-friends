"""Consistent hashing ring for channel / Redis / WebSocket node assignment.

MVP: in-process demonstration. Production: the same idea maps user_id or
channel name onto a Redis shard or Pub/Sub partition with minimal remapping
when nodes are added or removed.
"""

from __future__ import annotations

import hashlib
from typing import Hashable


def _hash(value: str) -> int:
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest, 16)


class HashRing:
    def __init__(self, nodes: list[str] | None = None, virtual_nodes: int = 150) -> None:
        if virtual_nodes < 1:
            raise ValueError("virtual_nodes must be >= 1")
        self.virtual_nodes = virtual_nodes
        self._ring: dict[int, str] = {}
        self._sorted_keys: list[int] = []
        self._nodes: set[str] = set()
        for node in nodes or []:
            self.add_node(node)

    def add_node(self, node: str) -> None:
        if node in self._nodes:
            return
        self._nodes.add(node)
        for i in range(self.virtual_nodes):
            key = _hash(f"{node}#{i}")
            self._ring[key] = node
        self._sorted_keys = sorted(self._ring)

    def remove_node(self, node: str) -> None:
        if node not in self._nodes:
            return
        self._nodes.remove(node)
        for i in range(self.virtual_nodes):
            key = _hash(f"{node}#{i}")
            self._ring.pop(key, None)
        self._sorted_keys = sorted(self._ring)

    def get_node(self, key: Hashable) -> str | None:
        if not self._ring:
            return None
        hashed = _hash(str(key))
        for ring_key in self._sorted_keys:
            if hashed <= ring_key:
                return self._ring[ring_key]
        return self._ring[self._sorted_keys[0]]

    @property
    def nodes(self) -> list[str]:
        return sorted(self._nodes)


def remap_fraction(old: HashRing, new: HashRing, keys: list[str]) -> float:
    """Fraction of keys whose assigned node changed (0..1)."""
    if not keys:
        return 0.0
    changed = sum(1 for k in keys if old.get_node(k) != new.get_node(k))
    return changed / len(keys)
