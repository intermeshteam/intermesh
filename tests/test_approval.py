"""
Validation humaine : les tâches qu'un agent ne lance pas seul.

Le cas de référence est l'achat engageant : l'agent d'approvisionnement a
le droit de négocier, mais pas de signer au-delà d'un montant sans qu'une
personne ait tranché. Une règle qui correspond ne refuse pas la tâche —
elle la suspend.
"""

import json

import pytest

from intermesh.approval import (
    ApprovalPolicy, ApprovalRule, requires_approval,
)


def _policy(**kwargs) -> ApprovalPolicy:
    return ApprovalPolicy.from_dict(kwargs)


# ----------------------------------------------------------------------
# Politique vide
# ----------------------------------------------------------------------

def test_no_policy_suspends_nothing():
    assert requires_approval({"title": "n'importe quoi"}, None) is None


def test_empty_policy_suspends_nothing():
    """Un système qui retient ce qu'on ne lui a pas demandé de retenir est
    un système qu'on désactive."""
    assert requires_approval({"title": "n'importe quoi"}, ApprovalPolicy()) is None


# ----------------------------------------------------------------------
# Garde-fous de construction
# ----------------------------------------------------------------------

def test_rule_without_any_criterion_is_refused():
    """Une telle règle suspendrait tout le trafic. L'oubli est plus
    probable que l'intention."""
    with pytest.raises(ValueError, match="aucun critère"):
        ApprovalRule(name="tout", reason="raison")


def test_rule_without_reason_is_refused():
    """`reason` est ce que lit la personne qui approuve."""
    with pytest.raises(ValueError, match="reason"):
        ApprovalRule(name="x", reason="", min_cost=100)


# ----------------------------------------------------------------------
# Critères
# ----------------------------------------------------------------------

def test_cost_threshold_is_inclusive_above_and_exclusive_below():
    pol = _policy(rules=[{"name": "gros", "reason": "Montant élevé", "min_cost": 5000}])

    assert requires_approval({"estimated_cost": 5000}, pol).name == "gros"
    assert requires_approval({"estimated_cost": 5000.01}, pol).name == "gros"
    assert requires_approval({"estimated_cost": 4999.99}, pol) is None


def test_missing_or_unparsable_cost_counts_as_zero():
    """Une tâche sans coût ne doit pas franchir un seuil par accident."""
    pol = _policy(rules=[{"name": "gros", "reason": "Montant élevé", "min_cost": 1}])

    assert requires_approval({"title": "sans coût"}, pol) is None
    assert requires_approval({"estimated_cost": None}, pol) is None
    assert requires_approval({"estimated_cost": "pas un nombre"}, pol) is None


def test_pattern_matches_title_and_payload():
    """Le motif doit mordre où que soit le mot — l'intitulé n'est pas le
    seul endroit où l'engagement apparaît."""
    pol = _policy(rules=[{"name": "contrats", "reason": "Engagement", "pattern": "contrat"}])

    assert requires_approval({"title": "Signer le contrat"}, pol).name == "contrats"
    assert requires_approval(
        {"title": "ping", "input_data": {"doc": "contrat annuel"}}, pol
    ).name == "contrats"
    assert requires_approval({"title": "ping", "input_data": {"doc": "devis"}}, pol) is None


def test_pattern_is_case_insensitive():
    pol = _policy(rules=[{"name": "r", "reason": "x", "pattern": "virement"}])
    assert requires_approval({"title": "VIREMENT urgent"}, pol) is not None


def test_assignee_restriction():
    pol = _policy(rules=[{"name": "banque", "reason": "Agent sensible",
                          "assignees": ["acme/treasury"]}])

    assert requires_approval({"assignee": "acme/treasury"}, pol).name == "banque"
    assert requires_approval({"assignee": "acme/logistics"}, pol) is None


def test_cross_org_only_ignores_internal_traffic():
    pol = _policy(rules=[{"name": "sortie", "reason": "Quitte l'organisation",
                          "cross_org_only": True}])

    assert requires_approval({"title": "t"}, pol, is_cross_org=True).name == "sortie"
    assert requires_approval({"title": "t"}, pol, is_cross_org=False) is None


def test_capabilities_restriction():
    pol = _policy(rules=[{"name": "paiement", "reason": "Manipule de l'argent",
                          "capabilities": ["payments"]}])

    assert requires_approval({}, pol, capabilities=["payments"]).name == "paiement"
    assert requires_approval({}, pol, capabilities=["pricing"]) is None
    assert requires_approval({}, pol, capabilities=[]) is None


# ----------------------------------------------------------------------
# Combinaison
# ----------------------------------------------------------------------

def test_criteria_are_cumulative_not_alternative():
    """Tous les critères renseignés doivent correspondre. Une règle qui se
    déclencherait sur l'un d'eux suspendrait bien plus que voulu."""
    pol = _policy(rules=[{
        "name": "sortie-chere", "reason": "Dépense sortant de l'organisation",
        "min_cost": 1000, "cross_org_only": True,
    }])

    assert requires_approval({"estimated_cost": 5000}, pol, is_cross_org=True) is not None
    # Le montant seul ne suffit pas.
    assert requires_approval({"estimated_cost": 5000}, pol, is_cross_org=False) is None
    # Le franchissement seul non plus.
    assert requires_approval({"estimated_cost": 10}, pol, is_cross_org=True) is None


def test_first_matching_rule_wins_and_carries_its_reason():
    """C'est le motif de la règle retenue qui sera montré à l'humain."""
    pol = _policy(rules=[
        {"name": "premiere", "reason": "Motif A", "min_cost": 100},
        {"name": "seconde", "reason": "Motif B", "min_cost": 200},
    ])

    rule = requires_approval({"estimated_cost": 5000}, pol)
    assert rule.name == "premiere"
    assert rule.reason == "Motif A"


# ----------------------------------------------------------------------
# Sérialisation
# ----------------------------------------------------------------------

def test_policy_survives_a_round_trip():
    raw = {
        "name": "achats",
        "rules": [{
            "name": "engagements", "reason": "Engage l'entreprise",
            "pattern": "contrat", "min_cost": 2500,
            "assignees": ["acme/legal"], "capabilities": ["signing"],
            "cross_org_only": True,
        }],
    }
    pol = ApprovalPolicy.from_dict(json.loads(json.dumps(raw)))
    again = ApprovalPolicy.from_dict(pol.to_dict())

    assert again.name == "achats"
    assert again.rules[0].min_cost == 2500
    assert again.rules[0].cross_org_only is True
    assert again.rules[0].reason == "Engage l'entreprise"


# ----------------------------------------------------------------------
# Intégration : le verrou dans un vrai Hub
#
# Le module ci-dessus décide si une tâche doit être approuvée. Ces tests
# vérifient ce qui compte vraiment : qu'une tâche retenue n'atteint pas son
# exécutant, et qu'elle l'atteint après approbation.
# ----------------------------------------------------------------------

import asyncio
import os
import subprocess
import sys
import tempfile
import time

from intermesh import InterMeshAgent

PORT = 8853
ADMIN_KEY = "nx_live_approval_admin_key"


@pytest.fixture
def hub_with_approval():
    work = tempfile.mkdtemp()

    keys_file = os.path.join(work, "api_keys.json")
    with open(keys_file, "w") as f:
        json.dump({ADMIN_KEY: {"org_id": "acme", "roles": ["admin", "service_account"],
                               "permissions": ["admin:*"]}}, f)
    os.chmod(keys_file, 0o600)

    policy_file = os.path.join(work, "approval.json")
    with open(policy_file, "w") as f:
        # Critère textuel plutôt qu'un montant : les garde-fous Asimov
        # plafonnent le coût estimé à 100 $ par défaut et rejettent la tâche
        # avant qu'elle n'atteigne le verrou d'approbation. L'ordre est
        # voulu — refuser l'illégitime, puis suspendre le légitime — mais il
        # rend `min_cost` inobservable ici.
        json.dump({"name": "achats", "rules": [
            {"name": "engagements", "reason": "Engage l'entreprise", "pattern": "contrat"},
        ]}, f)

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    env = {**os.environ, "INTERMESH_API_KEYS_FILE": keys_file}
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--state-file", os.path.join(work, "s.db"),
         "--secret-file", os.path.join(work, "k"),
         "--approval-policy", policy_file],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
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
async def test_cheap_task_is_delivered_without_approval(hub_with_approval):
    """Sous le seuil, rien ne change : la politique ne doit pas gêner le
    trafic ordinaire."""
    executed = asyncio.Event()

    worker = await _agent("worker", roles=["worker"])
    worker.on_task(lambda d, t: executed.set() or {"ok": True})

    lead = await _agent("lead", api_key=ADMIN_KEY)
    await lead.submit_task("Petit achat de fournitures", "worker", {"x": 1}, timeout=8)

    assert executed.is_set(), "une tâche sous le seuil doit être livrée directement"
    await worker.ws.close()
    await lead.ws.close()


@pytest.mark.asyncio
async def test_expensive_task_is_held_and_never_reaches_the_worker(hub_with_approval):
    """Le point central : l'exécutant ne voit rien tant qu'un humain n'a pas
    tranché."""
    executed = asyncio.Event()

    worker = await _agent("worker", roles=["worker"])
    worker.on_task(lambda d, t: executed.set() or {"ok": True})

    lead = await _agent("lead", api_key=ADMIN_KEY)
    asyncio.create_task(
        lead.submit_task("Signer le contrat annuel", "worker", {"x": 1}, timeout=4)
    )
    await asyncio.sleep(2)

    assert not executed.is_set(), "une tâche au-dessus du seuil ne doit pas être exécutée"

    pending = await lead.admin("approvals.list")
    assert pending["count"] == 1
    entry = pending["pending"][0]
    assert entry["rule"] == "engagements"
    assert entry["reason"] == "Engage l'entreprise"
    assert entry["title"] == "Signer le contrat annuel"

    await worker.ws.close()
    await lead.ws.close()


@pytest.mark.asyncio
async def test_approval_releases_the_task_to_the_worker(hub_with_approval):
    executed = asyncio.Event()

    worker = await _agent("worker", roles=["worker"])
    worker.on_task(lambda d, t: executed.set() or {"ok": True})

    lead = await _agent("lead", api_key=ADMIN_KEY)
    asyncio.create_task(
        lead.submit_task("Signer le contrat annuel", "worker", {"x": 1}, timeout=15)
    )
    await asyncio.sleep(2)
    assert not executed.is_set()

    pending = await lead.admin("approvals.list")
    task_id = pending["pending"][0]["task_id"]
    res = await lead.admin("approval.approve", task_id=task_id)
    assert res["status"] == "approved"

    await asyncio.wait_for(executed.wait(), timeout=8)

    # La file est vidée : une tâche approuvée ne doit pas pouvoir l'être deux fois.
    assert (await lead.admin("approvals.list"))["count"] == 0

    await worker.ws.close()
    await lead.ws.close()


@pytest.mark.asyncio
async def test_denial_keeps_the_task_from_ever_running(hub_with_approval):
    executed = asyncio.Event()

    worker = await _agent("worker", roles=["worker"])
    worker.on_task(lambda d, t: executed.set() or {"ok": True})

    lead = await _agent("lead", api_key=ADMIN_KEY)
    asyncio.create_task(
        lead.submit_task("Signer le contrat annuel", "worker", {"x": 1}, timeout=4)
    )
    await asyncio.sleep(2)

    pending = await lead.admin("approvals.list")
    task_id = pending["pending"][0]["task_id"]
    res = await lead.admin("approval.deny", task_id=task_id, note="hors budget")
    assert res["status"] == "denied"
    assert res["note"] == "hors budget"

    await asyncio.sleep(1.5)
    assert not executed.is_set(), "une tâche refusée ne doit jamais s'exécuter"
    assert (await lead.admin("approvals.list"))["count"] == 0

    await worker.ws.close()
    await lead.ws.close()


@pytest.mark.asyncio
async def test_approving_an_unknown_task_is_refused(hub_with_approval):
    lead = await _agent("lead", api_key=ADMIN_KEY)
    with pytest.raises(Exception):
        await lead.admin("approval.approve", task_id="inexistant")
    await lead.ws.close()
