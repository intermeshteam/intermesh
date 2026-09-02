"""
Authentification de la console d'exploitation.

Deux défauts se trouvaient au même endroit, dans la branche « observateur »
de l'enregistrement.

Le premier était une faille : un client qui déclarait `roles: ["observer"]`
recevait immédiatement l'inventaire des agents *et* la chaîne d'audit
complète, sans qu'aucune clé ne lui soit demandée — alors que le même client
déclaré agent était refusé. Le contrôle d'identité ne couvrait qu'une des
deux portes.

Le second rendait la console inutilisable. Elle déclare
`roles: ["admin", "observer"]` ; la branche observateur l'interceptait et lui
rendait le pseudo-jeton "observer", que `authorize()` rejette. Comme la
console sonde `hub.info` juste après connexion et abandonne si la sonde
échoue, elle ne pouvait jamais s'ouvrir — y compris dans la pile durcie.

Une console porteuse d'une clé emprunte donc le chemin agent, qui délivre un
vrai jeton signé, puis rejoint les observateurs. Les deux besoins — commander
et observer — ne s'excluent pas.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import pytest
import websockets

PORT = 8871
ADMIN_KEY = "nx_live_console_test_key"
WORKER_KEY = "nx_live_console_worker_key"


def _start_hub(port: int):
    work = tempfile.mkdtemp()
    keys = os.path.join(work, "keys.json")
    with open(keys, "w") as f:
        json.dump({ADMIN_KEY: {"org_id": "t", "roles": ["admin", "service_account"],
                               "permissions": ["admin:*"]},
                   WORKER_KEY: {"org_id": "t", "roles": ["worker", "service_account"],
                                "permissions": []}}, f)
    os.chmod(keys, 0o600)

    env = dict(os.environ)
    env["INTERMESH_API_KEYS_FILE"] = keys

    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "t",
         "--ephemeral-state", "--ephemeral-secret", "--require-api-key"],
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


async def _register(ws, api_key: str | None):
    """Reproduit exactement ce qu'envoie `dashboard/app.js` à la connexion."""
    content = {"name": "admin_console", "roles": ["admin", "observer"],
               "capabilities": ["administration"]}
    if api_key:
        content["api_key"] = api_key
    await ws.send(json.dumps({"id": str(uuid.uuid4()), "version": "intermesh/v1",
                              "type": "register", "sender": "admin_console",
                              "content": content}))

    registered = None
    for _ in range(4):
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if m.get("type") == "error":
            raise PermissionError(str(m.get("content")))
        if m.get("type") == "registered":
            registered = m.get("content") or {}
            break
    if registered is None:
        raise AssertionError("aucune réponse d'enregistrement")

    # L'instantané arrive *après* REGISTERED : un client n'installe son
    # gestionnaire définitif qu'une fois son jeton reçu.
    saw_telemetry = False
    try:
        for _ in range(3):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            if m.get("type") == "telemetry_event":
                saw_telemetry = True
                break
    except asyncio.TimeoutError:
        pass

    return registered.get("qualified_name"), registered.get("token"), saw_telemetry


async def _admin(ws, name, token, command):
    await ws.send(json.dumps({"id": str(uuid.uuid4()), "version": "intermesh/v1",
                              "type": "admin_request", "sender": name, "token": token,
                              "content": {"command": command, "params": {}}}))
    for _ in range(4):
        r = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if r.get("type") in ("admin_result", "error"):
            return r
    raise AssertionError(f"aucune réponse à {command}")


@pytest.mark.asyncio
async def test_anonymous_observer_is_refused():
    """La faille : le flux de télémétrie porte la chaîne d'audit."""
    hub = _start_hub(PORT)
    try:
        async with websockets.connect(f"ws://localhost:{PORT}") as ws:
            with pytest.raises(PermissionError) as exc:
                await _register(ws, None)
            assert "SELF_DECLARED_REFUSED" in str(exc.value)
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_observer_with_an_invalid_key_is_refused():
    hub = _start_hub(PORT + 1)
    try:
        async with websockets.connect(f"ws://localhost:{PORT + 1}") as ws:
            with pytest.raises(PermissionError) as exc:
                await _register(ws, "nx_live_pas_la_bonne")
            assert "invalide" in str(exc.value).lower()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_authenticated_console_gets_a_real_token_and_telemetry():
    """Le correctif : commander *et* observer, sur la même connexion."""
    hub = _start_hub(PORT + 2)
    try:
        async with websockets.connect(f"ws://localhost:{PORT + 2}") as ws:
            name, token, saw_telemetry = await _register(ws, ADMIN_KEY)

            # Un vrai jeton signé, pas le pseudo-jeton "observer".
            assert token != "observer"
            assert token and token.count(".") == 2

            # Et l'instantané du maillage, comme une observatrice.
            assert saw_telemetry

            # La sonde que fait la console avant de s'ouvrir.
            r = await _admin(ws, name, token, "hub.info")
            assert r["type"] == "admin_result", r.get("content")

            # Le Hub répond avec la charge utile directement dans `content` :
            # pas d'enveloppe {ok, result}. La console la lisait comme telle
            # et rejetait avec `content.error`, absent — `new Error(undefined)`
            # ayant un message vide, l'écran de connexion affichait un
            # encadré d'erreur sans rien dedans.
            assert "agents_online" in r["content"]
            assert "ok" not in r["content"]
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_a_key_without_admin_rights_is_stopped_at_the_probe():
    """La console sonde `hub.info` avant de s'ouvrir. Une clé d'exécutant
    passe l'enregistrement mais échoue là — mieux vaut le dire tout de suite
    qu'après trois clics.

    Et elle ne reçoit pas non plus le flux : déclarer `observer` ne suffit
    pas, puisque ce flux porte la chaîne d'audit."""
    hub = _start_hub(PORT + 3)
    try:
        async with websockets.connect(f"ws://localhost:{PORT + 3}") as ws:
            name, token, saw_telemetry = await _register(ws, WORKER_KEY)
            assert token and token != "observer"
            assert not saw_telemetry

            r = await _admin(ws, name, token, "hub.info")
            assert r["type"] == "error", r.get("content")
    finally:
        _stop(hub)
