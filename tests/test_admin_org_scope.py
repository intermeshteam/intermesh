"""
Cloisonnement de la console d'administration par organisation.

Un Hub qui héberge plusieurs entreprises (le cas visé par un portail web
où chaque société génère ses propres clés) doit garantir qu'une clé
`org_admin` d'une entreprise ne voit ni n'agit jamais sur les agents,
tâches ou clés d'une autre — sans quoi la clé admin d'une entreprise
verrait tout ce que fait sa concurrente sur le même Hub.

`admin` reste hub-wide, inchangé : voir `test_admin.py`.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from intermesh import InterMeshAgent
from intermesh.admin import AdminError, authorize, caller_scope

PORT = 8815


# ----------------------------------------------------------------------
# Unitaire, sans Hub
# ----------------------------------------------------------------------

def test_org_admin_role_alone_is_authorized():
    authorize({"agent_name": "console_acme", "roles": ["org_admin"], "auth_method": "api_key"})
    print("✓ org_admin seul suffit à passer l'autorisation")


def test_caller_scope_is_scoped_for_org_admin_only():
    org, scoped = caller_scope({"roles": ["org_admin"], "org_id": "acme"})
    assert (org, scoped) == ("acme", True)
    print("✓ org_admin est cloisonné à son org_id")


def test_caller_scope_admin_wins_over_org_admin():
    """Un opérateur de Hub qui cumule les deux rôles reste hub-wide."""
    org, scoped = caller_scope({"roles": ["admin", "org_admin"], "org_id": "acme"})
    assert scoped is False
    print("✓ admin l'emporte sur org_admin")


def test_caller_scope_admin_alone_is_unscoped():
    org, scoped = caller_scope({"roles": ["admin"], "org_id": "acme"})
    assert scoped is False
    print("✓ admin seul reste hub-wide, comportement historique inchangé")


# ----------------------------------------------------------------------
# Intégration, deux entreprises sur un même Hub
# ----------------------------------------------------------------------

@pytest.fixture
def shared_hub():
    """
    Un seul Hub, deux entreprises : `acme` et `globex`, chacune avec sa
    propre clé `org_admin` — le scénario exact d'un portail web
    multi-tenant où chaque société génère ses clés indépendamment.
    """
    work = tempfile.mkdtemp()
    keys_file = os.path.join(work, "api_keys.json")
    acme_key = "nx_live_acme_org_admin_test_key"
    globex_key = "nx_live_globex_org_admin_test_key"
    operator_key = "nx_live_hub_operator_test_key"

    with open(keys_file, "w") as f:
        json.dump({
            acme_key: {"org_id": "acme", "roles": ["org_admin"], "permissions": ["admin:*"]},
            globex_key: {"org_id": "globex", "roles": ["org_admin"], "permissions": ["admin:*"]},
            operator_key: {"org_id": "hub_operator", "roles": ["admin"], "permissions": ["admin:*"]},
        }, f)
    os.chmod(keys_file, 0o600)

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")

    env = {**os.environ, "INTERMESH_API_KEYS_FILE": keys_file}
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "shared",
         "--state-file", os.path.join(work, "s.db"),
         "--secret-file", os.path.join(work, "k")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    import time as _t
    _t.sleep(2)

    yield {"acme_key": acme_key, "globex_key": globex_key, "operator_key": operator_key}

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


async def _connect(name, org_id="default", api_key=None, roles=None):
    agent = InterMeshAgent(name=name, org_id=org_id, hub_url=f"ws://localhost:{PORT}",
                       api_key=api_key, roles=roles, encrypt=False)
    await agent.connect()
    return agent


@pytest.mark.asyncio
async def test_org_admin_only_sees_its_own_agents(shared_hub):
    acme_worker = await _connect("worker1", org_id="acme", roles=["worker"])
    globex_worker = await _connect("worker1", org_id="globex", roles=["worker"])

    acme_console = await _connect("console", api_key=shared_hub["acme_key"])
    listing = await acme_console.admin("agents.list")
    names = {a["name"] for a in listing["agents"]}

    assert acme_worker.qualified_name in names
    assert globex_worker.qualified_name not in names, "globex ne doit jamais apparaître côté acme"

    for a in (acme_worker, globex_worker, acme_console):
        await a.ws.close()
    print("✓ org_admin ne voit que les agents de sa propre organisation")


@pytest.mark.asyncio
async def test_org_admin_cannot_disconnect_a_foreign_agent(shared_hub):
    globex_worker = await _connect("worker2", org_id="globex", roles=["worker"])
    acme_console = await _connect("console2", api_key=shared_hub["acme_key"])

    with pytest.raises(RuntimeError, match="hors de votre organisation"):
        await acme_console.admin("agent.disconnect", name=globex_worker.qualified_name)

    await globex_worker.ws.close()
    await acme_console.ws.close()
    print("✓ org_admin ne peut pas déconnecter un agent d'une autre organisation")


@pytest.mark.asyncio
async def test_org_admin_cannot_create_key_for_another_org(shared_hub):
    acme_console = await _connect("console3", api_key=shared_hub["acme_key"])

    with pytest.raises(RuntimeError, match="propre organisation"):
        await acme_console.admin("apikey.create", org_id="globex", roles=["service_account"])

    # Omettre org_id retombe silencieusement sur la sienne — pratique, pas dangereux.
    created = await acme_console.admin("apikey.create", roles=["service_account"], label="auto")
    assert created["key"].startswith("nx_live_")

    keys = await acme_console.admin("apikeys.list")
    assert all(k["org_id"] == "acme" for k in keys["keys"])

    await acme_console.ws.close()
    print("✓ org_admin ne crée des clés que pour sa propre organisation")


@pytest.mark.asyncio
async def test_org_admin_cannot_revoke_a_foreign_key(shared_hub):
    acme_console = await _connect("console4", api_key=shared_hub["acme_key"])
    globex_console = await _connect("console5", api_key=shared_hub["globex_key"])

    created = await globex_console.admin("apikey.create", roles=["service_account"], label="globex_secret")
    globex_keys = await globex_console.admin("apikeys.list")
    entry = next(k for k in globex_keys["keys"] if k["label"] == "globex_secret")

    with pytest.raises(RuntimeError, match="hors de votre organisation"):
        await acme_console.admin("apikey.revoke", fingerprint=entry["fingerprint"])

    # globex peut révoquer sa propre clé sans problème.
    revoked = await globex_console.admin("apikey.revoke", fingerprint=entry["fingerprint"])
    assert revoked["revoked"] == entry["fingerprint"]

    await acme_console.ws.close()
    await globex_console.ws.close()
    print("✓ org_admin ne révoque pas les clés d'une autre organisation")


@pytest.mark.asyncio
async def test_org_admin_only_sees_its_own_tasks_and_audit(shared_hub):
    acme_lead = await _connect("lead", org_id="acme", roles=["admin"])
    globex_lead = await _connect("lead", org_id="globex", roles=["admin"])

    for lead, org in ((acme_lead, "acme"), (globex_lead, "globex")):
        try:
            await lead.submit_task("Isolée", f"{org}/personne", {"x": 1}, timeout=1.5)
        except Exception:
            pass

    acme_console = await _connect("console6", api_key=shared_hub["acme_key"])
    tasks = await acme_console.admin("tasks.list")
    assert all("globex" not in (t["orchestrator"] + t["assignee"]) for t in tasks["tasks"])
    assert any("acme" in t["orchestrator"] for t in tasks["tasks"])

    audit = await acme_console.admin("audit.list", limit=200)
    assert all("globex" not in json.dumps(e) for e in audit["entries"])

    for a in (acme_lead, globex_lead, acme_console):
        await a.ws.close()
    print("✓ org_admin ne voit que les tâches et l'audit de sa propre organisation")


@pytest.mark.asyncio
async def test_hub_operator_admin_still_sees_everything(shared_hub):
    """`admin` reste l'opérateur du Hub : le cloisonnement ne le concerne pas."""
    acme_worker = await _connect("worker3", org_id="acme", roles=["worker"])
    globex_worker = await _connect("worker3", org_id="globex", roles=["worker"])

    operator_console = await _connect("operator", api_key=shared_hub["operator_key"])
    listing = await operator_console.admin("agents.list")
    names = {a["name"] for a in listing["agents"]}

    assert acme_worker.qualified_name in names
    assert globex_worker.qualified_name in names

    for a in (acme_worker, globex_worker, operator_console):
        await a.ws.close()
    print("✓ admin (opérateur du Hub) voit toujours toutes les organisations")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
