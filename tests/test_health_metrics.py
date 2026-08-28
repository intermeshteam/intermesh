import asyncio
import json
import os
import subprocess
import sys
import urllib.request
import pytest
from intermesh.metrics import InterMeshMetricsCollector
from intermesh.health import HealthCheckHandler


def test_metrics_collector_prometheus_format():
    collector = InterMeshMetricsCollector()
    collector.increment("intermesh_messages_routed_total", 5)
    collector.increment("intermesh_tasks_submitted_total", 2)

    output = collector.generate_prometheus_output({
        "intermesh_connected_agents": 3,
        "intermesh_registered_identities": 10
    })

    assert "intermesh_uptime_seconds" in output
    assert "intermesh_connected_agents 3" in output
    assert "intermesh_registered_identities 10" in output
    assert "intermesh_messages_routed_total 5" in output
    assert "intermesh_tasks_submitted_total 2" in output


def test_health_handler_endpoints():
    handler = HealthCheckHandler(
        readiness_evaluator=lambda: True,
        state_metrics_provider=lambda: {"intermesh_connected_agents": 1}
    )

    # 1. Test /healthz
    status, headers, body = handler.handle_request("/healthz")
    assert status == 200
    assert json.loads(body.decode("utf-8"))["status"] == "ok"

    # 2. Test /readyz (nominal)
    status, headers, body = handler.handle_request("/readyz")
    assert status == 200
    assert json.loads(body.decode("utf-8"))["ready"] is True

    # 3. Test /readyz (non pret)
    unready_handler = HealthCheckHandler(readiness_evaluator=lambda: False)
    status, headers, body = unready_handler.handle_request("/readyz")
    assert status == 503
    assert json.loads(body.decode("utf-8"))["ready"] is False

    # 4. Test /metrics
    status, headers, body = handler.handle_request("/metrics")
    assert status == 200
    assert "intermesh_connected_agents 1" in body.decode("utf-8")


@pytest.mark.asyncio
async def test_live_hub_http_probes():
    """
    Valide les requetes HTTP reelles sur le Hub en ecoute.
    """
    port = 8860
    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub_proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port),
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    await asyncio.sleep(1.5)

    try:
        # Sonde /healthz
        with urllib.request.urlopen(f"http://localhost:{port}/healthz") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

        # Sonde /readyz
        with urllib.request.urlopen(f"http://localhost:{port}/readyz") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ready"] is True

        # Endpoint /metrics
        with urllib.request.urlopen(f"http://localhost:{port}/metrics") as resp:
            assert resp.status == 200
            metrics_text = resp.read().decode("utf-8")
            assert "intermesh_uptime_seconds" in metrics_text
            assert "intermesh_connected_agents" in metrics_text

    finally:
        hub_proc.terminate()
        hub_proc.wait()
