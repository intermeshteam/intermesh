"""
Grappe : plusieurs Hubs d'une même organisation formant un ensemble.

Deux Hubs partageant une base ne se voyaient pas mutuellement leurs agents.
Un agent connecté au premier ne pouvait pas joindre un agent connecté au
second, et rien ne le signalait : le message était simplement perdu.

La table `presence` dit quel Hub détient quel agent ; le Hub qui ne trouve
pas le destinataire chez lui transporte le message vers celui qui l'a.

À ne pas confondre avec la fédération, qui franchit une frontière
d'organisation, vérifie une signature et filtre ce qui sort. Ici rien ne
sort : c'est le même tenant, réparti sur plusieurs processus.

Les tests d'intégration exigent PostgreSQL — sans base partagée il n'y a
pas de grappe. Ils sont ignorés sinon :

    export INTERMESH_TEST_PG_DSN=postgresql://postgres:pw@localhost:55434/intermesh
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time

import pytest

from intermesh import InterMeshAgent
from intermesh.store import InterMeshStore

PG_DSN = os.environ.get("INTERMESH_TEST_PG_DSN")
needs_pg = pytest.mark.skipif(not PG_DSN, reason="INTERMESH_TEST_PG_DSN non défini")

PORT_A = 8883
PORT_B = 8884


# ----------------------------------------------------------------------
# Présence (unitaire, sans Hub)
# ----------------------------------------------------------------------

def test_presence_records_which_hub_holds_an_agent():
    store = InterMeshStore(ephemeral=True)
    now = time.time()
    store.record_presence("acme/w", "hubA", "ws://a:8765", "acme", now)

    found = store.find_presence("acme/w")
    assert found["hub_id"] == "hubA"
    assert found["hub_url"] == "ws://a:8765"
    assert store.find_presence("acme/inconnu") is None
    store.close()


def test_reconnecting_elsewhere_replaces_the_previous_location():
    store = InterMeshStore(ephemeral=True)
    now = time.time()
    store.record_presence("acme/w", "hubA", "ws://a", "acme", now)
    store.record_presence("acme/w", "hubB", "ws://b", "acme", now)

    assert store.find_presence("acme/w")["hub_id"] == "hubB"
    store.close()


def test_the_previous_hub_cannot_erase_a_newer_presence():
    """Course de reconnexion.

    Un agent bascule de A vers B, puis A traite sa déconnexion. Sans la
    condition sur `hub_id`, A effacerait la présence que B vient d'écrire —
    et l'agent deviendrait injoignable alors qu'il est connecté.
    """
    store = InterMeshStore(ephemeral=True)
    now = time.time()
    store.record_presence("acme/w", "hubA", "ws://a", "acme", now)
    store.record_presence("acme/w", "hubB", "ws://b", "acme", now)

    store.clear_presence("acme/w", "hubA")          # A, en retard
    assert store.find_presence("acme/w") is not None
    assert store.find_presence("acme/w")["hub_id"] == "hubB"

    store.clear_presence("acme/w", "hubB")          # le vrai propriétaire
    assert store.find_presence("acme/w") is None
    store.close()


def test_a_stale_presence_is_not_trusted():
    """Un Hub tué net laisse ses lignes derrière lui.

    Sans péremption, les frères continueraient de lui transmettre des
    messages dans le vide.
    """
    store = InterMeshStore(ephemeral=True)
    store.record_presence("acme/fantôme", "hub-mort", "ws://x", "acme", time.time() - 300)

    assert store.find_presence("acme/fantôme") is not None      # sans limite d'âge
    assert store.find_presence("acme/fantôme", max_age=60) is None
    assert store.list_presence(max_age=60) == []
    store.close()


def test_heartbeat_keeps_a_presence_fresh():
    store = InterMeshStore(ephemeral=True)
    store.record_presence("acme/w", "hubA", "ws://a", "acme", time.time() - 300)
    assert store.find_presence("acme/w", max_age=60) is None

    store.touch_presence("hubA", time.time())
    assert store.find_presence("acme/w", max_age=60) is not None
    store.close()


def test_stopping_a_hub_clears_only_its_own_agents():
    store = InterMeshStore(ephemeral=True)
    now = time.time()
    store.record_presence("acme/a1", "hubA", "ws://a", "acme", now)
    store.record_presence("acme/a2", "hubA", "ws://a", "acme", now)
    store.record_presence("acme/b1", "hubB", "ws://b", "acme", now)

    store.clear_hub_presence("hubA")
    remaining = [p["agent_name"] for p in store.list_presence()]
    assert remaining == ["acme/b1"]
    store.close()


# ----------------------------------------------------------------------
# Intégration : deux Hubs, un message qui traverse
# ----------------------------------------------------------------------

def _start(port: int, hub_id: str, secret: str):
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "acme",
         "--hub-id", hub_id, "--state-dsn", PG_DSN, "--secret-file", secret,
         "--cluster-url", f"ws://localhost:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def cluster():
    """Deux Hubs, même organisation, même base, même clé de signature.

    La clé partagée n'est pas un détail de confort : un jeton émis par l'un
    doit être accepté par l'autre, et c'est elle qui authentifie les Hubs
    frères entre eux.
    """
    work = tempfile.mkdtemp()
    secret = os.path.join(work, "secret")

    store = InterMeshStore(dsn=PG_DSN)
    store._conn.execute("DELETE FROM presence")
    store._conn.commit()
    store.close()

    for p in (PORT_A, PORT_B):
        os.system(f"fuser -k {p}/tcp 2>/dev/null")

    a = _start(PORT_A, "hubA", secret)
    time.sleep(3)
    b = _start(PORT_B, "hubB", secret)
    time.sleep(3)
    yield
    _stop(a)
    _stop(b)


async def _agent(name: str, port: int, **kw):
    a = InterMeshAgent(name=name, org_id="acme", hub_url=f"ws://localhost:{port}",
                       encrypt=False, **kw)
    await a.connect()
    return a


@needs_pg
@pytest.mark.asyncio
async def test_presence_is_published_when_an_agent_connects(cluster):
    w = await _agent("worker", PORT_B, roles=["worker"])
    await asyncio.sleep(1)

    store = InterMeshStore(dsn=PG_DSN)
    try:
        found = store.find_presence("acme/worker")
        assert found is not None, "l'agent doit publier où le joindre"
        assert found["hub_id"] == "hubB"
    finally:
        store.close()
        await w.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_request_crosses_from_one_hub_to_the_other(cluster):
    """Le point central : sans routage, ce message était perdu en silence."""
    w = await _agent("worker", PORT_B, roles=["worker"])
    w.on_request(lambda m: {"pong": "hubB"})
    await asyncio.sleep(1.5)

    lead = await _agent("lead", PORT_A, roles=["admin"])
    reply = await lead.ask(to="acme/worker", content={"ping": 1}, timeout=20)

    assert reply == {"pong": "hubB"}
    await w.ws.close()
    await lead.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_a_full_task_completes_across_hubs(cluster):
    """Aller-retour complet : assignation d'un Hub, exécution sur l'autre,
    résultat rapporté au demandeur."""
    w = await _agent("worker", PORT_B, roles=["worker"], capabilities=["calc"])
    w.on_task(lambda d, t: {"somme": d["a"] + d["b"]})
    await asyncio.sleep(1.5)

    lead = await _agent("lead", PORT_A, roles=["admin"])
    result = await lead.submit_task("Addition", "acme/worker", {"a": 20, "b": 22}, timeout=25)

    assert result == {"somme": 42}
    await w.ws.close()
    await lead.ws.close()


@needs_pg
@pytest.mark.asyncio
async def test_presence_is_withdrawn_on_disconnect(cluster):
    w = await _agent("éphémère", PORT_B, roles=["worker"])
    await asyncio.sleep(1)
    await w.ws.close()
    await asyncio.sleep(1.5)

    store = InterMeshStore(dsn=PG_DSN)
    try:
        assert store.find_presence("acme/éphémère") is None
    finally:
        store.close()
