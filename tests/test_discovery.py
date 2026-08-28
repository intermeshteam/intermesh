"""
Découverte d'agents.

Régression : `server/hub.py` ne traitait pas du tout `DISCOVER`. Le
message passait la vérification de token puis traversait toutes les
branches sans être capté — aucune réponse n'était envoyée et l'appel
expirait. Seul le Hub simplifié du CLI l'implémentait, si bien que la
fonctionnalité paraissait marcher en développement et se taisait en
production.
"""

import asyncio
import os
import subprocess
import sys
import tempfile

import pytest

from intermesh import InterMeshAgent

PORT = 8811


@pytest.fixture
def hub():
    work = tempfile.mkdtemp()
    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--state-file", os.path.join(work, "s.db"),
         "--secret-file", os.path.join(work, "k")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time as _t
    _t.sleep(2)
    yield
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


async def _agent(name, **kw):
    a = InterMeshAgent(name=name, hub_url=f"ws://localhost:{PORT}", encrypt=False, **kw)
    await a.connect()
    return a


@pytest.mark.asyncio
async def test_discovery_filters(hub):
    """Un seul Hub, plusieurs critères : le filtrage doit être exact."""
    fr = await _agent("translator_fr", capabilities=["translate", "nlp"],
                      roles=["worker"], metadata={"lang": "fr", "region": "africa"})
    calc = await _agent("calculator", capabilities=["calculate"],
                        roles=["worker"], metadata={"region": "europe"})
    lead = await _agent("lead", roles=["admin"])
    await asyncio.sleep(0.6)

    # Par capacité
    r = await lead.discover(capabilities=["translate"])
    assert r["count"] == 1 and r["agents"][0]["name"] == fr.qualified_name

    # Capacités multiples : toutes exigées
    assert (await lead.discover(capabilities=["translate", "nlp"]))["count"] == 1
    assert (await lead.discover(capabilities=["translate", "calculate"]))["count"] == 0

    # Par rôle : il suffit d'un
    assert (await lead.discover(roles=["worker"]))["count"] == 2

    # Par métadonnée
    r = await lead.discover(metadata={"region": "africa"})
    assert r["count"] == 1 and r["agents"][0]["name"] == fr.qualified_name

    # Croisement capacité + métadonnée
    assert (await lead.discover(capabilities=["calculate"],
                                metadata={"region": "europe"}))["count"] == 1
    assert (await lead.discover(capabilities=["calculate"],
                                metadata={"region": "africa"}))["count"] == 0

    # Par fragment de nom
    assert (await lead.discover(name_contains="calc"))["count"] == 1

    # Une capacité inconnue ne doit rien renvoyer
    assert (await lead.discover(capabilities=["telepathy"]))["count"] == 0

    for a in (fr, calc, lead):
        await a.ws.close()
    print("✓ Filtrage par capacité, rôle, métadonnée et nom")


@pytest.mark.asyncio
async def test_discovery_exposes_public_keys_for_e2e(hub):
    """
    La découverte doit rendre la clé publique : sans elle, impossible de
    chiffrer pour un agent qu'on vient tout juste de trouver.
    """
    worker = await _agent("secure_worker", capabilities=["compute"])
    lead = await _agent("lead2", roles=["admin"])
    await asyncio.sleep(0.5)

    found = (await lead.discover(capabilities=["compute"]))["agents"][0]
    assert found["public_key"], "clé publique absente du résultat"
    assert found["public_key"].startswith("-----BEGIN PUBLIC KEY-----")

    await worker.ws.close(); await lead.ws.close()
    print("✓ La découverte fournit la clé publique")


@pytest.mark.asyncio
async def test_offline_agents_are_findable_when_asked(hub):
    """
    Le registre étant persisté, un agent déconnecté reste trouvable — à
    condition de le demander explicitement.
    """
    ghost = await _agent("ghost", capabilities=["haunting"])
    await asyncio.sleep(0.4)
    await ghost.ws.close()
    await asyncio.sleep(0.6)

    lead = await _agent("lead3", roles=["admin"])

    assert (await lead.discover(capabilities=["haunting"]))["count"] == 0

    r = await lead.discover(capabilities=["haunting"], online_only=False)
    assert r["count"] == 1
    assert r["agents"][0]["online"] is False

    await lead.ws.close()
    print("✓ Les agents hors ligne sont trouvables sur demande")


@pytest.mark.asyncio
async def test_discovery_answers_at_all(hub):
    """
    Garde-fou minimal : avant correction, cet appel expirait sans jamais
    recevoir de réponse.
    """
    a = await _agent("probe", roles=["admin"])
    r = await asyncio.wait_for(a.discover(), timeout=5.0)
    assert "agents" in r and "count" in r
    await a.ws.close()
    print("✓ Le Hub répond aux requêtes de découverte")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
