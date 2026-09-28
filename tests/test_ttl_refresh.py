import pytest
from fakeredis import FakeAsyncRedis

from cache import LocationCache


@pytest.mark.asyncio
async def test_refresh_ttl_on_existing_key():
    r = FakeAsyncRedis()
    cache = LocationCache(r, ttl_seconds=60)
    await cache.set_location("u1", 37.77, -122.42, "9q8yy")
    assert await cache.refresh_ttl("u1") is True
    ttl = await r.ttl("loc:u1")
    assert ttl > 0


@pytest.mark.asyncio
async def test_refresh_ttl_missing():
    r = FakeAsyncRedis()
    cache = LocationCache(r, ttl_seconds=60)
    assert await cache.refresh_ttl("nope") is False
