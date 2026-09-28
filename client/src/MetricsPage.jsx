import { useEffect, useState } from "react";
import { apiGet } from "./api.js";

export default function MetricsPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  async function load() {
    try {
      setData(await apiGet("/metrics"));
      setErr(null);
    } catch (e) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  if (err) return <div className="metrics-page warn">{err}</div>;
  if (!data) return <div className="metrics-page muted">Loading metrics…</div>;

  const c = data.counts || {};
  const lat = data.latency_ms || {};
  return (
    <div className="metrics-page">
      <h2>Live service metrics</h2>
      <p className="muted">
        Shared via Redis so all API/WebSocket replicas contribute. Instance: {data.instance_id}
      </p>
      <div className="cards">
        <Card title="HTTP requests" value={c.http_requests} />
        <Card title="Location updates" value={c.location_updates} />
        <Card title="Failed updates" value={c.location_updates_failed} />
        <Card title="WS opened" value={c.ws_connections_opened} />
        <Card title="Pub/Sub published" value={c.pubsub_published} />
        <Card title="Pub/Sub received" value={c.pubsub_received} />
        <Card title="Nearby queries" value={c.nearby_queries} />
        <Card title="Errors" value={c.errors} />
      </div>
      <h3>Latency (ms)</h3>
      <table>
        <thead>
          <tr>
            <th>Operation</th>
            <th>Count</th>
            <th>Avg</th>
            <th>P50</th>
            <th>P95</th>
            <th>P99</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(lat).map(([name, row]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{row.count}</td>
              <td>{row.avg ?? "—"}</td>
              <td>{row.p50 ?? "—"}</td>
              <td>{row.p95 ?? "—"}</td>
              <td>{row.p99 ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Card({ title, value }) {
  return (
    <div className="card">
      <div className="muted small">{title}</div>
      <div className="big">{value ?? 0}</div>
    </div>
  );
}
