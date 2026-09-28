"""In-memory latency histogram used by the load simulator."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class LatencyStats:
    samples_ms: list[float] = field(default_factory=list)

    def observe(self, seconds: float) -> None:
        self.samples_ms.append(max(0.0, seconds * 1000.0))

    def percentile(self, p: float) -> float | None:
        if not self.samples_ms:
            return None
        ordered = sorted(self.samples_ms)
        idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
        return ordered[idx]

    def average(self) -> float | None:
        if not self.samples_ms:
            return None
        return sum(self.samples_ms) / len(self.samples_ms)


class SimulatorMetrics:
    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.location_ok = 0
        self.location_fail = 0
        self.nearby_ok = 0
        self.nearby_fail = 0
        self.pubsub_events = 0
        self.ws_connected = 0
        self.ws_peak = 0
        self.update_latency = LatencyStats()
        self.nearby_latency = LatencyStats()

    def mark_ws(self, delta: int) -> None:
        self.ws_connected += delta
        self.ws_peak = max(self.ws_peak, self.ws_connected)

    def elapsed(self) -> float:
        return max(1e-6, time.perf_counter() - self.started)

    def report(self, users: int) -> str:
        elapsed = self.elapsed()
        ups = self.location_ok / elapsed
        pps = self.pubsub_events / elapsed
        avg = self.update_latency.average()
        p50 = self.update_latency.percentile(50)
        p95 = self.update_latency.percentile(95)
        p99 = self.update_latency.percentile(99)
        fmt = lambda v: f"{v:.2f}ms" if v is not None else "n/a"
        return "\n".join(
            [
                f"Users: {users}",
                f"Active connections: {self.ws_connected} (peak {self.ws_peak})",
                f"Location updates/sec: {ups:.2f}",
                f"Pub/Sub events/sec: {pps:.2f}",
                f"Successful updates: {self.location_ok}",
                f"Failed updates: {self.location_fail}",
                f"Nearby queries ok/fail: {self.nearby_ok}/{self.nearby_fail}",
                f"Average latency: {fmt(avg)}",
                f"P50 latency: {fmt(p50)}",
                f"P95 latency: {fmt(p95)}",
                f"P99 latency: {fmt(p99)}",
                f"Elapsed: {elapsed:.2f}s",
            ]
        )
