# Hackathon demo

Open `http://localhost:8080` after Compose is healthy.

## Seeded users (deterministic IDs)

| Name | UUID | Start | Nearby at 5 miles from Alice? |
| --- | --- | --- | --- |
| Alice | `11111111-1111-1111-1111-111111111111` | Downtown SF | — |
| Bob | `22222222-2222-2222-2222-222222222222` | ~1 mi | Yes |
| Carol | `33333333-3333-3333-3333-333333333333` | ~1 mi | Yes |
| Dave | `44444444-4444-4444-4444-444444444444` | Oakland ~8 mi | No (yes at 10) |
| Eve | `55555555-5555-5555-5555-555555555555` | San Jose ~40 mi | No |

Friend graph: Alice–Bob–Carol–Dave mesh; Alice–Eve so Eve is a friend but not nearby.

**There are no passwords.** The user dropdown is the demo identity.

## 5-minute script

1. Show architecture diagram in `docs/architecture.md`.
2. Open Alice: sharing ON, radius 5, map + Bob/Carol.
3. Second browser (or switch user): Bob. Walk ON — Alice’s map marker moves without refresh.
4. Set Alice radius to 10 — Dave appears; Eve still absent.
5. Turn Alice sharing OFF — Bob loses Alice (`presence_update`).
6. Metrics tab: location updates, Pub/Sub, latency.
7. `docker compose ps` and optional `--scale` for two API/WS replicas.
8. `python simulation/load_test.py --scenario 2` and read **measured** lines.

## What judges should notice

- Redis is current location; Postgres history is separate
- Pub/Sub is per-user, not global broadcast
- Geohash + Haversine, not “query all users”
- Multi-instance story via nginx + INSTANCE_ID
