# Sequence diagrams

## 1. Client initialization

```mermaid
sequenceDiagram
    participant C as Client
    participant LB as Load balancer
    participant API as REST API
    participant WS as WebSocket server
    participant PG as Postgres
    participant R as Redis

    C->>LB: GET /api/users/{id}/friends
    LB->>API: GET /users/{id}/friends
    API->>PG: friends by user_id
    API-->>C: friend list
    C->>LB: GET /api/users/{id}/nearby
    API->>R: loc + geo cells
    API-->>C: nearby page
    C->>LB: WS /ws
    LB->>WS: upgrade
    C->>WS: initialize {user_id}
    WS->>PG: user + friends
    WS->>R: SUBSCRIBE user:{friend_id}
    WS->>R: nearby snapshot
    WS-->>C: initialize + nearby
    loop every few seconds
        C->>WS: location_update
    end
```

## 2. Periodic location update

```mermaid
sequenceDiagram
    participant C as Client A
    participant WS as WebSocket A
    participant H as Location history
    participant R as Redis cache
    participant P as Redis Pub/Sub
    participant WS2 as WebSocket B
    participant F as Client B (friend)

    C->>WS: location_update lat,lon
    WS->>R: SET loc:A EX 600 + geo cell
    WS->>H: INSERT location_history
    WS->>P: PUBLISH user:A
    P->>WS2: message
    WS2->>R: loc of B, radius of B
    WS2->>WS2: geohash + Haversine filter
    WS2-->>F: nearby_update upsert
```

## 3. Nearby friend discovery

```mermaid
sequenceDiagram
    participant C as Client
    participant API as REST API
    participant PG as Postgres
    participant R as Redis

    C->>API: GET /users/{id}/nearby
    API->>PG: user radius + friend ids
    API->>R: SMEMBERS geo:{cells}
    API->>API: intersect friends
    API->>R: MGET remaining loc keys
    API->>API: Haversine + radius + sort + page 20
    API-->>C: friends with distance + timestamp
```

## 4. Add friend

```mermaid
sequenceDiagram
    participant C as Client
    participant API as REST API
    participant PG as Postgres
    participant WS as WebSocket server

    C->>API: POST /users/{id}/friends/{friend}
    API->>PG: insert both directions (cap check)
    C->>WS: subscribe_friend
    WS->>PG: confirm friendship
    WS->>WS: watch friend channel
```

## 5. Remove friend

```mermaid
sequenceDiagram
    participant C as Client
    participant API as REST API
    participant PG as Postgres
    participant WS as WebSocket server

    C->>API: DELETE /users/{id}/friends/{friend}
    API->>PG: delete both directions
    C->>WS: unsubscribe_friend
    WS->>WS: drop watch; UNSUBSCRIBE if last local watcher
    Note over C: No further location events for that pair
```

## 6. WebSocket reconnection

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket server

    C--xWS: disconnect
    C->>C: show disconnected; backoff
    C->>WS: new socket
    C->>WS: initialize
    WS-->>C: snapshot nearby
    C->>C: resume location_update; keep last marker until first ok
```

## 7. Failure handling

```mermaid
sequenceDiagram
    participant C as Client
    participant API as REST API
    participant R as Redis
    participant WS as WebSocket

    C->>API: GET /nearby
    API->>R: GET
    R-->>API: timeout
    API-->>C: 500 / degraded metrics
    C->>C: keep last list; show Redis warning
    C--xWS: socket error
    C->>C: reconnect loop; status=connecting
```
