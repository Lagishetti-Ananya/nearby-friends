# Nearby Friends — Architecture

## 1. Problem

People want to know which **friends** are physically nearby **right now**, without scanning the entire user base, without exposing location to strangers, and without treating rapidly changing coordinates as durable source-of-truth data.

## 2. Functional requirements

- Share current location (opt-in)
- See nearby friends, distance, last-updated time
- Near-real-time updates over WebSockets
- Add / remove friends
- Configurable nearby radius (1 / 5 / 10 miles)
- Location sharing on/off
- Drop inactive users from discovery after TTL (default 10 minutes)
- Map view of nearby friends

## 3. Non-functional requirements

- Horizontal scale for API and WebSocket tiers
- Low latency over strong consistency for *current* location
- Privacy: location only to friends, and only while sharing is on
- Eventual consistency of a few seconds is acceptable
- Observability of update rate, Pub/Sub, connections, latency

## 4. Scale assumptions (from the system-design spec)

These are **design targets**, not local demo capacity:

| Assumption | Value |
| --- | --- |
| Total users | ~1 billion |
| Nearby-friends feature users | ~10% |
| Concurrent users | ~10 million |
| Average friends / user | ~400 |
| Example radius | 5 miles (configurable) |
| Location refresh | ~30 seconds |
| Location updates / sec | ~334,000 |
| Nearby list page size | ~20 |

## 5. High-level architecture

```
CLIENTS
   |
   v
LOAD BALANCER
   |
   +---------------------+
   |                     |
   v                     v
REST API SERVERS     WEBSOCKET SERVERS
   |                     |
   v                     v
USER DATABASE        REDIS LOCATION CACHE
                         |
                         v
                    REDIS PUB/SUB
                         |
                         v
                 OTHER WEBSOCKET SERVERS
                         |
                         v
                      CLIENTS

LOCATION HISTORY DATABASE  <--- written on each accepted location_update
```

Separation of concerns:

| Concern | Store / component |
| --- | --- |
| User / friendship data | PostgreSQL |
| Current location | Redis + TTL |
| Historical location | PostgreSQL `location_history` |
| Real-time communication | WebSocket servers |
| Messaging between instances | Redis Pub/Sub |

## 6. Location update flow

1. Client sends `location_update` on an existing WebSocket.
2. Load balancer (nginx in the MVP) routes to a WebSocket replica (`INSTANCE_ID` in logs/headers).
3. Server checks `location_sharing_enabled`. If off, active cache is deleted and a `presence` event is published.
4. Current location is written to Redis (`loc:{user_id}`) with TTL; geohash cell set is updated.
5. A history row is appended (not used for nearby lookup).
6. An event is published on `user:{user_id}`.
7. **Only** WebSocket processes that subscribed to that channel (because a locally connected client is friends with the updater) receive it.
8. Each replica filters: still friends? sharing on? in geohash candidate cells? Haversine ≤ subscriber radius?
9. Matching subscribers receive `nearby_update`. Others get `remove` so markers disappear when someone walks out of range.

## 7. Client initialization flow

1. Demo identity is selected (hackathon-safe; **not** production auth).
2. REST: profile, friends, nearby page.
3. WebSocket connect → `initialize` with `user_id`.
4. Server loads friends, **subscribes this replica** to `user:{friend_id}` channels.
5. Server returns nearby snapshot (geohash + Haversine, page size 20).
6. Client starts periodic `location_update` (UI uses 5s so the demo is visible; production assumption is ~30s).

## 8. Data model

**users:** `id`, `name`, `created_at`, `location_sharing_enabled`, `nearby_radius`

**friendships:** bidirectional rows `(user_id, friend_id)` so “list friends” is a single indexed query. Production can still shard by `user_id`.

**location_history:** `user_id`, `latitude`, `longitude`, `recorded_at`

Current location is **not** a Postgres row. History is for analytics / “where were they”, nearby uses Redis.

## 9. Redis cache

- Key `loc:{user_id}` → JSON `{latitude, longitude, timestamp, geohash}`
- TTL default 600s; every valid update refreshes TTL
- Set `geo:{geohash}` of user IDs for candidate pruning
- Expired keys disappear from nearby results; keyspace notifications emit `presence_update` on this replica set

Why Redis: high write rate, TTL as inactivity, cheap get/mget, no need for durable transactions on “now”.

## 10. Pub/Sub

Logical channel per user: `user:{user_id}`.

Do **not** broadcast every update to every user. Fan-out is “friends of currently connected clients on this replica”, then geographic + radius filters.

## 11. WebSockets

Events: `initialize`, `location_update`, `subscribe_friend`, `unsubscribe_friend`, `nearby_update`, `presence_update`.

Sockets live in process memory (unavoidable). Shared truth is Redis + Postgres. Pub/Sub is how replica B learns about an update that landed on replica A.

## 12. Geographic partitioning

```
User location
   → geohash (precision from radius)
   → center cell + 8 neighbors
   → Redis geo sets ∩ friend IDs
   → Haversine
   → radius filter
   → sort by distance
   → page of ~20
```

Neighbors exist so users on cell edges are not missed.

## 13. Load balancing

Local: nginx with Docker DNS (`resolver 127.0.0.11`) so `docker compose up --scale api-server=2 --scale websocket-server=2` round-robins.

Production: L4/L7 LB, separate pools for REST vs WebSocket (sticky sessions optional; not required because Pub/Sub connects instances).

## 14. Horizontal scaling

API servers are stateless. WebSocket servers are connection-stateful but interchangeable thanks to Pub/Sub. Scale each pool independently. `INSTANCE_ID` / hostname identifies replicas in logs and `/health`.

## 15. Database sharding

Shard `users` and `friendships` by `user_id` (hash). Friend lists stay on the owner’s shard because we store both directions. Cross-shard add-friend is a dual write with eventual consistency — acceptable for social graph, not for current location.

## 16. Redis scaling

Local: one Redis. Production: cluster; shard `loc:` by user_id and `geo:` by geohash prefix using the same consistent-hash module. Pub/Sub does not scale like the cache — production would partition channels across Pub/Sub nodes (or a dedicated broker as a **future** option, not in this MVP).

## 17. Service discovery

`location-service/discovery.py` is the abstraction. MVP: static Compose names. Production: etcd/ZooKeeper leases for live WS/Redis nodes feeding the hash ring. ZooKeeper is **not** deployed locally.

## 18. Consistent hashing

`location-service/consistent_hash.py` maps `user_id` / channel → node with virtual nodes. Adding a node remaps ~1/N keys. Demo: `python location-service/consistent_hash_demo.py`.

## 19. Failure handling

- Redis down: API `/health` degraded; nearby errors increment metrics; UI shows warning, does not crash
- WebSocket drop: client reconnects with backoff
- Failed location_update: client keeps last known marker + timestamp; never invents coordinates
- Instance death: nginx sends new HTTP to remaining API; new WS connections to remaining WS servers; in-flight sockets on the dead node reconnect

## 20. Eventual consistency

Location changes every few seconds. A missed Pub/Sub message is repaired by the next update or REST nearby refresh. We do not use distributed transactions across Redis + Postgres + Pub/Sub.

## 21. Trade-offs

| Choice | Why | Cost |
| --- | --- | --- |
| Redis for “now” | TTL + speed | Not a legal audit log |
| History in Postgres | Analytics | Must not be on the nearby hot path |
| Per-user Pub/Sub channels | Targeted delivery | Many subscriptions on WS nodes |
| Geohash + Haversine | Avoid global scans | Cell size vs radius tuning |
| Bidirectional friendships | Simple list/query | Double writes on add/remove |
| Demo auth = pick a user | Fast judging | Not production security |
| MVP max 50 friends | Bound fan-out | Whales need extra design |

## 22. Production evolution

See [scalability.md](scalability.md). Local Docker is a **functional** slice of this architecture, not a 1B-user cluster.
