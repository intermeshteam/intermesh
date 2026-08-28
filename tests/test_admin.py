"""Console d'administration : autorisation et commandes."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile

import pytest

from intermesh import InterMeshAgent
from intermesh.admin import AdminError, authorize

PORT = 8807


# ----------------------------------------------------------------------
# Autorisation (unitaire, sans Hub)
# ----------------------------------------------------------------------

def test_self_declared_admin_role_is_not_enough():
    """
    Le cœur du modèle : à l'enregistrement, un client choisit lui-même ses
    rôles. Si cela suffisait, n'importe qui pourrait révoquer des clés.
    """
    with pytest.raises(AdminError, match="clé d'API"):
        authorize({"agent_name": "attacker", "roles": ["admin"],
                   "auth_method": "self_declared"})
    print("✓ Rôle admin auto-déclaré refusé")


def test_api_key_without_admin_role_is_not_enough():
    with pytest.raises(AdminError, match="admin"):
        authorize({"agent_name": "worker", "roles": ["service_account"],
                   "auth_method": "api_key"})
    print("✓ Clé d'API sans rôle admin refusée")


def test_api_key_with_admin_role_is_authorized():
    authorize({"agent_name": "console", "roles": ["admin", "service_account"],
               "auth_method": "api_key"})
    print("✓ Clé d'API + rôle admin autorisés")


def test_missing_auth_method_is_refused():
    """Un token antérieur à ce champ ne doit pas ouvrir l'administration."""
    with pytest.raises(AdminError):
        authorize({"agent_name": "legacy", "roles": ["admin"]})
    print("✓ Token sans auth_method refusé")


# ----------------------------------------------------------------------
# Intégration, contre un vrai Hub
# ----------------------------------------------------------------------

@pytest.fixture
def hub():
    work = tempfile.mkdtemp()
    keys_file = os.path.join(work, "api_keys.json")
    admin_key = "nx_live_admin_console_test_key"
    worker_key = "nx_live_worker_no_admin_key"

    with open(keys_file, "w") as f:
        json.dump({
            admin_key: {"org_id": "acme", "roles": ["admin", "service_account"],
                        "permissions": ["admin:*"]},
            worker_key: {"org_id": "acme", "roles": ["service_account"],
                         "permissions": []},
        }, f)
    os.chmod(keys_file, 0o600)

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")

    env = {**os.environ, "INTERMESH_API_KEYS_FILE": keys_file}
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--state-file", os.path.join(work, "s.db"),
         "--secret-file", os.path.join(work, "k")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    import time as _t
    _t.sleep(2)

    yield {"admin_key": admin_key, "worker_key": worker_key, "work": work}

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


async def _connect(name, api_key=None, roles=None):
    agent = InterMeshAgent(name=name, hub_url=f"ws://localhost:{PORT}",
                       api_key=api_key, roles=roles, encrypt=False)
    await agent.connect()
    return agent


@pytest.mark.asyncio
async def test_hub_info_reports_live_state(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    info = await console.admin("hub.info")

    assert info["org"] == "acme"
    assert info["agents_online"] >= 1
    assert info["audit_intact"] is True
    assert info["state_ephemeral"] is False
    await console.ws.close()
    print("✓ hub.info renvoie l'état réel")


@pytest.mark.asyncio
async def test_agents_list_includes_offline_agents(hub):
    """Sans persistance, un agent déconnecté était invisible."""
    worker = await _connect("worker", roles=["worker"])
    await worker.ws.close()
    await asyncio.sleep(0.5)

    console = await _connect("console", api_key=hub["admin_key"])
    listing = await console.admin("agents.list")
    names = {a["name"]: a for a in listing["agents"]}

    assert worker.qualified_name in names
    assert names[worker.qualified_name]["online"] is False
    assert names[console.qualified_name]["online"] is True
    await console.ws.close()
    print("✓ Les agents hors ligne restent inventoriés")


@pytest.mark.asyncio
async def test_impostor_claiming_admin_is_refused(hub):
    """Un agent qui se déclare admin sans clé doit être bloqué."""
    impostor = await _connect("impostor", roles=["admin"])

    with pytest.raises(PermissionError, match="clé d'API"):
        await impostor.admin("hub.info")

    with pytest.raises(PermissionError):
        await impostor.admin("apikey.create", org_id="evil", roles=["admin"])

    await impostor.ws.close()
    print("✓ Imposteur 'admin' rejeté")


@pytest.mark.asyncio
async def test_service_account_without_admin_role_is_refused(hub):
    worker = await _connect("worker_svc", api_key=hub["worker_key"])
    with pytest.raises(PermissionError, match="admin"):
        await worker.admin("hub.info")
    await worker.ws.close()
    print("✓ Compte de service non-admin rejeté")


@pytest.mark.asyncio
async def test_apikey_lifecycle_through_the_console(hub):
    console = await _connect("console", api_key=hub["admin_key"])

    before = await console.admin("apikeys.list")
    created = await console.admin("apikey.create", org_id="globex",
                                  roles=["service_account"],
                                  permissions=["compute:execute"], label="test")

    assert created["key"].startswith("nx_live_")
    after = await console.admin("apikeys.list")
    assert len(after["keys"]) == len(before["keys"]) + 1

    # La valeur en clair n'apparaît nulle part dans l'inventaire.
    assert created["key"] not in json.dumps(after)

    new_entry = next(k for k in after["keys"] if k["label"] == "test")
    revoked = await console.admin("apikey.revoke", fingerprint=new_entry["fingerprint"])
    assert revoked["revoked"] == new_entry["fingerprint"]

    final = await console.admin("apikeys.list")
    assert len(final["keys"]) == len(before["keys"])
    await console.ws.close()
    print("✓ Création puis révocation d'une clé depuis la console")


@pytest.mark.asyncio
async def test_admin_actions_are_audited(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    await console.admin("apikey.create", org_id="audited", roles=["service_account"])

    audit = await console.admin("audit.list", limit=50)
    events = [e["event_type"] for e in audit["entries"]]

    assert "ADMIN_ACTION" in events, "toute mutation doit être tracée"
    assert audit["intact"] is True

    action = next(e for e in audit["entries"] if e["event_type"] == "ADMIN_ACTION")
    assert action["sender"] == console.qualified_name
    assert action["metadata"]["command"] == "apikey.create"
    await console.ws.close()
    print("✓ Les mutations sont auditées avec leur auteur")


@pytest.mark.asyncio
async def test_refused_admin_attempts_are_audited(hub):
    impostor = await _connect("impostor2", roles=["admin"])
    with pytest.raises(PermissionError):
        await impostor.admin("apikey.create", org_id="evil")
    await impostor.ws.close()
    await asyncio.sleep(0.3)

    console = await _connect("console", api_key=hub["admin_key"])
    audit = await console.admin("audit.list", limit=50)
    denied = [e for e in audit["entries"] if e["event_type"] == "ADMIN_DENIED"]

    assert denied, "une tentative refusée doit laisser une trace"
    assert denied[0]["sender"] == impostor.qualified_name
    await console.ws.close()
    print("✓ Les tentatives refusées sont tracées")


@pytest.mark.asyncio
async def test_task_cancel_and_audit_verify(hub):
    console = await _connect("console", api_key=hub["admin_key"])

    lead = await _connect("lead", roles=["admin"])
    try:
        await lead.submit_task("Bloquée", "acme/absent", {"x": 1}, timeout=2.0)
    except Exception:
        pass

    tasks = await console.admin("tasks.list", status="pending")
    assert tasks["total"] >= 1

    task_id = tasks["tasks"][0]["task_id"]
    cancelled = await console.admin("task.cancel", task_id=task_id)
    assert cancelled["status"] == "failed"

    verify = await console.admin("audit.verify")
    assert verify["intact"] is True
    assert verify["broken_at_index"] is None

    await lead.ws.close()
    await console.ws.close()
    print("✓ Annulation de tâche et vérification d'intégrité")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
