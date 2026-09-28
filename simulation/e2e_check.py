"""End-to-end check against a running stack (http://localhost:8080)."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

API = "http://localhost:8080/api"
WS = "ws://localhost:8080/ws"
ALICE = "11111111-1111-1111-1111-111111111111"
BOB = "22222222-2222-2222-2222-222222222222"


async def recv_until(ws, event: str, timeout: float = 8.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("event") == event:
            return msg
    raise TimeoutError(f"did not receive {event}")


async def main() -> int:
    async with httpx.AsyncClient(timeout=10) as client:
        health = (await client.get(f"{API}/health")).json()
        print("health:", health)
        if health.get("postgres") != "ok" or health.get("redis") != "ok":
            print("FAIL: postgres/redis not ok")
            return 1
        users = (await client.get(f"{API}/demo/users")).json()
        names = {u["name"] for u in users}
        print("demo users:", names)
        if not {"Alice", "Bob"} <= names:
            print("FAIL: seed users missing")
            return 1

        async with websockets.connect(WS) as ws_a, websockets.connect(WS) as ws_b:
            await ws_a.send(json.dumps({"event": "initialize", "user_id": ALICE}))
            await ws_b.send(json.dumps({"event": "initialize", "user_id": BOB}))
            init_a = await recv_until(ws_a, "initialize")
            init_b = await recv_until(ws_b, "initialize")
            print("ws instances", init_a.get("instance_id"), init_b.get("instance_id"))

            await ws_b.send(
                json.dumps({"event": "location_update", "latitude": 37.7840, "longitude": -122.4094})
            )
            await recv_until(ws_b, "location_update")

            await ws_a.send(
                json.dumps({"event": "location_update", "latitude": 37.7749, "longitude": -122.4194})
            )
            await recv_until(ws_a, "location_update")

            nearby_msg = None
            deadline = asyncio.get_event_loop().time() + 8
            while asyncio.get_event_loop().time() < deadline:
                raw = await asyncio.wait_for(ws_a.recv(), timeout=8)
                msg = json.loads(raw)
                if msg.get("event") == "nearby_update" and msg.get("upsert"):
                    nearby_msg = msg
                    if msg["upsert"]["user_id"] == BOB:
                        break
            if not nearby_msg:
                print("WARN: no nearby_update on Alice WS (may still appear via REST)")
            else:
                print("nearby_update upsert:", nearby_msg["upsert"]["name"], nearby_msg["upsert"]["distance_miles"])

            near = (await client.get(f"{API}/users/{ALICE}/nearby")).json()
            friend_names = {f["name"] for f in near["friends"]}
            print("REST nearby for Alice:", friend_names, "total", near["total"])
            if "Bob" not in friend_names:
                print("FAIL: Bob not nearby Alice")
                return 1

            off = await client.post(f"{API}/users/{BOB}/location-sharing", json={"enabled": False})
            off.raise_for_status()
            await asyncio.sleep(0.5)
            near2 = (await client.get(f"{API}/users/{ALICE}/nearby")).json()
            names2 = {f["name"] for f in near2["friends"]}
            print("after Bob sharing OFF:", names2)
            if "Bob" in names2:
                print("FAIL: Bob still nearby after sharing off")
                return 1
            await client.post(f"{API}/users/{BOB}/location-sharing", json={"enabled": True})

        print("E2E PASS")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
