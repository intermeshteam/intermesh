"""
Identité fédérée : un Hub pair peut être vérifié, jamais usurpé.

En HS256, deux Hubs fédérés partageaient le même secret de signature :
chacun pouvait forger des jetons au nom des agents de l'autre. Ces tests
verrouillent la propriété qui remplace ce modèle — un Hub signe avec sa
clé privée Ed25519, publie sa clé publique au pairage, et ne peut pas
émettre au nom d'une organisation dont il n'a pas la clé privée.
"""

import asyncio
import os
import subprocess
import sys
import time

import jwt
import pytest
import websockets

from intermesh.message import InterMeshMessage, MessageType
from intermesh.signing import ALGORITHM, derive_signing_key, key_fingerprint, public_pem

PORT = 8823
HUB_URL = f"ws://localhost:{PORT}"


# ----------------------------------------------------------------------
# Unitaires : dérivation et non-transférabilité des clés
# ----------------------------------------------------------------------

def test_signing_key_is_deterministic_across_restarts():
    """Même secret => même clé : un redémarrage n'invalide pas les jetons."""
    first = public_pem(derive_signing_key("s" * 64))
    second = public_pem(derive_signing_key("s" * 64))

    assert first == second
    assert key_fingerprint(first) == key_fingerprint(second)


def test_distinct_secrets_yield_distinct_identities():
    acme = public_pem(derive_signing_key("acme-secret-" + "a" * 40))
    globex = public_pem(derive_signing_key("globex-secret-" + "g" * 40))

    assert acme != globex
    assert key_fingerprint(acme) != key_fingerprint(globex)


def test_a_hub_cannot_sign_for_another_organisation():
    """Le cœur du modèle : la clé publique d'Acme ne valide que la signature d'Acme."""
    acme_key = derive_signing_key("acme-secret-" + "a" * 40)
    globex_key = derive_signing_key("globex-secret-" + "g" * 40)

    # Globex forge un jeton en se réclamant d'Acme.
    forged = jwt.encode(
        {"agent_name": "acme/cfo", "iss_org": "acme", "expires_at": time.time() + 3600},
        globex_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(forged, public_pem(acme_key), algorithms=[ALGORITHM])

    # Alors que le jeton légitime d'Acme, lui, se vérifie.
    genuine = jwt.encode(
        {"agent_name": "acme/cfo", "iss_org": "acme", "expires_at": time.time() + 3600},
        acme_key,
        algorithm=ALGORITHM,
    )
    assert jwt.decode(genuine, public_pem(acme_key), algorithms=[ALGORITHM])["agent_name"] == "acme/cfo"


# ----------------------------------------------------------------------
# Intégration : le Hub applique la règle sur le lien de fédération
# ----------------------------------------------------------------------

@pytest.fixture
def hub():
    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    time.sleep(0.4)
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "globex",
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


async def _peer_as(ws, org: str, private_key) -> InterMeshMessage:
    """Réalise le pairage entrant en publiant la clé publique de `org`."""
    await ws.send(InterMeshMessage(
        type=MessageType.PEER_CONNECT, sender=org,
        content={"org": org, "public_key": public_pem(private_key)},
    ).to_json())
    return InterMeshMessage.from_json(await asyncio.wait_for(ws.recv(), timeout=5))


def _token(private_key, agent_name: str, iss_org: str) -> str:
    return jwt.encode(
        {"agent_name": agent_name, "iss_org": iss_org,
         "expires_at": time.time() + 3600},
        private_key,
        algorithm=ALGORITHM,
    )


async def _relay(ws, origin_org: str, inner: InterMeshMessage) -> InterMeshMessage | None:
    await ws.send(InterMeshMessage(
        type=MessageType.FEDERATION_RELAY, sender=origin_org, content=inner.to_dict(),
    ).to_json())
    try:
        return InterMeshMessage.from_json(await asyncio.wait_for(ws.recv(), timeout=3))
    except asyncio.TimeoutError:
        return None


@pytest.mark.asyncio
async def test_peering_without_public_key_is_refused(hub):
    """Un pairage sans clé publique rendrait les jetons invérifiables."""
    async with websockets.connect(HUB_URL) as ws:
        await ws.send(InterMeshMessage(
            type=MessageType.PEER_CONNECT, sender="evil", content={"org": "evil"},
        ).to_json())
        reply = InterMeshMessage.from_json(await asyncio.wait_for(ws.recv(), timeout=5))

    assert reply.type == MessageType.ERROR
    assert "PEER_REJECTED" in str(reply.content)


@pytest.mark.asyncio
async def test_peering_with_malformed_public_key_is_refused(hub):
    async with websockets.connect(HUB_URL) as ws:
        await ws.send(InterMeshMessage(
            type=MessageType.PEER_CONNECT, sender="evil",
            content={"org": "evil", "public_key": "-----BEGIN PUBLIC KEY-----\nnope\n"},
        ).to_json())
        reply = InterMeshMessage.from_json(await asyncio.wait_for(ws.recv(), timeout=5))

    assert reply.type == MessageType.ERROR
    assert "PEER_REJECTED" in str(reply.content)


@pytest.mark.asyncio
async def test_peer_cannot_impersonate_a_third_organisation(hub):
    """
    Un pair légitime ne doit pas pouvoir relayer un message en se réclamant
    d'une organisation tierce. C'est l'attaque que HS256 rendait triviale.
    """
    evil_key = derive_signing_key("evil-secret-" + "e" * 40)

    async with websockets.connect(HUB_URL) as ws:
        reply = await _peer_as(ws, "evil", evil_key)
        assert reply.type == MessageType.PEER_CONNECTED

        # Pairé, "evil" signe avec SA clé mais prétend parler pour "acme".
        forged = _token(evil_key, "acme/cfo", iss_org="acme")
        denied = await _relay(ws, "evil", InterMeshMessage(
            type=MessageType.WHO_IS, sender="acme/cfo", content="globex/ceo", token=forged,
        ))

    assert denied is not None, "le Hub doit répondre, pas ignorer silencieusement"
    assert denied.type == MessageType.ERROR
    assert "FEDERATION_DENIED" in str(denied.content)


@pytest.mark.asyncio
async def test_relayed_message_without_token_is_denied(hub):
    evil_key = derive_signing_key("evil-secret-" + "e" * 40)

    async with websockets.connect(HUB_URL) as ws:
        await _peer_as(ws, "evil", evil_key)
        denied = await _relay(ws, "evil", InterMeshMessage(
            type=MessageType.WHO_IS, sender="evil/scout", content="globex/ceo",
        ))

    assert denied is not None
    assert denied.type == MessageType.ERROR
    assert "FEDERATION_DENIED" in str(denied.content)


@pytest.mark.asyncio
async def test_token_signed_by_an_unrelated_key_is_denied(hub):
    """Le pair publie une clé mais signe avec une autre : rejet."""
    published = derive_signing_key("published-" + "p" * 40)
    actually_used = derive_signing_key("other-" + "o" * 40)

    async with websockets.connect(HUB_URL) as ws:
        await _peer_as(ws, "evil", published)
        denied = await _relay(ws, "evil", InterMeshMessage(
            type=MessageType.WHO_IS, sender="evil/scout", content="globex/ceo",
            token=_token(actually_used, "evil/scout", iss_org="evil"),
        ))

    assert denied is not None
    assert denied.type == MessageType.ERROR
    assert "FEDERATION_DENIED" in str(denied.content)


@pytest.mark.asyncio
async def test_expired_federated_token_is_denied(hub):
    evil_key = derive_signing_key("evil-secret-" + "e" * 40)
    expired = jwt.encode(
        {"agent_name": "evil/scout", "iss_org": "evil", "expires_at": time.time() - 1},
        evil_key, algorithm=ALGORITHM,
    )

    async with websockets.connect(HUB_URL) as ws:
        await _peer_as(ws, "evil", evil_key)
        denied = await _relay(ws, "evil", InterMeshMessage(
            type=MessageType.WHO_IS, sender="evil/scout", content="globex/ceo", token=expired,
        ))

    assert denied is not None
    assert denied.type == MessageType.ERROR
    assert "FEDERATION_DENIED" in str(denied.content)


@pytest.mark.asyncio
async def test_correctly_signed_peer_token_is_accepted(hub):
    """Contre-épreuve : un jeton correctement signé passe le contrôle.

    Sans elle, les tests ci-dessus seraient satisfaits par un Hub qui
    refuserait tout.
    """
    evil_key = derive_signing_key("evil-secret-" + "e" * 40)

    async with websockets.connect(HUB_URL) as ws:
        await _peer_as(ws, "evil", evil_key)
        answer = await _relay(ws, "evil", InterMeshMessage(
            type=MessageType.WHO_IS, sender="evil/scout", content="globex/unknown",
            token=_token(evil_key, "evil/scout", iss_org="evil"),
        ))

    # `globex/unknown` n'existe pas : le Hub ne répond rien, mais surtout
    # il ne répond pas FEDERATION_DENIED — le jeton a été accepté.
    assert answer is None or "FEDERATION_DENIED" not in str(answer.content)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
