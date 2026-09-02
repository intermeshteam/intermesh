"""
Désaccord de chiffrement entre deux agents.

Trouvé en suivant le parcours de démarrage depuis un environnement neuf :
un agent configuré sans chiffrement, sollicité par un orchestrateur qui
chiffre, recevait le texte chiffré **comme s'il s'agissait de données**. Le
gestionnaire le traitait, la tâche se terminait en succès, et le résultat
était faux — « bonjour undefined » au lieu de « bonjour Adrien ».

C'est le pire mode de défaillance pour un produit dont l'argument est le
chiffrement de bout en bout : silencieux, et il produit des données fausses
plutôt qu'un échec. Un premier utilisateur tombe dessus et n'a aucun moyen
de comprendre.

Le refus est désormais explicite et porte le remède dans son message. Il ne
casse pas l'agent : la tâche est rapportée en échec, l'orchestrateur reçoit
la raison, et l'agent reste en service.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time

import pytest

from intermesh import EncryptionMismatch, InterMeshAgent
from intermesh.crypto import encrypt_for, generate_keypair, get_public_key_pem, looks_encrypted

PORT = 8920
ORG = "essai"


# ----------------------------------------------------------------------
# Reconnaissance d'une charge chiffrée (unitaire)
# ----------------------------------------------------------------------

def test_an_encrypted_payload_is_recognised():
    key = generate_keypair()
    blob = encrypt_for(get_public_key_pem(key), json.dumps({"a": 1}))
    assert looks_encrypted(blob) is True


@pytest.mark.parametrize("ordinary", [
    "bonjour",
    '{"a": 1}',
    "",
    "aGVsbG8gd29ybGQgdGVzdCBzdHJpbmcgbG9uZw==",   # base64 valide, pas une enveloppe
    None,
    42,
    {"a": 1},
])
def test_ordinary_values_are_not_mistaken_for_ciphertext(ordinary):
    """Un faux positif serait pire que le défaut corrigé : il refuserait
    des données parfaitement valides."""
    assert looks_encrypted(ordinary) is False


def test_a_json_object_with_other_keys_is_not_an_envelope():
    import base64
    payload = base64.b64encode(json.dumps({"ek": 1, "n": 2, "autre": 3}).encode()).decode()
    assert looks_encrypted(payload) is False


# ----------------------------------------------------------------------
# Déballage côté agent (unitaire, sans réseau)
# ----------------------------------------------------------------------

def _blob_for_someone_else() -> str:
    other = generate_keypair()
    return encrypt_for(get_public_key_pem(other), json.dumps({"nom": "Adrien"}))


def test_a_plain_agent_refuses_ciphertext_instead_of_passing_it_on():
    agent = InterMeshAgent(name="clair", org_id=ORG, encrypt=False)
    with pytest.raises(EncryptionMismatch) as exc:
        agent._unwrap_incoming(_blob_for_someone_else(), "Contenu de tâche")

    message = str(exc.value)
    # Le message doit porter le remède : sans lui, l'utilisateur sait que
    # quelque chose ne va pas, sans savoir quoi changer.
    assert "encrypt=False" in message
    assert "émetteur" in message


def test_a_plain_agent_still_receives_ordinary_data():
    agent = InterMeshAgent(name="clair", org_id=ORG, encrypt=False)
    assert agent._unwrap_incoming({"nom": "Adrien"}, "x") == {"nom": "Adrien"}
    assert agent._unwrap_incoming("bonjour", "x") == "bonjour"


def test_an_encrypting_agent_refuses_a_payload_meant_for_another_key():
    """Cas voisin : le chiffrement est bien actif, mais la charge a été
    chiffrée pour quelqu'un d'autre. Rendre le texte chiffré serait le même
    piège."""
    agent = InterMeshAgent(name="chiffre", org_id=ORG, encrypt=True)
    with pytest.raises(EncryptionMismatch):
        agent._unwrap_incoming(_blob_for_someone_else(), "Contenu de tâche")


def test_an_encrypting_agent_opens_its_own_payload():
    agent = InterMeshAgent(name="chiffre", org_id=ORG, encrypt=True)
    blob = encrypt_for(agent.identity.public_key, json.dumps({"nom": "Adrien"}))
    assert agent._unwrap_incoming(blob, "Contenu de tâche") == {"nom": "Adrien"}


# ----------------------------------------------------------------------
# Intégration : ce que reçoit l'orchestrateur
# ----------------------------------------------------------------------

def _start_hub(port: int):
    os.system(f"fuser -k {port}/tcp >/dev/null 2>&1")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", ORG,
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.5)
    return proc


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_the_orchestrator_learns_why_rather_than_timing_out():
    """Avant : le résultat était faux, ou l'orchestrateur attendait son
    délai sans rien apprendre. Maintenant il reçoit la raison."""
    hub = _start_hub(PORT)
    try:
        worker = InterMeshAgent(name="clair_bot", org_id=ORG, capabilities=["greet"],
                                roles=["worker"], hub_url=f"ws://localhost:{PORT}",
                                encrypt=False)
        worker.on_task(lambda data, task: {"salut": f"bonjour {data.get('nom')}"})
        await worker.connect()

        lead = InterMeshAgent(name="chef", org_id=ORG, roles=["admin"],
                              hub_url=f"ws://localhost:{PORT}", encrypt=True)
        await lead.connect()
        await asyncio.sleep(1)

        with pytest.raises(RuntimeError) as exc:
            await lead.submit_task("Saluer", f"{ORG}/clair_bot",
                                   {"nom": "Adrien"}, timeout=20)

        assert "chiffr" in str(exc.value).lower()
        # L'agent n'est pas tombé : il doit pouvoir servir la suite.
        assert worker.ws is not None

        await worker.ws.close()
        await lead.ws.close()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_agreeing_sides_are_untouched():
    """Le correctif ne doit rien changer quand les deux côtés s'accordent,
    chiffré comme en clair."""
    hub = _start_hub(PORT + 1)
    try:
        for encrypt in (True, False):
            suffix = "chiffre" if encrypt else "clair"
            worker = InterMeshAgent(name=f"w_{suffix}", org_id=ORG, capabilities=["greet"],
                                    roles=["worker"], hub_url=f"ws://localhost:{PORT + 1}",
                                    encrypt=encrypt)
            worker.on_task(lambda data, task: {"salut": f"bonjour {data['nom']}"})
            await worker.connect()

            lead = InterMeshAgent(name=f"l_{suffix}", org_id=ORG, roles=["admin"],
                                  hub_url=f"ws://localhost:{PORT + 1}", encrypt=encrypt)
            await lead.connect()
            await asyncio.sleep(1)

            result = await lead.submit_task("Saluer", f"{ORG}/w_{suffix}",
                                            {"nom": "Adrien"}, timeout=20)
            assert result == {"salut": "bonjour Adrien"}

            await worker.ws.close()
            await lead.ws.close()
    finally:
        _stop(hub)
