"""Reprise des tâches restées inachevées."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

import pytest

from nexus_sdk import NexusAgent

PORT = 8805


def _start_hub(state_db, secret_file):
    return subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--state-file", state_db, "--secret-file", secret_file],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_task_submitted_while_assignee_offline_is_resumed_on_reconnect():
    """
    Une tâche confiée à un agent absent doit lui être réassignée dès qu'il
    se connecte, sans que l'orchestrateur ait à la resoumettre.
    """
    work = tempfile.mkdtemp()
    state_db = os.path.join(work, "hub_state.db")
    secret_file = os.path.join(work, "hub_secret")

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub = _start_hub(state_db, secret_file)
    await asyncio.sleep(1.5)

    executed = asyncio.Event()

    try:
        # 1. L'orchestrateur confie une tâche à un exécutant hors ligne.
        lead = NexusAgent(name="lead", hub_url=f"ws://localhost:{PORT}",
                          roles=["admin"], encrypt=False)
        await lead.connect()

        with pytest.raises(Exception):
            await lead.submit_task("Travail différé", "acme/worker",
                                   {"a": 6, "b": 7}, timeout=3.0)

        # La tâche est bien enregistrée, en attente.
        conn = sqlite3.connect(state_db)
        statuses = dict(conn.execute(
            "SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
        conn.close()
        assert statuses.get("pending") == 1, f"attendu 1 tâche pending, trouvé {statuses}"

        # 2. L'exécutant arrive. Le Hub doit lui pousser la tâche.
        async def handler(input_data, task):
            executed.set()
            return {"result": input_data["a"] * input_data["b"]}

        worker = NexusAgent(name="worker", org_id="acme",
                            hub_url=f"ws://localhost:{PORT}",
                            capabilities=["calculate"], roles=["worker"], encrypt=False)
        worker.on_task(handler)
        await worker.connect()

        await asyncio.wait_for(executed.wait(), timeout=8.0)
        await asyncio.sleep(1.0)   # laisse le TASK_UPDATE remonter

        conn = sqlite3.connect(state_db)
        statuses = dict(conn.execute(
            "SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
        events = [r[0] for r in conn.execute("SELECT payload FROM audit_log")]
        conn.close()

        assert statuses.get("completed") == 1, f"la tâche doit être terminée, trouvé {statuses}"
        assert any("TASK_RESUMED" in e for e in events), "la reprise doit être auditée"

        await worker.ws.close()
        await lead.ws.close()
        print("✓ Tâche en attente réassignée à la reconnexion de l'exécutant")

    finally:
        _stop(hub)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
