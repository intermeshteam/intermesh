"""
Identité auto-déclarée : qui a le droit de choisir ses propres rôles.

Sans clé d'API, un agent qui s'enregistre déclare lui-même son
organisation, ses rôles et ses permissions. Sur localhost c'est un confort
de développement. Depuis une adresse distante, cela signifie que quiconque
connaît l'adresse se déclare admin de n'importe quelle organisation.

Le Hub écoute toujours sur 0.0.0.0 : « exposé » ne se déduit d'aucun
réglage. La décision se prend donc par connexion, selon son origine.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest

from intermesh import InterMeshAgent
from intermesh.hub import _is_local_connection

PORT = 8861
API_KEY = "nx_live_selfdecl_test_key"


def _lan_address() -> str | None:
    """Une adresse non-loopback de cette machine, pour simuler un client distant.

    Se connecter dessus emprunte la même pile réseau, mais le Hub voit une
    adresse pair qui n'est pas 127.0.0.1 — ce qui est exactement le critère
    testé. Renvoie None sur une machine sans interface réseau.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        addr = s.getsockname()[0]
        s.close()
        return None if addr.startswith("127.") else addr
    except Exception:
        return None


LAN = _lan_address()
needs_lan = pytest.mark.skipif(not LAN, reason="aucune adresse non-loopback disponible")


class _FakeSocket:
    def __init__(self, address):
        self.remote_address = address


# ----------------------------------------------------------------------
# Reconnaissance de l'origine (unitaire)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("address,expected", [
    (("127.0.0.1", 5000), True),
    (("127.0.1.1", 5000), True),
    (("::1", 5000), True),
    (("10.0.0.5", 5000), False),
    (("203.0.113.9", 5000), False),
    (None, False),
])
def test_local_connection_detection(address, expected):
    assert _is_local_connection(_FakeSocket(address)) is expected


def test_unreadable_peer_is_treated_as_remote():
    """En cas de doute, le Hub choisit le comportement restrictif."""
    class Broken:
        @property
        def remote_address(self):
            raise RuntimeError("socket fermée")

    assert _is_local_connection(Broken()) is False


# ----------------------------------------------------------------------
# Intégration
# ----------------------------------------------------------------------

def _start_hub(port: int, *extra: str, with_keys: bool = False):
    work = tempfile.mkdtemp()
    env = dict(os.environ)

    if with_keys:
        keys = os.path.join(work, "keys.json")
        with open(keys, "w") as f:
            json.dump({API_KEY: {"org_id": "t", "roles": ["worker", "service_account"],
                                 "permissions": []}}, f)
        os.chmod(keys, 0o600)
        env["INTERMESH_API_KEYS_FILE"] = keys

    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "t",
         "--ephemeral-state", "--ephemeral-secret", *extra],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    return proc


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_localhost_may_still_self_declare():
    """Le développement local ne doit pas être gêné."""
    hub = _start_hub(PORT)
    try:
        a = InterMeshAgent(name="local", hub_url=f"ws://localhost:{PORT}",
                           roles=["admin"], encrypt=False)
        await a.connect()
        assert a.ws is not None
        await a.ws.close()
    finally:
        _stop(hub)


@needs_lan
@pytest.mark.asyncio
async def test_remote_self_declaration_is_refused_by_default():
    """Le cœur du correctif : sans clé, une connexion distante est refusée."""
    hub = _start_hub(PORT + 1)
    try:
        a = InterMeshAgent(name="intrus", hub_url=f"ws://{LAN}:{PORT + 1}",
                           roles=["admin"], encrypt=False)
        with pytest.raises(PermissionError) as exc:
            await a.connect()
        assert "SELF_DECLARED_REFUSED" in str(exc.value)
    finally:
        _stop(hub)


@needs_lan
@pytest.mark.asyncio
async def test_remote_with_a_valid_api_key_is_accepted():
    """Le refus ne vise que l'auto-déclaration, pas l'accès distant."""
    hub = _start_hub(PORT + 2, with_keys=True)
    try:
        a = InterMeshAgent(name="légitime", hub_url=f"ws://{LAN}:{PORT + 2}",
                           api_key=API_KEY, encrypt=False)
        await a.connect()
        assert a.ws is not None
        await a.ws.close()
    finally:
        _stop(hub)


@needs_lan
@pytest.mark.asyncio
async def test_allow_self_declared_reopens_remote_registration():
    """L'échappatoire existe pour un réseau privé, mais elle se déclare."""
    hub = _start_hub(PORT + 3, "--allow-self-declared")
    try:
        a = InterMeshAgent(name="privé", hub_url=f"ws://{LAN}:{PORT + 3}",
                           roles=["worker"], encrypt=False)
        await a.connect()
        assert a.ws is not None
        await a.ws.close()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_require_api_key_refuses_even_localhost():
    """Le seul réglage qui tienne derrière un reverse proxy, où toute
    connexion paraît locale."""
    hub = _start_hub(PORT + 4, "--require-api-key", with_keys=True)
    try:
        a = InterMeshAgent(name="local_sans_clé", hub_url=f"ws://localhost:{PORT + 4}",
                           roles=["admin"], encrypt=False)
        with pytest.raises(PermissionError) as exc:
            await a.connect()
        assert "SELF_DECLARED_REFUSED" in str(exc.value)

        # La même connexion locale, avec une clé, doit passer.
        b = InterMeshAgent(name="local_avec_clé", hub_url=f"ws://localhost:{PORT + 4}",
                           api_key=API_KEY, encrypt=False)
        await b.connect()
        assert b.ws is not None
        await b.ws.close()
    finally:
        _stop(hub)
