"""Tests du séquestre inter-agents Nexus Escrow (protocole — pas de vrai paiement)."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time

import pytest

from nexus_sdk import NexusAgent
from nexus_sdk.escrow import EscrowError, EscrowManager, InsufficientFundsError, SimulatedLedger

PORT = 8880


# ----------------------------------------------------------------------
# Unitaire : ledger et gestionnaire de séquestres, sans Hub
# ----------------------------------------------------------------------

def test_ledger_starts_at_zero_and_only_grant_creates_funds():
    ledger = SimulatedLedger()
    assert ledger.balance("acme") == 0.0
    assert ledger.debit("acme", 10.0) is False

    ledger.grant("acme", 100.0)
    assert ledger.balance("acme") == 100.0
    print("✓ Le solde ne peut naître que d'un grant explicite")


def test_hold_moves_funds_out_of_payer_immediately():
    manager = EscrowManager()
    manager.ledger.grant("acme", 100.0)

    manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=40.0)

    assert manager.ledger.balance("acme") == 60.0, "le montant séquestré quitte le solde du payeur tout de suite"
    assert manager.ledger.balance("globex") == 0.0, "le bénéficiaire n'est crédité qu'à la libération"
    print("✓ Le séquestre débite le payeur immédiatement, sans créditer le bénéficiaire")


def test_insufficient_funds_is_refused_and_nothing_moves():
    manager = EscrowManager()
    manager.ledger.grant("acme", 10.0)

    with pytest.raises(InsufficientFundsError, match="ESCROW_INSUFFICIENT_FUNDS"):
        manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=999.0)

    assert manager.ledger.balance("acme") == 10.0, "un séquestre refusé ne doit rien débiter"
    assert manager.get("t1") is None
    print("✓ Solde insuffisant : rien ne bouge")


def test_release_credits_payee_and_refund_credits_payer():
    manager = EscrowManager()
    manager.ledger.grant("acme", 100.0)
    manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=40.0)

    released = manager.release("t1")
    assert released.status.value == "released"
    assert manager.ledger.balance("globex") == 40.0
    assert manager.ledger.balance("acme") == 60.0

    manager.ledger.grant("acme", 100.0)
    manager.create_hold(task_id="t2", payer_org="acme", payee_org="globex", amount=25.0)
    refunded = manager.refund("t2")
    assert refunded.status.value == "refunded"
    assert manager.ledger.balance("acme") == 60.0 + 100.0 - 25.0 + 25.0  # rendu intégralement
    print("✓ Libération crédite le bénéficiaire, remboursement recrédite le payeur")


def test_a_resolved_hold_cannot_be_resolved_twice():
    manager = EscrowManager()
    manager.ledger.grant("acme", 100.0)
    manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=10.0)
    manager.release("t1")

    with pytest.raises(EscrowError):
        manager.release("t1")
    with pytest.raises(EscrowError):
        manager.refund("t1")
    print("✓ Un séquestre résolu ne peut pas être résolu une seconde fois")


def test_duplicate_hold_for_the_same_task_is_rejected():
    manager = EscrowManager()
    manager.ledger.grant("acme", 100.0)
    manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=10.0)

    with pytest.raises(EscrowError):
        manager.create_hold(task_id="t1", payer_org="acme", payee_org="globex", amount=5.0)
    print("✓ Un seul séquestre par tâche")


# ----------------------------------------------------------------------
# Intégration : contre un vrai Hub
# ----------------------------------------------------------------------

@pytest.fixture
def hub():
    work = tempfile.mkdtemp()
    admin_key = "nx_live_escrow_admin_key"

    with open(os.path.join(work, "api_keys.json"), "w") as f:
        json.dump({admin_key: {"org_id": "acme", "roles": ["admin", "service_account"],
                               "permissions": ["admin:*"]}}, f)
    os.chmod(os.path.join(work, "api_keys.json"), 0o600)

    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    env = {**os.environ, "NEXUS_API_KEYS_FILE": os.path.join(work, "api_keys.json")}
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


async def _connect(name, org_id="acme", api_key=None, roles=None, encrypt=False):
    agent = NexusAgent(name=name, org_id=org_id, hub_url=f"ws://localhost:{PORT}",
                       api_key=api_key, roles=roles, encrypt=encrypt)
    await agent.connect()
    return agent


@pytest.mark.asyncio
async def test_escrow_released_on_task_completion(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    await console.admin("escrow.grant", org_id="acme", amount=200.0)

    worker = await _connect("worker", org_id="globex", roles=["worker"])

    @worker.on_task
    async def _handle(input_data, task):
        return {"done": True}

    lead = await _connect("lead", org_id="acme", roles=["admin"])
    result = await lead.submit_task(
        "Audit cross-org", "globex/worker", {"x": 1},
        escrow={"amount": 100.0, "currency": "USD", "auto_release": True}, timeout=5.0,
    )
    assert result == {"done": True}

    await asyncio.sleep(0.3)  # laisse le Hub traiter le TASK_UPDATE et résoudre le séquestre

    acme_balance = await console.admin("escrow.balance", org_id="acme")
    assert acme_balance["balance"] == 100.0

    globex_balance = await console.admin("escrow.balance", org_id="globex")
    assert globex_balance["balance"] == 100.0

    await worker.ws.close()
    await lead.ws.close()
    await console.ws.close()
    print("✓ Séquestre libéré vers le bénéficiaire à la complétion de la tâche")


@pytest.mark.asyncio
async def test_escrow_insufficient_funds_rejects_the_task(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    lead = await _connect("lead", org_id="acme", roles=["admin"])  # aucun grant : solde à 0

    with pytest.raises(RuntimeError, match="ESCROW_INSUFFICIENT_FUNDS"):
        await lead.submit_task(
            "Trop cher", "globex/nobody", {"x": 1},
            escrow={"amount": 50.0, "currency": "USD"}, timeout=3.0,
        )

    audit = await console.admin("audit.list", limit=50)
    rejected = [e for e in audit["entries"] if e["event_type"] == "ESCROW_REJECTED"]
    assert rejected, "un refus de séquestre doit être tracé"

    await lead.ws.close()
    await console.ws.close()
    print("✓ Solde insuffisant : tâche refusée et tracée")


@pytest.mark.asyncio
async def test_escrow_refunded_on_task_failure(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    await console.admin("escrow.grant", org_id="acme", amount=100.0)

    worker = await _connect("worker", org_id="globex", roles=["worker"])

    @worker.on_task
    async def _fail(input_data, task):
        raise RuntimeError("Le worker a explosé en plein vol")

    lead = await _connect("lead", org_id="acme", roles=["admin"])
    with pytest.raises(Exception):
        await lead.submit_task(
            "Va échouer", "globex/worker", {"x": 1},
            escrow={"amount": 30.0, "currency": "USD"}, timeout=5.0,
        )

    await asyncio.sleep(0.3)

    acme_balance = await console.admin("escrow.balance", org_id="acme")
    assert acme_balance["balance"] == 100.0, "l'échec de la tâche doit rembourser intégralement le payeur"

    await worker.ws.close()
    await lead.ws.close()
    await console.ws.close()
    print("✓ Échec de tâche : séquestre remboursé au payeur")


@pytest.mark.asyncio
async def test_manual_release_when_auto_release_is_disabled(hub):
    console = await _connect("console", api_key=hub["admin_key"])
    await console.admin("escrow.grant", org_id="acme", amount=100.0)

    worker = await _connect("worker", org_id="globex", roles=["worker"])

    @worker.on_task
    async def _handle(input_data, task):
        return {"done": True}

    lead = await _connect("lead", org_id="acme", roles=["admin"])
    await lead.submit_task(
        "Litige possible", "globex/worker", {"x": 1},
        escrow={"amount": 20.0, "currency": "USD", "auto_release": False}, timeout=5.0,
    )
    await asyncio.sleep(0.3)

    holds = await console.admin("escrow.list")
    held = next(h for h in holds["holds"] if h["status"] == "held")
    assert held["amount"] == 20.0, "sans auto_release, le séquestre reste ouvert malgré la complétion"

    released = await console.admin("escrow.release", task_id=held["task_id"])
    assert released["status"] == "released"

    balance = await console.admin("escrow.balance", org_id="globex")
    assert balance["balance"] == 20.0

    await worker.ws.close()
    await lead.ws.close()
    await console.ws.close()
    print("✓ Libération manuelle d'un séquestre non auto-libéré")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
