# Nearby Friends — Scalable Real-Time Location Sharing

Hackathon system-design project: friends can share location, see who is nearby (distance + last update), and receive updates in near real time — with an architecture that **explains** how you would grow toward ~1B users / ~334k location updates per second.

This repository is a **functional MVP**. It does **not** claim that your laptop is a billion-user cluster.

## Problem statement

Naive “query every user and compute distance” does not survive city-scale, let alone 10 million concurrent clients. Current location is hot, lossy, and ephemeral; friendships and history are not.

## Solution

Split the problem:

- **Postgres** — users and friendships (later shard by `user_id`); append-only location history
- **Redis + TTL** — current location and geohash cell indexes (inactive users vanish after 10 minutes)
- **Redis Pub/Sub** — `user:{id}` channels so WebSocket replicas can fan out **selectively**
- **Geohash neighbors + Haversine** — candidate pruning, then exact miles, then radius and a page of ~20
- **Stateless REST** + **connection-bearing WebSocket** processes behind a load balancer

## Key features

- Location sharing on/off
- Configurable radius (1 / 5 / 10 miles)
- Live Leaflet map
- Add/remove friends (MVP cap 50)
- Metrics dashboard
- Load simulator with **measured** latency/throughput
- Multi-instance Compose (`--scale`)

## Architecture

```
CLIENTS → LOAD BALANCER → REST API SERVERS → Postgres (users/friends)
                       → WEBSOCKET SERVERS → Redis location cache
                                           → Redis Pub/Sub → other WS servers → clients
                       → Location history (Postgres, not on the nearby hot path)
```

Details: [docs/architecture.md](docs/architecture.md) · sequences: [docs/sequence-diagram.md](docs/sequence-diagram.md) · scale: [docs/scalability.md](docs/scalability.md)

## Technology stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React, Vite, JavaScript, Leaflet | Fast local UI, OSM tiles, no vendor map key |
| REST / WS | Python, FastAPI, Uvicorn | Specified stack; async Redis + Postgres |
| User & history DB | PostgreSQL 16 | Relational friendships + indexed history |
| Cache / Pub/Sub | Redis 7 | TTL inactivity + simple channel fan-out |
| Edge | nginx | Local stand-in for an HTTP/WS load balancer |
| Packaged run | Docker Compose | One command demo |
| Simulator | Python asyncio | Configurable virtual users |

**Not in the MVP (future/production options only):** Kafka, Kubernetes, Cassandra, Elasticsearch, MongoDB, AWS-specific services.

## How to run (Docker — recommended)

```bash
cd nearby-friends
copy .env.example .env   # Windows
# cp .env.example .env  # macOS/Linux
docker compose up --build
```

Wait until `seed` has printed demo users, then open **http://localhost:8080**.

Health:

```bash
curl http://localhost:8080/api/health
```

Seed again if needed:

```bash
docker compose run --rm seed
```

## Docker commands

```bash
docker compose up --build
docker compose up --build --scale api-server=2 --scale websocket-server=2
docker compose ps
docker compose logs -f websocket-server
docker compose down -v
```

`INSTANCE_ID` defaults to the container hostname so replicas are distinguishable in `/health` and UI connection status.

## Local tests (no full stack)

```bash
cd nearby-friends
python -m pip install -r requirements-dev.txt -r api-server/requirements.txt
python -m pytest tests -q
python location-service/consistent_hash_demo.py
python simulation/load_test.py --scenario 1
```

## API

See [docs/api.md](docs/api.md). Highlights: `POST /users`, `GET /users/{id}`, friends CRUD, `GET /users/{id}/nearby`, `POST /users/{id}/location-sharing`, `GET /health`.

## WebSocket events

See [docs/websocket.md](docs/websocket.md): `initialize`, `location_update`, `subscribe_friend`, `unsubscribe_friend`, `nearby_update`, `presence_update`.

## Database design

- `users` — profile, sharing flag, radius
- `friendships` — bidirectional edges, PK `(user_id, friend_id)`, index on `friend_id`
- `location_history` — append-only, indexed by `(user_id, recorded_at)`

**Why two location stores:** nearby is “who is active *now*” (Redis TTL). History is “what happened” and must not be scanned on every map frame.

## Redis design

- `loc:{user_id}` JSON + TTL 600s
- `geo:{geohash}` sets for partitioning
- Pub/Sub `user:{user_id}`
- `metrics:*` counters shared across replicas

## Scalability strategy

Documented in [docs/scalability.md](docs/scalability.md). Local: small PG/Redis, few API/WS replicas. Production: LB, sharded PG, Redis cluster, partitioned Pub/Sub, consistent hashing, service discovery (etcd/ZK — **not** shipped in Compose).

## Load testing

```bash
python simulation/load_test.py --scenario 1   # 100 users
python simulation/load_test.py --scenario 2   # 1,000
python simulation/load_test.py --scenario 3   # 10,000
python simulation/load_test.py --scenario 4   # large in-process update loop
python simulation/load_test.py --mode live --concurrent 5 --interval 1 --duration 10
```

Printout includes updates/sec, Pub/Sub events/sec, avg/p50/p95/p99, successes/failures, connections. See [simulation/README.md](simulation/README.md).

## Measured results

Re-run the simulator on the judge machine and paste the CLI output. Numbers in a conversation write-up are from a specific host and must not be treated as SLAs.

## Limitations

- Demo identity picker is **not** authentication
- Single Redis and Postgres in Compose
- MVP friend cap 50; 400-friend / whale fan-out is designed, not fully solved
- Pub/Sub is fire-and-forget (eventual consistency)
- Leaflet tiles need outbound HTTPS to OSM
- Simulator `live` mode uses the five seeded users, not 10k real sockets (use `local` mode for large synthetic loops)

## Production architecture

Load balancer → N API + M WebSocket → Redis cluster + partitioned Pub/Sub → sharded Postgres + independent history pipeline → service discovery + consistent hash rings → monitoring and autoscaling.

## Future improvements

- Real auth (OIDC) and per-friend visibility rules
- Durable queue if history ingest lags
- Channel sharding / worker pools for whales
- Connection draining on WS deploys
- Geo-replicated Redis for continents

## Demo instructions

[docs/demo.md](docs/demo.md) — Alice/Bob/Carol in SF, Dave in Oakland, Eve in San Jose.

## Privacy

Exact coordinates are only sent to **friends** who pass nearby filters. Application logs include user ids and geohash cells, not lat/lon. Config is environment variables (`.env.example`).
