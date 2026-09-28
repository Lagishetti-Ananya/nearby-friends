# WebSocket events

Connect: `ws://localhost:8080/ws`

All messages are JSON objects with an `event` field.

## Client → server

### initialize

```json
{ "event": "initialize", "user_id": "11111111-1111-1111-1111-111111111111" }
```

### location_update

```json
{ "event": "location_update", "latitude": 37.7749, "longitude": -122.4194 }
```

### subscribe_friend

```json
{ "event": "subscribe_friend", "friend_id": "22222222-2222-2222-2222-222222222222" }
```

### unsubscribe_friend

```json
{ "event": "unsubscribe_friend", "friend_id": "22222222-2222-2222-2222-222222222222" }
```

## Server → client

### initialize (ack + snapshot)

```json
{
  "event": "initialize",
  "user_id": "11111111-1111-1111-1111-111111111111",
  "name": "Alice",
  "location_sharing_enabled": true,
  "nearby_radius": 5.0,
  "friends": [{ "id": "…", "name": "Bob" }],
  "nearby": [],
  "instance_id": "ws"
}
```

### location_update (ack)

```json
{
  "event": "location_update",
  "ok": true,
  "timestamp": "2026-09-28T00:00:00+00:00",
  "geohash": "9q8yy",
  "pubsub_receivers": 1
}
```

`geohash` is a cell id, not a street address. Coordinates are not written to application logs.

### nearby_update

```json
{
  "event": "nearby_update",
  "upsert": {
    "user_id": "22222222-2222-2222-2222-222222222222",
    "name": "Bob",
    "latitude": 37.784,
    "longitude": -122.4094,
    "distance_miles": 0.91,
    "updated_at": "2026-09-28T00:00:00+00:00",
    "active": true
  },
  "remove": null
}
```

When a friend leaves the radius or cell set: `"upsert": null, "remove": "<user_id>"`.

### presence_update

```json
{ "event": "presence_update", "user_id": "22222222-2222-2222-2222-222222222222", "active": false }
```

Fired when sharing is turned off or Redis TTL expires.

### subscribe_friend / unsubscribe_friend acks

```json
{ "event": "subscribe_friend", "friend_id": "…", "ok": true }
```

### error

```json
{ "event": "error", "message": "Unknown user_id" }
```
