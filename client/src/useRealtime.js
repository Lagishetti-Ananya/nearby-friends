import { useCallback, useEffect, useRef, useState } from "react";

function wsUrl() {
  const configured = import.meta.env.VITE_WS_URL || "/ws";
  if (configured.startsWith("ws://") || configured.startsWith("wss://")) return configured;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${configured}`;
}

export function useRealtime({ userId, enabled, onNearby, onPresence, onInit }) {
  const [status, setStatus] = useState("disconnected");
  const [lastSync, setLastSync] = useState(null);
  const [instanceId, setInstanceId] = useState(null);
  const [error, setError] = useState(null);
  const socketRef = useRef(null);
  const retriesRef = useRef(0);
  const userIdRef = useRef(userId);
  userIdRef.current = userId;

  const send = useCallback((payload) => {
    const ws = socketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (!userId || !enabled) {
      setStatus("disconnected");
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return undefined;
    }

    let stopped = false;
    let reconnectTimer;

    const connect = () => {
      if (stopped) return;
      setStatus("connecting");
      const ws = new WebSocket(wsUrl());
      socketRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
        setStatus("connected");
        setError(null);
        ws.send(JSON.stringify({ event: "initialize", user_id: userIdRef.current }));
      };

      ws.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        setLastSync(new Date().toISOString());
        if (msg.event === "error") {
          setError(msg.message);
          return;
        }
        if (msg.event === "initialize") {
          setInstanceId(msg.instance_id || null);
          onInit?.(msg);
        }
        if (msg.event === "nearby_update") onNearby?.(msg);
        if (msg.event === "presence_update") onPresence?.(msg);
        if (msg.event === "location_update" && msg.ok) {
          setLastSync(msg.timestamp || new Date().toISOString());
        }
      };

      ws.onerror = () => {
        setError("WebSocket error — retrying");
      };

      ws.onclose = () => {
        setStatus("disconnected");
        if (stopped) return;
        const delay = Math.min(8000, 500 * 2 ** retriesRef.current);
        retriesRef.current += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [userId, enabled, onInit, onNearby, onPresence]);

  return { status, lastSync, instanceId, error, send };
}
