import json

from discovery import StaticRegistry, default_local_registry, ServiceEndpoint


def test_static_registry():
    reg = default_local_registry()
    kinds = {n.kind for n in reg.list()}
    assert "websocket" in kinds and "redis" in kinds
    reg.register(ServiceEndpoint("ws-2", "websocket-server", 8001, "websocket"))
    assert len(reg.list("websocket")) == 2
    reg.unregister("ws-2")
    assert len(reg.list("websocket")) == 1


def test_websocket_event_shapes():
    initialize = {
        "event": "initialize",
        "user_id": "11111111-1111-1111-1111-111111111111",
    }
    location_update = {"event": "location_update", "latitude": 37.77, "longitude": -122.42}
    nearby_update = {
        "event": "nearby_update",
        "upsert": {
            "user_id": "22222222-2222-2222-2222-222222222222",
            "name": "Bob",
            "distance_miles": 0.9,
            "active": True,
        },
        "remove": None,
    }
    presence = {"event": "presence_update", "user_id": "22222222-2222-2222-2222-222222222222", "active": False}
    for payload in (initialize, location_update, nearby_update, presence):
        assert json.loads(json.dumps(payload))["event"]
