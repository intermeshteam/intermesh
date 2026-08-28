"""
Tests de la reconnexion/failover côté client (SDK).

Portée assumée : ceci est un mécanisme de reconnexion CLIENT vers une liste
de Hubs candidats déjà en fonctionnement (ex: un Hub principal et une
réplique à chaud partageant le même `--state-file`) — pas une élection de
leader ni une promotion automatique côté serveur. Voir le docstring de
`InterMeshAgent._reconnect_loop` dans agent.py.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time

import pytest

from intermesh import InterMeshAgent

PORT_A = 8890
PORT_B = 8891


def test_hub_url_accepts_a_single_string_or_a_list():
    single = InterMeshAgent(name="a", hub_url="ws://localhost:8765")
    assert single._hub_candidates == ["ws://localhost:8765"]
    assert single.hub_url == "ws://localhost:8765"

    multi = InterMeshAgent(name="b", hub_url=["ws://localhost:8765", "ws://localhost:8766"])
    assert multi._hub_candidates == ["ws://localhost:8765", "ws://localhost:8766"]
    assert multi.hub_url == "ws://localhost:8765"
    print("✓ hub_url accepte une chaîne ou une liste de secours")


def test_auto_reconnect_is_off_by_default():
    """Aucune reconnexion surprise pour le code existant qui ferme `agent.ws` lui-même."""
    agent = InterMeshAgent(name="a")
    assert agent.auto_reconnect is False
    print("✓ auto_reconnect désactivé par défaut (rétrocompatible)")


@pytest.fixture
def shared_state_hubs():
    """Deux Hubs indépendants partageant le même fichier d'état — une réplique à chaud."""
    work = tempfile.mkdtemp()
    state_file = os.path.join(work, "shared.db")

    os.system(f"fuser -k {PORT_A}/tcp {PORT_B}/tcp 2>/dev/null")

    hub_a = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT_A), "--org", "acme",
         "--state-file", state_file, "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    hub_b = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT_B), "--org", "acme",
         "--state-file", state_file, "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    yield hub_a, hub_b
    for proc in (hub_a, hub_b):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _wait_until(predicate, timeout=10.0, interval=0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return False


@pytest.mark.asyncio
async def test_agent_fails_over_to_backup_hub_when_primary_dies(shared_state_hubs):
    hub_a, hub_b = shared_state_hubs
    hub_a_url = f"ws://localhost:{PORT_A}"
    hub_b_url = f"ws://localhost:{PORT_B}"

    failovers = []
    worker = InterMeshAgent(
        name="worker", org_id="acme", hub_url=[hub_a_url, hub_b_url],
        auto_reconnect=True, reconnect_backoff=0.3, encrypt=False,
    )
    worker.on_failover(lambda old, new: failovers.append((old, new)))

    @worker.on_task
    async def _handle(input_data, task):
        return {"handled_on": worker.hub_url}

    await worker.connect()
    assert worker.hub_url == hub_a_url

    # Le Hub A meurt brutalement.
    hub_a.terminate()
    hub_a.wait(timeout=5)

    ok = await _wait_until(lambda: worker.hub_url == hub_b_url, timeout=15.0)
    assert ok, "l'agent doit basculer automatiquement sur le Hub de secours"
    assert failovers and failovers[0] == (hub_a_url, hub_b_url)

    # L'agent redevenu joignable traite normalement une nouvelle tâche.
    lead = InterMeshAgent(name="lead", org_id="acme", hub_url=hub_b_url, roles=["admin"], encrypt=False)
    await lead.connect()
    result = await lead.submit_task("Après bascule", "acme/worker", {"x": 1}, timeout=5.0)
    assert result == {"handled_on": hub_b_url}

    await lead.close()
    await worker.close()
    print("✓ Bascule automatique vers le Hub de secours, service repris")


@pytest.mark.asyncio
async def test_pending_calls_fail_fast_on_disconnect_instead_of_hanging(shared_state_hubs):
    """
    Sans auto_reconnect, une perte de connexion doit échouer vite (ConnectionError)
    plutôt que de laisser l'appelant attendre le timeout complet.
    """
    agent = InterMeshAgent(name="lonely", org_id="acme", hub_url=f"ws://localhost:{PORT_A}", encrypt=False)
    await agent.connect()

    # who_is sur un nom inconnu : le Hub ne répond jamais, l'appel resterait
    # en attente jusqu'au timeout (5s par défaut) sans notre mécanisme.
    task = asyncio.create_task(agent.who_is("acme/does_not_exist", timeout=10.0))
    await asyncio.sleep(0.2)
    await agent.ws.close()

    start = time.monotonic()
    with pytest.raises(ConnectionError):
        await asyncio.wait_for(task, timeout=3.0)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, "l'échec doit être rapide, pas attendre le timeout de who_is()"
    print("✓ Les appels en attente échouent vite à la déconnexion")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
