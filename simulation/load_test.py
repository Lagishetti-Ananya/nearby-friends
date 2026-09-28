"""Load / scale simulator.

Modes:
  local  — in-process geohash + Haversine + in-memory pub/sub fan-out (no Docker).
  live   — hits REST + WebSocket of a running stack.

Examples:
  python load_test.py --mode local --users 1000 --interval 0.05 --duration 5
  python load_test.py --mode live --users 100 --concurrent 50 --interval 1 --duration 15
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "location-service"))
sys.path.insert(0, os.path.dirname(__file__))

from distance import haversine_miles  # noqa: E402
from geohash import encode  # noqa: E402
from metrics import SimulatorMetrics  # noqa: E402
from virtual_users import make_users, step  # noqa: E402


async def run_local(
    users_n: int, interval: float, duration: float, seed: int
) -> SimulatorMetrics:
    users = make_users(
        users_n, avg_friends=min(12, max(1, users_n // 5)), seed=seed
    )
    by_id = {u.user_id: u for u in users}
    locations = {
        u.user_id: (u.lat, u.lon, encode(u.lat, u.lon, 5)) for u in users
    }
    watchers: dict[str, set[str]] = defaultdict(set)
    for u in users:
        for fid in u.friends:
            watchers[fid].add(u.user_id)

    metrics = SimulatorMetrics()
    rng = random.Random(seed + 7)
    deadline = time.perf_counter() + duration
    idx = 0

    while time.perf_counter() < deadline:
        user = users[idx % len(users)]
        idx += 1
        started = time.perf_counter()

        step(user, rng)
        gh = encode(user.lat, user.lon, 5)
        locations[user.user_id] = (user.lat, user.lon, gh)

        fanout = 0
        for watcher_id in watchers.get(user.user_id, ()):
            w = by_id[watcher_id]
            wloc = locations[w.user_id]
            dist = haversine_miles(
                wloc[0], wloc[1], user.lat, user.lon
            )
            if dist <= w.radius:
                fanout += 1

        elapsed = time.perf_counter() - started
        metrics.location_ok += 1
        metrics.pubsub_events += fanout
        metrics.update_latency.observe(elapsed)

        if interval > 0:
            await asyncio.sleep(interval)
        elif idx % 500 == 0:
            await asyncio.sleep(0)

    metrics.ws_connected = users_n
    metrics.ws_peak = users_n
    return metrics


async def run_live(
    base: str,
    ws_url: str,
    users_n: int,
    concurrent: int,
    interval: float,
    duration: float,
) -> SimulatorMetrics:
    import json

    import httpx
    import websockets
    from websockets.exceptions import ConnectionClosedOK

    metrics = SimulatorMetrics()

    # Use the demo endpoint so live mode exercises the actual running stack.
    demo = httpx.get(f"{base}/demo/users", timeout=10)
    demo.raise_for_status()
    identities = demo.json()

    if len(identities) < 2:
        raise SystemExit("Need seeded demo users. Run database/seed.py first.")

    chosen = identities[: max(2, min(users_n, len(identities)))]
    concurrent = min(concurrent, len(chosen))

    async def worker(user: dict) -> None:
        uri = ws_url
        deadline = time.perf_counter() + duration

        try:
            async with websockets.connect(uri, max_size=2**20) as ws:
                metrics.mark_ws(1)

                await ws.send(
                    json.dumps(
                        {
                            "event": "initialize",
                            "user_id": user["id"],
                        }
                    )
                )

                # The server sends an initialize response first.
                await ws.recv()

                seed = {
                    "Alice": (37.7749, -122.4194),
                    "Bob": (37.784, -122.4094),
                    "Carol": (37.7649, -122.4294),
                }.get(user["name"], (37.77, -122.42))

                lat, lon = seed

                while time.perf_counter() < deadline:
                    lat += random.uniform(-0.001, 0.001)
                    lon += random.uniform(-0.001, 0.001)
                    started = time.perf_counter()

                    await ws.send(
                        json.dumps(
                            {
                                "event": "location_update",
                                "latitude": lat,
                                "longitude": lon,
                            }
                        )
                    )

                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=5
                        )
                        msg = json.loads(raw)

                        if (
                            msg.get("event") == "location_update"
                            and msg.get("ok")
                        ):
                            metrics.location_ok += 1
                            metrics.pubsub_events += int(
                                msg.get("pubsub_receivers") or 0
                            )

                        elif msg.get("event") == "error":
                            print(
                                f"LOAD TEST ERROR for {user['name']} "
                                f"({user['id']}): server error: "
                                f"{msg.get('message')}"
                            )
                            metrics.location_fail += 1

                        else:
                            # Any non-error response is treated as a successful
                            # round-trip, preserving compatibility with the server.
                            metrics.location_ok += 1

                    except TimeoutError:
                        print(
                            f"LOAD TEST ERROR for {user['name']} "
                            f"({user['id']}): TimeoutError waiting for "
                            f"location acknowledgment"
                        )
                        metrics.location_fail += 1

                    metrics.update_latency.observe(
                        time.perf_counter() - started
                    )

                    if interval > 0:
                        await asyncio.sleep(interval)

        # A WebSocket close with code 1000 is a normal close.
        # Do not count it as a failed location update.
        except ConnectionClosedOK:
            print(
                f"LOAD TEST INFO for {user['name']} "
                f"({user['id']}): WebSocket closed normally"
            )

        except Exception as exc:
            print(
                f"LOAD TEST ERROR for {user['name']} "
                f"({user['id']}): {type(exc).__name__}: {exc}"
            )
            metrics.location_fail += 1

        finally:
            metrics.mark_ws(-1)

    await asyncio.gather(
        *(worker(chosen[i]) for i in range(concurrent))
    )

    # Exercise the REST nearby endpoint after the WebSocket workers finish.
    async with httpx.AsyncClient(base_url=base, timeout=10) as client:
        for user in chosen[:concurrent]:
            t0 = time.perf_counter()
            try:
                r = await client.get(
                    f"/users/{user['id']}/nearby"
                )
                if r.status_code == 200:
                    metrics.nearby_ok += 1
                else:
                    print(
                        f"NEARBY QUERY ERROR for {user['name']} "
                        f"({user['id']}): HTTP {r.status_code}"
                    )
                    metrics.nearby_fail += 1

            except Exception as exc:
                print(
                    f"NEARBY QUERY ERROR for {user['name']} "
                    f"({user['id']}): {type(exc).__name__}: {exc}"
                )
                metrics.nearby_fail += 1

            metrics.nearby_latency.observe(
                time.perf_counter() - t0
            )

    return metrics


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Nearby Friends load simulator"
    )
    p.add_argument(
        "--mode",
        choices=["local", "live"],
        default=os.getenv("MODE", "local"),
    )
    p.add_argument(
        "--users",
        type=int,
        default=int(os.getenv("USERS", "1000")),
    )
    p.add_argument(
        "--concurrent",
        type=int,
        default=int(os.getenv("CONCURRENT_USERS", "100")),
    )
    p.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("UPDATE_INTERVAL", "0.01")),
    )
    p.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("DURATION", "3")),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--api",
        default=os.getenv("API_BASE", "http://localhost:8080/api"),
    )
    p.add_argument(
        "--ws",
        default=os.getenv("WS_URL", "ws://localhost:8080/ws"),
    )
    p.add_argument(
        "--scenario",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
    )
    return p.parse_args()


def apply_scenario(args: argparse.Namespace) -> argparse.Namespace:
    if args.scenario == 1:
        args.users, args.mode, args.interval, args.duration = (
            100,
            "local",
            0.0,
            1.0,
        )
    elif args.scenario == 2:
        args.users, args.mode, args.interval, args.duration = (
            1000,
            "local",
            0.0,
            1.5,
        )
    elif args.scenario == 3:
        args.users, args.mode, args.interval, args.duration = (
            10000,
            "local",
            0.0,
            2.0,
        )
    elif args.scenario == 4:
        args.users, args.mode, args.interval, args.duration = (
            2000,
            "local",
            0.0,
            8.0,
        )
        # ~2000 users * many steps ≈ 100k updates depending on loop speed.
    return args


async def amain() -> None:
    args = apply_scenario(parse_args())

    if args.mode == "local":
        metrics = await run_local(
            args.users,
            args.interval,
            args.duration,
            args.seed,
        )

        if args.scenario == 4 and metrics.location_ok < 100_000:
            # Continue until 100k updates or 60s, whichever first,
            # if the machine is fast.
            extra = await run_local(
                args.users,
                0.0,
                max(0.5, 12 - metrics.elapsed()),
                args.seed + 1,
            )
            metrics.location_ok += extra.location_ok
            metrics.pubsub_events += extra.pubsub_events
            metrics.update_latency.samples_ms.extend(
                extra.update_latency.samples_ms
            )

        print(metrics.report(args.users))
        print("Mode: local in-process (not 1B-user production)")
        return

    metrics = await run_live(
        args.api,
        args.ws,
        args.users,
        args.concurrent,
        args.interval,
        args.duration,
    )

    print(metrics.report(min(args.users, args.concurrent)))
    print("Mode: live stack")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
