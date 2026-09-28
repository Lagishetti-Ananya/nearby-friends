import pytest
from fakeredis import FakeAsyncRedis

from cache import LocationCache
from pubsub import LocationPubSub, user_channel


@pytest.mark.asyncio
async def test_cache_set_get_and_geo():
    r = FakeAsyncRedis()
    cache = LocationCache(r, ttl_seconds=60)
    await cache.set_location("u1", 37.77, -122.42, "9q8yy")
    loc = await cache.get_location("u1")
    assert loc["latitude"] == 37.77
    members = await cache.users_in_cells(["9q8yy"])
    assert "u1" in members
    multi = await cache.get_locations(["u1", "missing"])
    assert "u1" in multi and "missing" not in multi


@pytest.mark.asyncio
async def test_ttl_delete_removes_active_location():
    r = FakeAsyncRedis()
    cache = LocationCache(r, ttl_seconds=60)
    await cache.set_location("u1", 37.77, -122.42, "9q8yy")
    await r.delete("loc:u1")
    assert await cache.get_location("u1") is None


@pytest.mark.asyncio
async def test_delete_location_clears_geo():
    r = FakeAsyncRedis()
    cache = LocationCache(r, ttl_seconds=60)
    await cache.set_location("u1", 37.77, -122.42, "9q8yy")
    await cache.delete_location("u1")
    assert "u1" not in await cache.users_in_cells(["9q8yy"])


@pytest.mark.asyncio
async def test_pubsub_channel_name_and_publish():
    r = FakeAsyncRedis()
    bus = LocationPubSub(r)
    assert user_channel("abc") == "user:abc"
    n = await bus.publish("abc", {"type": "location", "user_id": "abc"})
    assert n >= 0
