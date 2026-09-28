"""In-memory connection tracking for THIS WebSocket instance only.

Shared state lives in Redis/Postgres so other instances can still deliver
events via Pub/Sub. Process memory holds sockets that exist on this replica.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.sockets: dict[str, WebSocket] = {}
        self.user_friends: dict[str, set[str]] = {}
        self.watchers: dict[str, set[str]] = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, user_id: str, ws: WebSocket) -> WebSocket | None:
        """Register socket. Returns previous socket if the user reconnects."""
        async with self.lock:
            previous = self.sockets.get(user_id)
            self.sockets[user_id] = ws
            return previous

    async def disconnect(self, user_id: str, ws: WebSocket) -> list[str]:
        """Remove user if this socket is still the active one. Returns friend ids to maybe unsubscribe."""
        async with self.lock:
            if self.sockets.get(user_id) is not ws:
                return []
            self.sockets.pop(user_id, None)
            friends = self.user_friends.pop(user_id, set())
            dropped: list[str] = []
            for fid in friends:
                watchers = self.watchers.get(fid)
                if watchers:
                    watchers.discard(user_id)
                    if not watchers:
                        self.watchers.pop(fid, None)
                        dropped.append(fid)
            return dropped

    async def set_subscriptions(self, user_id: str, friend_ids: list[str]) -> tuple[list[str], list[str]]:
        """Replace the friend watch list. Returns (newly_watched, no_longer_needed)."""
        async with self.lock:
            old = self.user_friends.get(user_id, set())
            new = set(friend_ids)
            added = list(new - old)
            removed = list(old - new)
            still_needed: list[str] = []
            for fid in removed:
                watchers = self.watchers.get(fid)
                if watchers:
                    watchers.discard(user_id)
                    if not watchers:
                        self.watchers.pop(fid, None)
                        still_needed.append(fid)
            for fid in added:
                self.watchers[fid].add(user_id)
            self.user_friends[user_id] = new
            return added, still_needed

    async def add_subscription(self, user_id: str, friend_id: str) -> bool:
        """Returns True if this instance should subscribe to Redis for friend_id."""
        async with self.lock:
            self.user_friends.setdefault(user_id, set()).add(friend_id)
            was_empty = friend_id not in self.watchers or not self.watchers[friend_id]
            self.watchers[friend_id].add(user_id)
            return was_empty

    async def remove_subscription(self, user_id: str, friend_id: str) -> bool:
        """Returns True if this instance should unsubscribe from Redis for friend_id."""
        async with self.lock:
            friends = self.user_friends.get(user_id)
            if friends:
                friends.discard(friend_id)
            watchers = self.watchers.get(friend_id)
            if not watchers:
                return False
            watchers.discard(user_id)
            if not watchers:
                self.watchers.pop(friend_id, None)
                return True
            return False

    def local_watchers(self, friend_id: str) -> list[str]:
        return list(self.watchers.get(friend_id, set()))

    def local_user_ids(self) -> list[str]:
        return list(self.sockets.keys())

    async def send_json(self, user_id: str, payload: dict) -> None:
        ws = self.sockets.get(user_id)
        if ws is None:
            return
        try:
            await ws.send_json(payload)
        except Exception:
            pass
