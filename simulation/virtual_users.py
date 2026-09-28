"""Generate virtual users, sparse friendships, and walking locations around SF."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


SF = (37.7749, -122.4194)


@dataclass
class VirtualUser:
    user_id: str
    name: str
    lat: float
    lon: float
    radius: float = 5.0
    friends: list[str] = field(default_factory=list)


def _jitter(index: int, scale: float = 0.08) -> tuple[float, float]:
    """Spread users in a disc around SF so geohash cells differ."""
    angle = (index * 137.5) % 360
    radius = scale * math.sqrt((index % 97) / 97)
    dlat = radius * math.cos(math.radians(angle))
    dlon = radius * math.sin(math.radians(angle)) / max(0.2, math.cos(math.radians(SF[0])))
    return SF[0] + dlat, SF[1] + dlon


def make_users(n: int, avg_friends: int = 8, seed: int = 42) -> list[VirtualUser]:
    rng = random.Random(seed)
    users: list[VirtualUser] = []
    for i in range(n):
        lat, lon = _jitter(i)
        users.append(VirtualUser(user_id=f"sim-{i:06d}", name=f"Sim{i}", lat=lat, lon=lon))
    cap = min(avg_friends, max(0, n - 1))
    for i, user in enumerate(users):
        choices = list(range(n))
        choices.remove(i)
        rng.shuffle(choices)
        user.friends = [users[j].user_id for j in choices[:cap]]
    return users


def step(user: VirtualUser, rng: random.Random, delta: float = 0.002) -> None:
    user.lat += rng.uniform(-delta, delta)
    user.lon += rng.uniform(-delta, delta)
    user.lat = min(85.0, max(-85.0, user.lat))
    user.lon = min(179.0, max(-179.0, user.lon))
