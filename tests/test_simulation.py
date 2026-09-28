import os

import pytest

from metrics import SimulatorMetrics
from virtual_users import make_users
from load_test import run_local


def test_virtual_users_friend_cap():
    users = make_users(20, avg_friends=5, seed=1)
    assert len(users) == 20
    assert all(len(u.friends) == 5 for u in users)


@pytest.mark.asyncio
async def test_local_simulation_measures_real_counts():
    metrics = await run_local(users_n=40, interval=0.0, duration=0.2, seed=2)
    assert metrics.location_ok > 0
    assert metrics.location_ok == len(metrics.update_latency.samples_ms)
    report = metrics.report(40)
    assert "Location updates/sec:" in report
    assert "P95 latency:" in report


def test_metrics_percentiles_order():
    m = SimulatorMetrics()
    for x in [10, 20, 30, 40, 50]:
        m.update_latency.observe(x / 1000)
    assert m.update_latency.percentile(50) <= m.update_latency.percentile(95)


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="Set RUN_INTEGRATION=1 against a live stack")
def test_api_health_integration():
    import httpx

    r = httpx.get("http://localhost:8080/api/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
