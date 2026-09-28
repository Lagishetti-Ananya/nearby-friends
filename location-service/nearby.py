"""Nearby-friend filtering: geohash prune, then exact Haversine, then sort/page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from distance import haversine_miles
from geohash import candidate_cells, in_candidate_cells


@dataclass
class LocatedUser:
    user_id: str
    name: str
    latitude: float
    longitude: float
    updated_at: datetime
    geohash: str
    active: bool = True


@dataclass
class NearbyFriend:
    user_id: str
    name: str
    latitude: float
    longitude: float
    distance_miles: float
    updated_at: datetime
    active: bool


def select_nearby(
    origin_lat: float,
    origin_lon: float,
    origin_user_id: str,
    candidates: list[LocatedUser],
    radius_miles: float,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[NearbyFriend], int]:
    """Return (page of nearby friends sorted by distance, total matching count)."""
    cells = candidate_cells(origin_lat, origin_lon, radius_miles)
    matched: list[NearbyFriend] = []
    for cand in candidates:
        if cand.user_id == origin_user_id:
            continue
        if not cand.active:
            continue
        if not in_candidate_cells(cand.geohash, cells):
            continue
        dist = haversine_miles(origin_lat, origin_lon, cand.latitude, cand.longitude)
        if dist <= radius_miles:
            matched.append(
                NearbyFriend(
                    user_id=cand.user_id,
                    name=cand.name,
                    latitude=cand.latitude,
                    longitude=cand.longitude,
                    distance_miles=round(dist, 3),
                    updated_at=cand.updated_at if cand.updated_at.tzinfo else cand.updated_at.replace(tzinfo=timezone.utc),
                    active=True,
                )
            )
    matched.sort(key=lambda f: f.distance_miles)
    total = len(matched)
    page = max(1, page)
    start = (page - 1) * page_size
    return matched[start : start + page_size], total
