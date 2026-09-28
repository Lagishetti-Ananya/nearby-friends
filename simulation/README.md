# Load / scale simulator

This tool generates virtual users and location updates, then **measures** throughput and latency. It does not invent metrics.

## Modes

### `local` (default)

Runs geohash encoding, Haversine, and in-memory fan-out in-process. Use this for large synthetic scenarios (1k–100k updates) without saturating Docker.

### `live`

Opens real WebSocket connections against a running stack (`http://localhost:8080`) using seeded demo users.

## Commands

From `nearby-friends/`:

```bash
pip install httpx websockets
python simulation/load_test.py --scenario 1
python simulation/load_test.py --scenario 2
python simulation/load_test.py --scenario 3
python simulation/load_test.py --scenario 4
```

Live stack (after `docker compose up`):

```bash
python simulation/load_test.py --mode live --users 5 --concurrent 5 --interval 1 --duration 10
```

Environment overrides: `USERS`, `CONCURRENT_USERS`, `UPDATE_INTERVAL`, `MODE`, `API_BASE`, `WS_URL`.

## Scenarios

| Scenario | What it stresses |
| --- | --- |
| 1 | 100 virtual users |
| 2 | 1,000 virtual users |
| 3 | 10,000 virtual users |
| 4 | Aim for ~100,000 location-processing iterations on a capable machine |

These numbers characterize **this laptop**, not a 1-billion-user production deployment.
