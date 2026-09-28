# REST API

Base URL behind Docker: `http://localhost:8080/api`

Demo simplification: callers send `user_id` in the path. There is no password. Do not treat this as production authentication.

## POST /users

Create a user.

```json
{ "name": "Riley" }
```

```json
{
  "id": "uuid",
  "name": "Riley",
  "created_at": "2026-09-28T00:00:00Z",
  "location_sharing_enabled": true,
  "nearby_radius": 5.0
}
```

## GET /users/{id}

Fetch profile.

## GET /users/{id}/friends

List friends (other `User` objects).

## POST /users/{id}/friends/{friend_id}

Add a bidirectional friendship. 204. 409 if either side is at `MAX_FRIENDS` (default 50).

## DELETE /users/{id}/friends/{friend_id}

Remove both directions. 204.

## GET /users/{id}/nearby?page=1&page_size=20

Nearby **friends** with active Redis locations inside the user’s radius.

```json
{
  "origin_user_id": "…",
  "radius_miles": 5.0,
  "page": 1,
  "page_size": 20,
  "total": 2,
  "friends": [
    {
      "user_id": "…",
      "name": "Bob",
      "latitude": 37.784,
      "longitude": -122.4094,
      "distance_miles": 0.91,
      "updated_at": "2026-09-28T00:00:00Z",
      "active": true
    }
  ],
  "redis_available": true
}
```

Requires the origin user to have a current Redis location.

## POST /users/{id}/location-sharing

```json
{ "enabled": false }
```

When `false`, the API deletes the Redis location and publishes `presence` inactive.

## POST /users/{id}/radius

```json
{ "nearby_radius": 10 }
```

Presets used by the UI: 1, 5, 10.

## GET /health

```json
{
  "status": "ok",
  "service": "api-server",
  "instance_id": "api",
  "postgres": "ok",
  "redis": "ok"
}
```

## GET /metrics

Redis-backed counters and latency summaries.

## GET /demo/users

Seeded identities for the UI.
