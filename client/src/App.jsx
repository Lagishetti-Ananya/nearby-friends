import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapView from "./MapView.jsx";
import MetricsPage from "./MetricsPage.jsx";
import { apiGet, apiSend } from "./api.js";
import { DEMO_STARTS } from "./demoUsers.js";
import { useRealtime } from "./useRealtime.js";

const RADIUS_OPTIONS = [1, 5, 10];

// Requirement: location refresh every 30 seconds.
const LOCATION_REFRESH_MS = 30_000;

export default function App() {
  const [view, setView] = useState("map");
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState("");
  const [profile, setProfile] = useState(null);
  const [friends, setFriends] = useState([]);
  const [nearby, setNearby] = useState([]);
  const [sharing, setSharing] = useState(true);
  const [radius, setRadius] = useState(5);
  const [selfLoc, setSelfLoc] = useState(null);
  const [bootError, setBootError] = useState(null);
  const [redisHint, setRedisHint] = useState(true);
  const [walk, setWalk] = useState(true);
  const [candidateId, setCandidateId] = useState("");

  const socketSendRef = useRef(null);
  const posRef = useRef(null);

  /*
   * Keep the latest values available to the 30-second location timer
   * without recreating the timer on every React render.
   */
  const userIdRef = useRef(userId);
  const sharingRef = useRef(sharing);
  const walkRef = useRef(walk);

  useEffect(() => {
    userIdRef.current = userId;
  }, [userId]);

  useEffect(() => {
    sharingRef.current = sharing;
  }, [sharing]);

  useEffect(() => {
    walkRef.current = walk;
  }, [walk]);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiGet("/demo/users");

      setUsers(data);

      if (!userId && data.length) {
        setUserId(data[0].id);
      }

      setBootError(null);
    } catch (err) {
      setBootError(err.message || "API unavailable");
    }
  }, [userId]);

  useEffect(() => {
    loadUsers();

    const timer = setInterval(loadUsers, 15000);

    return () => clearInterval(timer);
  }, [loadUsers]);

  const refreshRest = useCallback(async (id) => {
    if (!id) return;

    try {
      const [me, flist, near] = await Promise.all([
        apiGet(`/users/${id}`),
        apiGet(`/users/${id}/friends`),
        apiGet(`/users/${id}/nearby`),
      ]);

      setProfile(me);
      setSharing(me.location_sharing_enabled);
      setRadius(me.nearby_radius);
      setFriends(flist);
      setNearby(near.friends || []);
      setRedisHint(near.redis_available !== false);
    } catch (err) {
      setBootError(err.message);
    }
  }, []);

  useEffect(() => {
    if (userId) {
      refreshRest(userId);
    }
  }, [userId, refreshRest]);

  const onInit = useCallback((msg) => {
    setNearby(msg.nearby || []);

    if (msg.nearby_radius) {
      setRadius(msg.nearby_radius);
    }

    if (typeof msg.location_sharing_enabled === "boolean") {
      setSharing(msg.location_sharing_enabled);
    }
  }, []);

  const onNearby = useCallback((msg) => {
    setNearby((prev) => {
      let next = prev.slice();

      if (msg.friends) {
        return msg.friends;
      }

      if (msg.remove) {
        next = next.filter((f) => f.user_id !== msg.remove);
      }

      if (msg.upsert) {
        next = next.filter(
          (f) => f.user_id !== msg.upsert.user_id
        );

        next.push(msg.upsert);

        next.sort(
          (a, b) => a.distance_miles - b.distance_miles
        );
      }

      return next;
    });
  }, []);

  const onPresence = useCallback((msg) => {
    if (msg.active === false) {
      setNearby((prev) =>
        prev.filter((f) => f.user_id !== msg.user_id)
      );
    }
  }, []);

  const {
    status,
    lastSync,
    instanceId,
    error,
    send,
  } = useRealtime({
    userId,
    enabled: Boolean(userId),
    onInit,
    onNearby,
    onPresence,
  });

  /*
   * Keep the latest send function available to the 30-second timer.
   */
  useEffect(() => {
    socketSendRef.current = send;
  }, [send]);

  /*
   * Reset simulated location whenever the selected demo user changes.
   */
  useEffect(() => {
    const seed = DEMO_STARTS[userId];

    posRef.current = seed
      ? {
          lat: seed.lat,
          lon: seed.lon,
        }
      : {
          lat: 37.7749,
          lon: -122.4194,
        };

    setSelfLoc({
      ...posRef.current,
      updatedAt: null,
    });
  }, [userId]);

  /*
   * 30-SECOND LOCATION UPDATE
   *
   * The WebSocket should stay connected.
   * We only send a new location every 30 seconds.
   */
  useEffect(() => {
    const sendLocationUpdate = () => {
      const currentUserId = userIdRef.current;

      if (!currentUserId || !sharingRef.current) {
        return;
      }

      const pos = posRef.current || {
        lat: 37.7749,
        lon: -122.4194,
      };

      /*
       * Simulate a small movement when "Simulate walk" is enabled.
       */
      if (walkRef.current) {
        pos.lat += (Math.random() - 0.5) * 0.0015;
        pos.lon += (Math.random() - 0.5) * 0.0015;
      }

      posRef.current = pos;

      const timestamp = new Date().toISOString();

      setSelfLoc({
        lat: pos.lat,
        lon: pos.lon,
        updatedAt: timestamp,
      });

      /*
       * Send through the existing WebSocket.
       * If the socket is temporarily disconnected, the reconnect
       * mechanism in useRealtime will handle the connection.
       */
      const currentSend = socketSendRef.current;

      if (currentSend) {
        currentSend({
          event: "location_update",
          latitude: pos.lat,
          longitude: pos.lon,
        });
      }
    };

    /*
     * Send the initial location immediately.
     */
    sendLocationUpdate();

    /*
     * Then update exactly every 30 seconds.
     */
    const timer = setInterval(
      sendLocationUpdate,
      LOCATION_REFRESH_MS
    );

    return () => {
      clearInterval(timer);
    };
  }, []);

  const otherUsers = useMemo(
    () => users.filter((u) => u.id !== userId),
    [users, userId]
  );

  const friendIds = useMemo(
    () => new Set(friends.map((f) => f.id)),
    [friends]
  );

  async function toggleSharing(next) {
    setSharing(next);
    sharingRef.current = next;

    await apiSend(
      `/users/${userId}/location-sharing`,
      "POST",
      {
        enabled: next,
      }
    );

    if (!next) {
      setSelfLoc(null);
    }
  }

  async function changeRadius(value) {
    const n = Number(value);

    setRadius(n);

    await apiSend(
      `/users/${userId}/radius`,
      "POST",
      {
        nearby_radius: n,
      }
    );

    refreshRest(userId);
  }

  async function addFriend() {
    if (!candidateId) return;

    await apiSend(
      `/users/${userId}/friends/${candidateId}`,
      "POST"
    );

    send({
      event: "subscribe_friend",
      friend_id: candidateId,
    });

    setCandidateId("");

    refreshRest(userId);
  }

  async function removeFriend(fid) {
    await apiSend(
      `/users/${userId}/friends/${fid}`,
      "DELETE"
    );

    send({
      event: "unsubscribe_friend",
      friend_id: fid,
    });

    setNearby((prev) =>
      prev.filter((f) => f.user_id !== fid)
    );

    refreshRest(userId);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">
            Nearby Friends
          </div>

          <div className="muted">
            Scalable real-time location sharing
          </div>
        </div>

        <nav>
          <button
            className={view === "map" ? "active" : ""}
            onClick={() => setView("map")}
          >
            Live map
          </button>

          <button
            className={view === "metrics" ? "active" : ""}
            onClick={() => setView("metrics")}
          >
            Metrics
          </button>
        </nav>

        <div className={`status ${status}`}>
          <span className="dot" />

          {status}

          {instanceId ? (
            <span className="muted">
              {" · "}
              {instanceId}
            </span>
          ) : null}
        </div>
      </header>

      {view === "metrics" ? (
        <MetricsPage />
      ) : (
        <div className="layout">
          <aside className="panel">
            <label>
              Demo identity (not production auth)
            </label>

            <select
              value={userId}
              onChange={(e) =>
                setUserId(e.target.value)
              }
            >
              {users.map((u) => (
                <option
                  key={u.id}
                  value={u.id}
                >
                  {u.name}
                </option>
              ))}
            </select>

            <div className="row">
              <span>Location sharing</span>

              <button
                className={sharing ? "on" : "off"}
                onClick={() =>
                  toggleSharing(!sharing)
                }
              >
                {sharing ? "ON" : "OFF"}
              </button>
            </div>

            <label>
              Nearby radius
            </label>

            <select
              value={radius}
              onChange={(e) =>
                changeRadius(e.target.value)
              }
            >
              {RADIUS_OPTIONS.map((r) => (
                <option
                  key={r}
                  value={r}
                >
                  {r} mile{r === 1 ? "" : "s"}
                </option>
              ))}
            </select>

            <div className="row">
              <span>Simulate walk</span>

              <button
                className={walk ? "on" : "off"}
                onClick={() =>
                  setWalk(!walk)
                }
              >
                {walk ? "ON" : "OFF"}
              </button>
            </div>

            <p className="muted small">
              Location refresh: every 30 seconds
            </p>

            <p className="muted small">
              Last sync:{" "}
              {lastSync
                ? new Date(
                    lastSync
                  ).toLocaleTimeString()
                : "—"}
            </p>

            {error ? (
              <p className="warn">
                {error}
              </p>
            ) : null}

            {bootError ? (
              <p className="warn">
                {bootError}
              </p>
            ) : null}

            {!redisHint ? (
              <p className="warn">
                Redis unavailable — nearby
                discovery degraded.
              </p>
            ) : null}

            <h3>Friends</h3>

            <ul className="list">
              {friends.map((f) => (
                <li key={f.id}>
                  <span>{f.name}</span>

                  <button
                    className="tiny"
                    onClick={() =>
                      removeFriend(f.id)
                    }
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>

            <div className="add-friend">
              <select
                value={candidateId}
                onChange={(e) =>
                  setCandidateId(e.target.value)
                }
              >
                <option value="">
                  Add friend…
                </option>

                {otherUsers
                  .filter(
                    (u) =>
                      !friendIds.has(u.id)
                  )
                  .map((u) => (
                    <option
                      key={u.id}
                      value={u.id}
                    >
                      {u.name}
                    </option>
                  ))}
              </select>

              <button
                onClick={addFriend}
                disabled={!candidateId}
              >
                Add
              </button>
            </div>

            <h3>
              Nearby ({nearby.length})
            </h3>

            <ul className="list nearby">
              {nearby.map((f) => (
                <li key={f.user_id}>
                  <div>
                    <strong>
                      {f.name}
                    </strong>

                    <div className="muted small">
                      {f.distance_miles.toFixed(
                        2
                      )}{" "}
                      mi ·{" "}
                      {new Date(
                        f.updated_at
                      ).toLocaleTimeString()}
                    </div>
                  </div>

                  <span className="badge">
                    {f.active
                      ? "active"
                      : "inactive"}
                  </span>
                </li>
              ))}

              {nearby.length === 0 ? (
                <li className="muted">
                  No friends inside the
                  radius.
                </li>
              ) : null}
            </ul>
          </aside>

          <main className="map-wrap">
            <MapView
              self={selfLoc}
              friends={nearby}
            />
          </main>
        </div>
      )}
    </div>
  );
}