# Scalability

## A. What we actually run locally

- One Postgres 16
- One Redis 7 (with keyspace notifications)
- One or more FastAPI API containers (stateless)
- One or more FastAPI WebSocket containers
- nginx load balancer
- React/Vite static frontend

This is a **correct architecture in miniature**. It is not 10 million concurrent users.

## B. What we would deploy at production scale

- Load balancer (separate HTTP and WebSocket pools)
- Horizontally scaled API servers
- Horizontally scaled WebSocket servers (connection draining on deploy)
- Redis Cluster for `loc:` and `geo:` keys
- Partitioned Pub/Sub (channel ownership via consistent hashing + service discovery)
- Postgres sharded by `user_id` (friendship table co-located)
- History database scaled independently (batch ingest OK)
- etcd/ZooKeeper (or equivalent) for membership
- Metrics, tracing, autoscaling

## Fan-out math (why we filter early)

~334k location updates/sec × ~400 friends = **~134 million raw pushes/sec** if you naively notify every friend.

That is why this system:

1. Publishes once, on `user:{updater}`
2. Subscribes only where a **connected** friend exists
3. Drops events that fail friendship / sharing / geohash / radius checks
4. Pages the UI to ~20 nearby friends

Even after filters, hot cities and “whale” users (far more than 400 friends) dominate cost. MVP `MAX_FRIENDS=50`. Production whales: partition friend lists across workers, or push “dirty geohash cell” notifications instead of per-friend sends.

## WebSocket scaling

Connections are sticky to a process. Redis Pub/Sub is the cross-talk fabric. Graceful shutdown: stop accepting new WS, wait for clients to reconnect elsewhere, then exit. (MVP: container stop; clients reconnect automatically.)

## Redis sharding

Consistent hash(`user_id`) → cache node for `loc:`. Consistent hash(geohash prefix) → node for `geo:`. Adding a cache node remaps ~1/N keys (see tests). A single Redis process **cannot** absorb 334k writes/sec plus geo sets; the local container is a demo.

## Database sharding

Hash(`user_id`) % N shards. Dual-row friendships mean “friends of U” never scatter-gathers at read time. Add-friend is two shard writes.

## Geographic partitioning

Geohash cells bound the candidate set so we never Haversine the planet. Precision is chosen from radius (1 / 5 / 10 miles). Always include neighboring cells.

## Service discovery

Production membership (which WS/Redis nodes are alive) belongs in etcd/ZooKeeper. The MVP uses Docker DNS + `location-service/discovery.py` as the hook.

## Measured local throughput

Run `python simulation/load_test.py --scenario 1` through `--scenario 4` and record the printed numbers. Those numbers describe the machine that ran the simulator, not the theoretical 1B-user fleet.
