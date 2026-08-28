"""Tests du branchement réel des garde-fous Asimov : cost-cap, rate-limit, policy par organisation."""

import json
import os
import subprocess
import sys
import tempfile
import time

import pytest

from intermesh import InterMeshAgent
from intermesh.guardrails import AsimovGuardrailEngine, GuardrailPolicy, PolicyViolationError

PORT = 8870


# ----------------------------------------------------------------------
# Unitaire : moteur seul, sans Hub
# ----------------------------------------------------------------------

def test_cost_cap_is_actually_enforced():
    policy = GuardrailPolicy(max_cost_per_task=10.0)
    engine = AsimovGuardrailEngine(policy=policy)

    engine.validate_task_submission("agent_a", task_id="t1", estimated_cost=5.0)

    with pytest.raises(PolicyViolationError, match="TASK_COST_CAP_EXCEEDED"):
        engine.validate_task_submission("agent_a", task_id="t2", estimated_cost=50.0)
    print("✓ Plafond de coût par tâche appliqué")


def test_rate_limit_trips_after_the_configured_count():
    policy = GuardrailPolicy(max_tasks_per_minute=3)
    engine = AsimovGuardrailEngine(policy=policy)

    for i in range(3):
        engine.validate_task_submission("agent_b", task_id=f"t{i}")

    with pytest.raises(PolicyViolationError, match="RATE_LIMIT_EXCEEDED"):
        engine.validate_task_submission("agent_b", task_id="t_over")
    print("✓ Débit de tâches/minute appliqué")


def test_rejected_submission_does_not_consume_rate_quota():
    """Une tâche refusée pour une autre raison ne doit pas gaspiller le débit autorisé."""
    policy = GuardrailPolicy(max_tasks_per_minute=1, max_cost_per_task=10.0)
    engine = AsimovGuardrailEngine(policy=policy)

    with pytest.raises(PolicyViolationError, match="TASK_COST_CAP_EXCEEDED"):
        engine.validate_task_submission("agent_c", task_id="t1", estimated_cost=999.0)

    # Le quota de débit est toujours intact malgré le refus précédent.
    engine.validate_task_submission("agent_c", task_id="t2", estimated_cost=1.0)
    print("✓ Un refus ne consomme pas le quota de débit")


def test_org_policies_are_isolated():
    engine = AsimovGuardrailEngine(policy=GuardrailPolicy(max_cost_per_task=1000.0))
    engine.set_org_policy("startup_free_tier", GuardrailPolicy(max_cost_per_task=5.0))

    # L'organisation par défaut garde la policy large du Hub.
    engine.validate_task_submission("acme/worker", task_id="t1", estimated_cost=500.0, org_id="acme")

    # startup_free_tier a sa propre limite, bien plus stricte.
    with pytest.raises(PolicyViolationError, match="TASK_COST_CAP_EXCEEDED"):
        engine.validate_task_submission("startup_free_tier/worker", task_id="t2",
                                        estimated_cost=500.0, org_id="startup_free_tier")
    print("✓ Les policies par organisation sont cloisonnées")


# ----------------------------------------------------------------------
# Intégration : contre un vrai Hub
# ----------------------------------------------------------------------

@pytest.fixture
def hub():
    work = tempfile.mkdtemp()
    admin_key = "nx_live_guardrail_admin_key"

    with open(os.path.join(work, "api_keys.json"), "w") as f:
        json.dump({admin_key: {"org_id": "acme", "roles": ["admin", "service_account"],
                               "permissions": ["admin:*"]}}, f)
    os.chmod(os.path.join(work, "api_keys.json"), 0o600)

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    env = {**os.environ, "INTERMESH_API_KEYS_FILE": os.path.join(work, "api_keys.json")}
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--ephemeral-state", "--ephemeral-secret"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    yield {"admin_key": admin_key}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


async def _connect(name, api_key=None, roles=None):
    agent = InterMeshAgent(name=name, hub_url=f"ws://localhost:{PORT}", api_key=api_key, roles=roles, encrypt=False)
    await agent.connect()
    return agent


@pytest.mark.asyncio
async def test_task_over_cost_cap_is_refused_and_audited(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    await console.admin("guardrails.set_policy", max_cost_per_task=10.0)

    lead = await _connect("lead", roles=["admin"])
    with pytest.raises(RuntimeError, match="TASK_COST_CAP_EXCEEDED"):
        await lead.submit_task("Trop cher", "acme/nobody", {"x": 1}, estimated_cost=999.0, timeout=3.0)

    audit = await console.admin("audit.list", limit=50)
    events = [e for e in audit["entries"] if e["event_type"] == "ASIMOV_GUARDRAIL_VIOLATION"]
    assert events, "le refus doit être tracé dans le journal d'audit"
    assert events[0]["metadata"]["rule"] == "TASK_COST_CAP_EXCEEDED"

    await lead.ws.close()
    await console.ws.close()
    print("✓ Dépassement du plafond de coût refusé et audité")


@pytest.mark.asyncio
async def test_guardrails_policy_roundtrip_through_admin_console(hub):
    console = await _connect("console", api_key=hub["admin_key"])

    before = await console.admin("guardrails.policy")
    assert before["org_id"] == "acme"

    updated = await console.admin("guardrails.set_policy", max_tasks_per_minute=2)
    assert updated["policy"]["max_tasks_per_minute"] == 2
    # Les autres champs restent hérités, pas réinitialisés aux valeurs par défaut du dataclass.
    assert updated["policy"]["max_cascade_depth"] == before["policy"]["max_cascade_depth"]

    again = await console.admin("guardrails.policy")
    assert again["policy"]["max_tasks_per_minute"] == 2

    await console.ws.close()
    print("✓ Lecture/écriture de la policy via la console d'administration")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
