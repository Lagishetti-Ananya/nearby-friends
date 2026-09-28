"""Deterministic demo users, friendships, and starting locations."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg
import redis as redis_lib

sys.path.insert(0, os.environ.get("LOCATION_SERVICE_PATH", "/shared/location-service"))

DEMO_USERS = [
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Bob",
        "lat": 37.7840,
        "lon": -122.4094,
        "radius": 5.0,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "Carol",
        "lat": 37.7649,
        "lon": -122.4294,
        "radius": 5.0,
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "name": "Dave",
        "lat": 37.8044,
        "lon": -122.2711,
        "radius": 10.0,
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "name": "Eve",
        "lat": 37.3382,
        "lon": -121.8863,
        "radius": 5.0,
    },
]

# Undirected friendships (seed inserts both directions).
DEMO_FRIENDS = [
    ("Bob", "Carol"),
    ("Bob", "Dave"),
    ("Carol", "Dave"),
]


def _id(name: str) -> str:
    return next(u["id"] for u in DEMO_USERS if u["name"] == name)


def encode_geohash(lat: float, lon: float, precision: int = 5) -> str:
    from geohash import encode

    return encode(lat, lon, precision)


def seed() -> None:
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://nearby:nearby@localhost:5432/nearby_friends",
    )
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    ttl = int(os.environ.get("LOCATION_TTL_SECONDS", "600"))

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:

            # Remove Alice from existing database data.
            alice_id = "11111111-1111-1111-1111-111111111111"

            cur.execute(
                "DELETE FROM friendships WHERE user_id = %s OR friend_id = %s",
                (alice_id, alice_id),
            )

            cur.execute(
                "DELETE FROM location_history WHERE user_id = %s",
                (alice_id,),
            )

            cur.execute(
                "DELETE FROM users WHERE id = %s",
                (alice_id,),
            )

            # Seed remaining demo users.
            for user in DEMO_USERS:
                cur.execute(
                    """
                    INSERT INTO users (id, name, location_sharing_enabled, nearby_radius)
                    VALUES (%s, %s, TRUE, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET name = EXCLUDED.name,
                        nearby_radius = EXCLUDED.nearby_radius
                    """,
                    (user["id"], user["name"], user["radius"]),
                )

            # Seed friendships.
            for a, b in DEMO_FRIENDS:
                for left, right in ((a, b), (b, a)):
                    cur.execute(
                        """
                        INSERT INTO friendships (user_id, friend_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (_id(left), _id(right)),
                    )

        conn.commit()

    r = redis_lib.from_url(redis_url, decode_responses=True)

    # Remove Alice's current-location data from Redis.
    r.delete(f"loc:{alice_id}")

    now = datetime.now(timezone.utc).isoformat()

    for user in DEMO_USERS:
        gh = encode_geohash(user["lat"], user["lon"])

        payload = json.dumps(
            {
                "user_id": user["id"],
                "latitude": user["lat"],
                "longitude": user["lon"],
                "timestamp": now,
                "geohash": gh,
            }
        )

        r.set(
            f"loc:{user['id']}",
            payload,
            ex=ttl,
        )

        r.sadd(
            f"geo:{gh}",
            user["id"],
        )

        r.expire(
            f"geo:{gh}",
            ttl,
        )

    # History row for demo (analytics path, not used for nearby).
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for user in DEMO_USERS:
                cur.execute(
                    """
                    INSERT INTO location_history
                    (user_id, latitude, longitude, recorded_at)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (
                        uuid.UUID(user["id"]),
                        user["lat"],
                        user["lon"],
                    ),
                )

        conn.commit()

    print("Seeded demo users: Bob, Carol, Dave, Eve")
    print("Demo user IDs:")

    for user in DEMO_USERS:
        print(f"  {user['name']}: {user['id']}")


if __name__ == "__main__":
    seed()