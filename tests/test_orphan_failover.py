"""
Sort des agents portés par un Hub qui meurt.

Le banc de mesure en grappe montrait que les Hubs survivants encaissent la
perte d'un frère sans une erreur. Il excluait volontairement les agents du
Hub tué, et laissait donc la question ouverte : que deviennent-ils ?

Mesuré avant d'être corrigé : ils restaient orphelins. Un agent ne connaît
que l'adresse qu'on lui a donnée ; son Hub mort, la boucle de reconnexion
rejouait indéfiniment la même adresse alors qu'un frère de la même grappe
l'aurait accepté. Le Hub, lui, sait qui est vivant — il ne le disait
simplement jamais.

Le Hub annonce désormais ses frères dans la réponse d'enregistrement, et
l'agent les ajoute à sa liste de repli. Ajoute, jamais ne substitue :
l'adresse écrite par l'exploitant reste la première essayée.

Exécution :
    export INTERMESH_TEST_PG_DSN=postgresql://intermesh:...@localhost:55435/intermesh
"""

from __future__ import annotations

import asyncio
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from intermesh import InterMeshAgent
from intermesh.store import InterMeshStore

PG_DSN = os.environ.get("INTERMESH_TEST_PG_DSN")
needs_pg = pytest.mark.skipif(not PG_DSN, reason="INTERMESH_TEST_PG_DSN non défini")

BASE_PORT = 9840
ORG = "banque"


def _wait_port(port: int, limit: float = 45.0) -> bool:
    deadline = time.time() + limit
    while time.time() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


class _Cluster:
    def __init__(self, ports: list[int]):
        self.ports = ports
        self.procs: dict[int, subprocess.Popen] = {}
        self.secret = Path(tempfile.mkdtemp()) / "cluster.secret"
        self.secret.write_text(secrets.token_hex(32))
        os.chmod(self.secret, 0o600)

    def url(self, index: int) -> str:
        return f"ws://localhost:{self.ports[index]}"

    def start(self) -> None:
        for index, port in enumerate(self.ports):
            os.system(f"fuser -k {port}/tcp >/dev/null 2>&1")
            self.procs[index] = subprocess.Popen(
                [sys.executable, "-u", "server/hub.py", "--port", str(port),
                 "--org", ORG, "--hub-id", f"hub-{index}",
                 "--state-dsn", PG_DSN, "--secret-file", str(self.secret),
                 "--cluster-url", self.url(index)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        for port in self.ports:
            assert _wait_port(port), f"le Hub sur {port} n'a pas démarré"
        # Laisse chaque Hub se déclarer avant qu'un agent n'arrive.
        time.sleep(2)

    def kill(self, index: int) -> None:
        proc = self.procs.pop(index)
        proc.kill()
        proc.wait(timeout=10)

    def stop(self) -> None:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.procs.clear()


@pytest.fixture
def cluster():
    store = InterMeshStore(dsn=PG_DSN)
    try:
        # Les Hubs d'un test précédent, tués sans se retirer, fausseraient
        # la liste annoncée.
        for hub in store.list_hubs():
            store.clear_hub(hub["hub_id"])
    finally:
        store.close()

    group = _Cluster([BASE_PORT, BASE_PORT + 1])
    group.start()
    yield group
    group.stop()


async def _agent(name: str, url: str, **kwargs) -> InterMeshAgent:
    agent = InterMeshAgent(name=name, org_id=ORG, hub_url=url, encrypt=False,
                           auto_reconnect=True, reconnect_backoff=0.3,
                           reconnect_max_backoff=2.0, **kwargs)
    await agent.connect()
    return agent


# ----------------------------------------------------------------------
# Unitaire : l'agent apprend, mais ne se laisse pas réécrire
# ----------------------------------------------------------------------

def test_siblings_are_added_never_substituted():
    """L'adresse écrite par l'exploitant reste la première essayée."""
    agent = InterMeshAgent(name="a", hub_url="ws://principal:8765", encrypt=False)
    agent._learn_siblings(["ws://frere-1:8765", "ws://frere-2:8765"])
    assert agent._hub_candidates[0] == "ws://principal:8765"
    assert "ws://frere-1:8765" in agent._hub_candidates


def test_duplicates_and_rubbish_are_ignored():
    agent = InterMeshAgent(name="a", hub_url="ws://principal:8765", encrypt=False)
    agent._learn_siblings(["ws://principal:8765", "", None, 42, "ws://frere:8765"])
    assert agent._hub_candidates == ["ws://principal:8765", "ws://frere:8765"]


def test_a_hub_outside_a_cluster_announces_nothing():
    """Le déploiement à un seul Hub ne change pas de comportement."""
    agent = InterMeshAgent(name="a", hub_url="ws://seul:8765", encrypt=False)
    agent._learn_siblings(None)
    agent._learn_siblings([])
    assert agent._hub_candidates == ["ws://seul:8765"]


# ----------------------------------------------------------------------
# Intégration
# ----------------------------------------------------------------------

@needs_pg
@pytest.mark.asyncio
async def test_the_hub_hands_out_its_siblings(cluster):
    agent = await _agent("apprenti", cluster.url(0), roles=["worker"])
    try:
        assert cluster.url(1) in agent._hub_candidates, (
            "le Hub doit annoncer ses frères, sinon l'agent ne peut pas basculer")
    finally:
        await agent.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_an_orphaned_agent_re_attaches_to_a_sibling(cluster):
    """Le cœur du correctif : sans lui, l'agent bouclait sur un Hub mort."""
    agent = await _agent("orphelin", cluster.url(0), roles=["worker"],
                         capabilities=["calc"])
    agent.on_task(lambda data, task: {"somme": data["a"] + data["b"]})
    await asyncio.sleep(1)

    cluster.kill(0)

    for _ in range(60):
        await asyncio.sleep(0.5)
        if agent.hub_url == cluster.url(1):
            break

    assert agent.hub_url == cluster.url(1), "l'agent est resté sur le Hub mort"
    await agent.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_a_re_attached_agent_is_reachable_again(cluster):
    """Rattaché ne suffit pas : il doit être *joignable*.

    Un agent reconnecté dont la présence n'aurait pas suivi serait en ligne
    sans que personne ne puisse lui parler — une panne plus insidieuse que
    la déconnexion franche.
    """
    worker = await _agent("exécutant", cluster.url(0), roles=["worker"],
                          capabilities=["calc"])
    worker.on_task(lambda data, task: {"somme": data["a"] + data["b"]})

    lead = await _agent("chef", cluster.url(1), roles=["admin"])
    await asyncio.sleep(1.5)

    cluster.kill(0)
    for _ in range(60):
        await asyncio.sleep(0.5)
        if worker.hub_url == cluster.url(1):
            break
    assert worker.hub_url == cluster.url(1)

    # Laisse la présence se republier depuis le nouveau Hub.
    await asyncio.sleep(2)
    result = await lead.submit_task("Addition", f"{ORG}/exécutant",
                                    {"a": 20, "b": 22}, timeout=25)
    assert result == {"somme": 42}

    await worker.ws.close()
    await lead.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_a_dead_hub_is_not_advertised(cluster):
    """Proposer l'adresse d'un Hub mort renverrait l'agent là où il échoue.

    C'est pour cela que la lecture est bornée par un âge : un Hub tué net
    n'a pas l'occasion de se retirer de la table.
    """
    cluster.kill(0)

    store = InterMeshStore(dsn=PG_DSN)
    try:
        # Vieillir l'entrée du Hub mort au-delà du seuil, comme le ferait
        # le temps qui passe.
        store.record_hub("hub-0", cluster.url(0), ORG, seen_at=time.time() - 600)
        fresh = [h["hub_id"] for h in store.list_hubs(org_id=ORG, max_age=45.0)]
    finally:
        store.close()

    assert "hub-0" not in fresh
    assert "hub-1" in fresh
