"""
Pont universel : brancher un agent écrit dans un autre langage.

L'enjeu n'est pas Python — c'est qu'un binaire Go, un script Node ou un
service HTTP existant deviennent des agents InterMesh sans qu'on écrive
d'intégration. Ces tests exercent de vrais processus externes, dont un
agent Node, plutôt que des simulacres.
"""

import asyncio
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from intermesh import InterMeshAgent
from intermesh.bridge import (
    BridgeError, from_command, from_http, post_task, run_command,
)

PORT = 8851
HTTP_PORT = 8852
HUB_URL = f"ws://localhost:{PORT}"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node.js absent de la machine")


def _write_script(path, body: str) -> str:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


# ----------------------------------------------------------------------
# Mode exec : n'importe quel exécutable
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shell_script_round_trips_json(tmp_path):
    script = _write_script(tmp_path / "agent.sh", """#!/bin/bash
read -r payload
echo "{\\"echo\\": $payload, \\"runtime\\": \\"bash\\"}"
""")
    result = await run_command(script, {"value": 42})

    assert result["echo"] == {"value": 42}
    assert result["runtime"] == "bash"


@needs_node
@pytest.mark.asyncio
async def test_node_script_is_a_valid_agent_backend(tmp_path):
    script = _write_script(tmp_path / "agent.js", """
let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  process.stdout.write(JSON.stringify({
    sum: input.a + input.b,
    runtime: 'node ' + process.version.split('.')[0],
  }));
});
""")
    result = await run_command([NODE, script], {"a": 20, "b": 22})

    assert result["sum"] == 42
    assert result["runtime"].startswith("node")


@pytest.mark.asyncio
async def test_non_json_output_is_wrapped_not_rejected(tmp_path):
    """Un `echo` doit suffire à faire un agent — sinon le cas d'usage meurt."""
    script = _write_script(tmp_path / "plain.sh", "#!/bin/bash\ncat > /dev/null\necho bonjour\n")

    assert await run_command(script, {"x": 1}) == {"output": "bonjour"}


@pytest.mark.asyncio
async def test_empty_output_is_an_empty_result(tmp_path):
    script = _write_script(tmp_path / "silent.sh", "#!/bin/bash\ncat > /dev/null\n")

    assert await run_command(script, {"x": 1}) == {}


@pytest.mark.asyncio
async def test_non_zero_exit_surfaces_stderr(tmp_path):
    script = _write_script(tmp_path / "broken.sh",
                           "#!/bin/bash\ncat > /dev/null\necho 'disque plein' >&2\nexit 3\n")

    with pytest.raises(BridgeError) as exc:
        await run_command(script, {})

    assert "3" in str(exc.value)
    assert "disque plein" in str(exc.value)


@pytest.mark.asyncio
async def test_a_hanging_program_is_killed_not_awaited_forever(tmp_path):
    script = _write_script(tmp_path / "hang.sh", "#!/bin/bash\nsleep 30\n")

    started = time.monotonic()
    with pytest.raises(BridgeError, match="n'a pas répondu"):
        await run_command(script, {}, timeout=1.0)

    assert time.monotonic() - started < 5, "le timeout doit couper, pas attendre la fin"


@pytest.mark.asyncio
async def test_argument_list_form_does_not_use_a_shell(tmp_path):
    """La forme liste évite l'interprétation shell des métacaractères."""
    script = _write_script(tmp_path / "show.sh", "#!/bin/bash\ncat > /dev/null\necho \"$1\"\n")
    result = await run_command([script, "; rm -rf /"], {})

    assert result == {"output": "; rm -rf /"}


# ----------------------------------------------------------------------
# Mode http : n'importe quel service déjà en ligne
# ----------------------------------------------------------------------

class _DoublingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps({"doubled": payload["value"] * 2, "runtime": "http"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def http_service():
    server = HTTPServer(("127.0.0.1", HTTP_PORT), _DoublingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{HTTP_PORT}/task"
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_http_service_round_trips_json(http_service):
    assert await post_task(http_service, {"value": 21}) == {"doubled": 42, "runtime": "http"}


@pytest.mark.asyncio
async def test_unreachable_http_service_raises_bridge_error():
    with pytest.raises(BridgeError, match="injoignable"):
        await post_task("http://127.0.0.1:9/task", {}, timeout=2.0)


# ----------------------------------------------------------------------
# Bout en bout : le programme externe devient un agent du maillage
# ----------------------------------------------------------------------

def _start_hub():
    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    time.sleep(0.4)
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "default",
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    return proc


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def hub():
    proc = _start_hub()
    yield
    _stop(proc)


@needs_node
@pytest.mark.asyncio
async def test_a_node_agent_collaborates_with_a_python_agent(hub, tmp_path):
    """Un agent Node reçoit une tâche d'un orchestrateur Python, chiffrée E2E."""
    script = _write_script(tmp_path / "pricing.js", """
let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  process.stdout.write(JSON.stringify({
    total: input.quantity * input.unit_price,
    computed_by: 'node',
  }));
});
""")

    worker = orchestrator = None
    try:
        worker = from_command([NODE, script], name="node_pricing",
                              capabilities=["pricing"], hub_url=HUB_URL)
        await worker.connect()

        orchestrator = InterMeshAgent(name="py_lead", roles=["admin"], hub_url=HUB_URL)
        await orchestrator.connect()
        await asyncio.sleep(0.8)

        result = await orchestrator.submit_task(
            title="Devis", assignee="node_pricing",
            input_data={"quantity": 1000, "unit_price": 115.0}, timeout=15.0,
        )

        assert result["total"] == 115000.0
        assert result["computed_by"] == "node"
    finally:
        for agent in (worker, orchestrator):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()


@pytest.mark.asyncio
async def test_an_http_service_becomes_an_agent(hub, http_service):
    worker = orchestrator = None
    try:
        worker = from_http(http_service, name="http_worker",
                           capabilities=["doubling"], hub_url=HUB_URL)
        await worker.connect()

        orchestrator = InterMeshAgent(name="http_lead", roles=["admin"], hub_url=HUB_URL)
        await orchestrator.connect()
        await asyncio.sleep(0.8)

        result = await orchestrator.submit_task(
            title="Doubler", assignee="http_worker",
            input_data={"value": 21}, timeout=15.0,
        )

        assert result["doubled"] == 42
    finally:
        for agent in (worker, orchestrator):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()


@needs_node
@pytest.mark.asyncio
async def test_cli_serve_exposes_a_foreign_program_without_any_code(hub, tmp_path):
    """
    La revendication « une ligne » prise au mot : aucun code d'intégration,
    seulement `intermesh serve --exec ...` sur un script Node.
    """
    script = _write_script(tmp_path / "upper.js", """
let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  process.stdout.write(JSON.stringify({shouted: input.text.toUpperCase()}));
});
""")

    served = subprocess.Popen(
        [sys.executable, "-m", "intermesh.cli", "serve",
         "--name", "shouter", "--exec", f"{NODE} {script}",
         "--capability", "shouting", "--hub", HUB_URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    await asyncio.sleep(2.5)

    orchestrator = None
    try:
        orchestrator = InterMeshAgent(name="cli_lead", roles=["admin"], hub_url=HUB_URL)
        await orchestrator.connect()
        await asyncio.sleep(0.8)

        result = await orchestrator.submit_task(
            title="Crier", assignee="shouter",
            input_data={"text": "intermesh"}, timeout=15.0,
        )

        assert result["shouted"] == "INTERMESH"
    finally:
        if orchestrator is not None and orchestrator.ws is not None:
            await orchestrator.ws.close()
        _stop(served)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
