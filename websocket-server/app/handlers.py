from __future__ import annotations

from datetime import datetime, timezone

from fastapi import WebSocket

from cache import LocationCache
from geohash import candidate_cells, in_candidate_cells
from metrics_store import MetricsStore
from nearby import LocatedUser, select_nearby
from pubsub import LocationPubSub

from app.connection_manager import ConnectionManager
from app.database import SessionLocal
from app.store import append_history, friend_payload, geohash_for, is_friend, load_friend_ids, load_user


ALLOWED_EVENTS = {
    "initialize",
    "location_update",
    "subscribe_friend",
    "unsubscribe_friend",
}


def _err(message: str) -> dict:
    return {"event": "error", "message": message}


async def handle_message(
    ws: WebSocket,
    user_id: str | None,
    message: dict,
    manager: ConnectionManager,
    cache: LocationCache,
    pubsub: LocationPubSub,
    metrics: MetricsStore,
    instance_id: str,
) -> str | None:
    event = message.get("event")
    if event not in ALLOWED_EVENTS:
        await ws.send_json(_err("Unknown event"))
        return user_id

    if event == "initialize":
        return await _initialize(ws, message, manager, cache, pubsub, metrics, instance_id)

    if user_id is None:
        await ws.send_json(_err("Send initialize first"))
        return None

    if event == "location_update":
        await _location_update(ws, user_id, message, cache, pubsub, metrics)
    elif event == "subscribe_friend":
        await _subscribe(ws, user_id, message, manager, pubsub)
    elif event == "unsubscribe_friend":
        await _unsubscribe(ws, user_id, message, manager, pubsub)
    return user_id


async def _initialize(ws, message, manager, cache, pubsub, metrics, instance_id) -> str | None:
    raw_id = str(message.get("user_id", "")).strip()
    async with SessionLocal() as session:
        user = await load_user(session, raw_id)
        if user is None:
            await ws.send_json(_err("Unknown user_id"))
            return None
        friend_ids = await load_friend_ids(session, raw_id)
        friends = []
        if friend_ids:
            from sqlalchemy import select
            from app.models import User
            import uuid as uuidlib

            ids = [uuidlib.UUID(x) for x in friend_ids]
            result = await session.execute(select(User).where(User.id.in_(ids)))
            friends = [{"id": str(u.id), "name": u.name} for u in result.scalars().all()]

    previous = await manager.connect(raw_id, ws)
    if previous is not None and previous is not ws:
        try:
            await previous.send_json({"event": "error", "message": "Replaced by a new session"})
            await previous.close()
        except Exception:
            pass

    added, _ = await manager.set_subscriptions(raw_id, friend_ids)
    for fid in added:
        await pubsub.subscribe(fid)

    nearby_list = await _nearby_snapshot(raw_id, cache)
    await ws.send_json(
        {
            "event": "initialize",
            "user_id": raw_id,
            "name": user.name,
            "location_sharing_enabled": user.location_sharing_enabled,
            "nearby_radius": user.nearby_radius,
            "friends": friends,
            "nearby": nearby_list,
            "instance_id": instance_id,
        }
    )
    await metrics.incr("ws_connections_opened")
    await metrics.incr("ws_connections")
    return raw_id


async def _nearby_snapshot(user_id: str, cache: LocationCache) -> list[dict]:
    origin = await cache.get_location(user_id)
    if origin is None:
        return []
    async with SessionLocal() as session:
        user = await load_user(session, user_id)
        friend_ids = await load_friend_ids(session, user_id)
        if user is None or not friend_ids:
            return []
        from sqlalchemy import select
        from app.models import User

        import uuid as uuidlib

        ids = [uuidlib.UUID(x) for x in friend_ids]
        result = await session.execute(select(User).where(User.id.in_(ids)))
        profiles = {str(u.id): u for u in result.scalars().all()}
    locs = await cache.get_locations(friend_ids)
    located: list[LocatedUser] = []
    for fid, loc in locs.items():
        profile = profiles.get(fid)
        if profile is None or not profile.location_sharing_enabled:
            continue
        from datetime import datetime

        located.append(
            LocatedUser(
                user_id=fid,
                name=profile.name,
                latitude=float(loc["latitude"]),
                longitude=float(loc["longitude"]),
                updated_at=datetime.fromisoformat(loc["timestamp"]),
                geohash=loc.get("geohash") or geohash_for(float(loc["latitude"]), float(loc["longitude"])),
            )
        )
    page, _ = select_nearby(
        origin["latitude"],
        origin["longitude"],
        user_id,
        located,
        user.nearby_radius,
        page=1,
        page_size=20,
    )
    return [
        {
            "user_id": f.user_id,
            "name": f.name,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "distance_miles": f.distance_miles,
            "updated_at": f.updated_at.isoformat(),
            "active": True,
        }
        for f in page
    ]


async def _location_update(ws, user_id, message, cache, pubsub, metrics) -> None:
    import time

    started = time.perf_counter()
    try:
        lat = float(message["latitude"])
        lon = float(message["longitude"])
    except (KeyError, TypeError, ValueError):
        await ws.send_json(_err("latitude and longitude are required numbers"))
        await metrics.incr("location_updates_failed")
        return
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        await ws.send_json(_err("coordinates out of range"))
        await metrics.incr("location_updates_failed")
        return

    async with SessionLocal() as session:
        user = await load_user(session, user_id)
        if user is None:
            await ws.send_json(_err("Unknown user"))
            return
        if not user.location_sharing_enabled:
            await cache.delete_location(user_id)
            await pubsub.publish(user_id, {"type": "presence", "user_id": user_id, "active": False})
            await metrics.incr("pubsub_published")
            await ws.send_json({"event": "presence_update", "user_id": user_id, "active": False})
            return

    ts = datetime.now(timezone.utc)
    gh = geohash_for(lat, lon)
    await cache.set_location(user_id, lat, lon, gh, ts)
    await append_history(user_id, lat, lon)
    event = {
        "type": "location",
        "user_id": user_id,
        "name": user.name,
        "latitude": lat,
        "longitude": lon,
        "timestamp": ts.isoformat(),
        "geohash": gh,
    }
    receivers = await pubsub.publish(user_id, event)
    await metrics.incr("location_updates")
    await metrics.incr("pubsub_published")
    await metrics.incr("redis_ops", 3)
    await metrics.observe_latency("location_update", time.perf_counter() - started)
    await ws.send_json(
        {
            "event": "location_update",
            "ok": True,
            "timestamp": ts.isoformat(),
            "geohash": gh,
            "pubsub_receivers": receivers,
        }
    )


async def _subscribe(ws, user_id, message, manager, pubsub) -> None:
    friend_id = str(message.get("friend_id", "")).strip()
    async with SessionLocal() as session:
        if not await is_friend(session, user_id, friend_id):
            await ws.send_json(_err("Not friends; cannot subscribe"))
            return
    should_sub = await manager.add_subscription(user_id, friend_id)
    if should_sub:
        await pubsub.subscribe(friend_id)
    await ws.send_json({"event": "subscribe_friend", "friend_id": friend_id, "ok": True})


async def _unsubscribe(ws, user_id, message, manager, pubsub) -> None:
    friend_id = str(message.get("friend_id", "")).strip()
    should_unsub = await manager.remove_subscription(user_id, friend_id)
    if should_unsub:
        await pubsub.unsubscribe(friend_id)
    await ws.send_json({"event": "unsubscribe_friend", "friend_id": friend_id, "ok": True})


async def fanout_event(event: dict, manager: ConnectionManager, cache: LocationCache, metrics: MetricsStore) -> None:
    publisher = str(event.get("user_id", ""))
    if not publisher:
        return
    watchers = manager.local_watchers(publisher)
    if not watchers:
        return
    await metrics.incr("pubsub_received")
    if event.get("type") == "presence" and event.get("active") is False:
        for watcher in watchers:
            if watcher == publisher:
                continue
            await manager.send_json(
                watcher,
                {"event": "presence_update", "user_id": publisher, "active": False},
            )
        return

    plat = float(event["latitude"])
    plon = float(event["longitude"])
    pgh = event.get("geohash") or geohash_for(plat, plon)
    pname = event.get("name") or "Friend"
    pts = event.get("timestamp") or datetime.now(timezone.utc).isoformat()

    async with SessionLocal() as session:
        for watcher in watchers:
            if watcher == publisher:
                continue
            if not await is_friend(session, watcher, publisher):
                continue
            watcher_user = await load_user(session, watcher)
            origin = await cache.get_location(watcher)
            if watcher_user is None or origin is None:
                continue
            cells = candidate_cells(origin["latitude"], origin["longitude"], watcher_user.nearby_radius)
            if not in_candidate_cells(pgh, cells):
                await manager.send_json(
                    watcher,
                    {"event": "nearby_update", "upsert": None, "remove": publisher},
                )
                continue
            dist = None
            payload = friend_payload(
                publisher,
                pname,
                plat,
                plon,
                origin["latitude"],
                origin["longitude"],
                pts,
            )
            if payload["distance_miles"] <= watcher_user.nearby_radius:
                await manager.send_json(watcher, {"event": "nearby_update", "upsert": payload, "remove": None})
            else:
                await manager.send_json(
                    watcher,
                    {"event": "nearby_update", "upsert": None, "remove": publisher},
                )
            _ = dist
