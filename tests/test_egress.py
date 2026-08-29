"""
Filtrage de sortie : ce qui franchit la frontière d'organisation.

Le cas de référence est la due diligence : l'agent du vendeur transmet des
pièces financières à l'agent de l'acheteur, en retirant au passage ce qui
relève du secret industriel ou de données personnelles.
"""

import asyncio
import json
import os
import subprocess
import sys
import time

import pytest

from intermesh import InterMeshAgent
from intermesh.egress import (
    EgressBlocked, EgressPolicy, EgressRule, apply_egress,
)

PORT_SELLER = 8841
PORT_BUYER = 8842


def _policy(**kwargs) -> EgressPolicy:
    return EgressPolicy.from_dict(kwargs)


# ----------------------------------------------------------------------
# Moteur
# ----------------------------------------------------------------------

def test_empty_policy_is_a_no_op():
    payload = {"prix": 115000.0, "marge": "secret"}
    filtered, triggered = apply_egress(payload, "acme", EgressPolicy())

    assert filtered == payload
    assert triggered == []


def test_no_policy_at_all_is_a_no_op():
    assert apply_egress({"a": 1}, "acme", None) == ({"a": 1}, [])


def test_drop_removes_a_field_at_any_depth():
    policy = _policy(name="m&a", rules=[
        {"name": "no_margin", "action": "drop", "field": "marge_reelle"},
    ])
    payload = {
        "chiffre_affaires": 4_200_000,
        "marge_reelle": 0.42,
        "filiales": [{"nom": "Sud", "marge_reelle": 0.51}],
    }

    filtered, triggered = apply_egress(payload, "acme", policy)

    assert "marge_reelle" not in filtered
    assert "marge_reelle" not in filtered["filiales"][0]
    assert filtered["chiffre_affaires"] == 4_200_000
    assert triggered == ["no_margin"]


def test_redact_masks_matching_text():
    policy = _policy(name="rgpd", rules=[
        {"name": "iban", "action": "redact",
         "pattern": r"[A-Z]{2}\d{2}[A-Z0-9]{10,}", "replacement": "[IBAN]"},
    ])
    payload = {"note": "Virement vers FR7630006000011234567890189 effectué."}

    filtered, triggered = apply_egress(payload, "acme", policy)

    assert "FR7630006000011234567890189" not in filtered["note"]
    assert "[IBAN]" in filtered["note"]
    assert triggered == ["iban"]


def test_block_refuses_the_whole_payload():
    policy = _policy(name="secret", rules=[
        {"name": "classified", "action": "block", "pattern": r"SECRET[- ]DEFENSE"},
    ])

    with pytest.raises(EgressBlocked) as exc:
        apply_egress({"doc": "Mention SECRET-DEFENSE en en-tête"}, "acme", policy)

    assert exc.value.rule_name == "classified"
    assert exc.value.target_org == "acme"


def test_rules_can_target_specific_organisations():
    policy = _policy(name="ciblee", rules=[
        {"name": "only_for_acme", "action": "drop", "field": "marge",
         "to_orgs": ["acme"]},
    ])
    payload = {"marge": 0.42}

    assert apply_egress(payload, "acme", policy)[0] == {}
    assert apply_egress(payload, "globex", policy)[0] == {"marge": 0.42}


def test_triggered_rules_report_names_not_values():
    """Un journal d'audit ne doit pas devenir le lieu où fuit le secret."""
    policy = _policy(name="rgpd", rules=[
        {"name": "iban", "action": "redact", "pattern": r"FR\d{10,}"},
    ])
    _, triggered = apply_egress({"note": "FR7630006000011234567890189"}, "acme", policy)

    assert triggered == ["iban"]
    assert all("FR76" not in name for name in triggered)


def test_malformed_rules_are_rejected_at_construction():
    with pytest.raises(ValueError):
        EgressRule(name="x", action="teleport")
    with pytest.raises(ValueError):
        EgressRule(name="x", action="redact")          # pattern manquant
    with pytest.raises(ValueError):
        EgressRule(name="x", action="drop")            # field manquant


def test_policy_loads_from_file(tmp_path):
    path = tmp_path / "egress.json"
    path.write_text(json.dumps({
        "name": "due_diligence",
        "rules": [{"name": "no_margin", "action": "drop", "field": "marge"}],
    }), encoding="utf-8")

    policy = EgressPolicy.load(path)

    assert policy.name == "due_diligence"
    assert len(policy.rules) == 1
    assert apply_egress({"marge": 1}, "acme", policy)[0] == {}


# ----------------------------------------------------------------------
# Bout en bout : filtrage côté agent, chiffrement E2E actif
# ----------------------------------------------------------------------

def _start_hub(*args):
    return subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", *args,
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def federated_hubs():
    os.system(f"fuser -k {PORT_SELLER}/tcp {PORT_BUYER}/tcp 2>/dev/null")
    time.sleep(0.4)
    seller = _start_hub("--port", str(PORT_SELLER), "--org", "vendeur")
    time.sleep(1.2)
    buyer = _start_hub("--port", str(PORT_BUYER), "--org", "acheteur",
                       "--peer", f"vendeur=ws://localhost:{PORT_SELLER}")
    time.sleep(1.8)
    yield
    _stop(buyer)
    _stop(seller)


DUE_DILIGENCE = EgressPolicy.from_dict({
    "name": "due_diligence",
    "rules": [
        {"name": "no_margin", "action": "drop", "field": "marge_reelle"},
        {"name": "no_iban", "action": "redact",
         "pattern": r"FR\d{10,}", "replacement": "[IBAN]"},
    ],
})


@pytest.mark.asyncio
async def test_seller_agent_filters_before_answering_the_buyer(federated_hubs):
    """
    Le cas M&A : l'acheteur demande des pièces, le vendeur répond en
    retirant marge et IBAN. Le chiffrement E2E est actif — le filtre doit
    donc agir chez l'agent, avant chiffrement.
    """
    seller = buyer = None
    try:
        async def documents(input_data, task):
            return {
                "chiffre_affaires": 4_200_000,
                "marge_reelle": 0.42,
                "compte": "Virement sur FR7630006000011234567890189",
            }

        seller = InterMeshAgent(
            name="data_room", org_id="vendeur", capabilities=["due_diligence"],
            roles=["worker"], hub_url=f"ws://localhost:{PORT_SELLER}",
            egress_policy=DUE_DILIGENCE,
        )
        seller.on_task(documents)
        await seller.connect()

        buyer = InterMeshAgent(name="auditeur", org_id="acheteur", roles=["admin"],
                               hub_url=f"ws://localhost:{PORT_BUYER}")
        await buyer.connect()
        await asyncio.sleep(1.0)

        received = await buyer.submit_task(
            title="Pièces financières", assignee="vendeur/data_room",
            input_data={"exercice": 2025}, timeout=10.0,
        )

        assert received["chiffre_affaires"] == 4_200_000, "le chiffre autorisé doit passer"
        assert "marge_reelle" not in received, "la marge ne doit pas franchir la frontière"
        assert "FR7630006000011234567890189" not in received["compte"]
        assert "[IBAN]" in received["compte"]
    finally:
        for agent in (seller, buyer):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()


@pytest.mark.asyncio
async def test_internal_exchanges_are_not_filtered(federated_hubs):
    """
    Contre-épreuve : la politique décrit une frontière, pas une censure
    interne. Deux agents de la même organisation échangent en clair.
    """
    worker = lead = None
    try:
        async def documents(input_data, task):
            return {"marge_reelle": 0.42, "chiffre_affaires": 4_200_000}

        worker = InterMeshAgent(
            name="compta", org_id="vendeur", capabilities=["compta"], roles=["worker"],
            hub_url=f"ws://localhost:{PORT_SELLER}", egress_policy=DUE_DILIGENCE,
        )
        worker.on_task(documents)
        await worker.connect()

        lead = InterMeshAgent(name="direction", org_id="vendeur", roles=["admin"],
                              hub_url=f"ws://localhost:{PORT_SELLER}",
                              egress_policy=DUE_DILIGENCE)
        await lead.connect()
        await asyncio.sleep(0.8)

        received = await lead.submit_task(
            title="Marge interne", assignee="vendeur/compta",
            input_data={"exercice": 2025}, timeout=10.0,
        )

        assert received["marge_reelle"] == 0.42, "aucun filtrage entre agents d'une même org"
    finally:
        for agent in (worker, lead):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()


@pytest.mark.asyncio
async def test_hub_filters_when_the_agent_did_not(tmp_path):
    """
    Garde-fou : un agent sans politique ne doit pas suffire à faire sortir
    la donnée. Le Hub applique la politique de l'organisation au relais.

    Le chiffrement est désactivé ici — non pour arranger le test, mais
    parce que c'est la limite réelle : un Hub ne filtre que ce qu'il peut
    lire. Avec E2E actif, seul le filtre côté agent s'applique.
    """
    policy_file = tmp_path / "egress.json"
    policy_file.write_text(json.dumps({
        "name": "org_vendeur",
        "rules": [{"name": "no_margin", "action": "drop", "field": "marge_reelle"}],
    }), encoding="utf-8")

    os.system(f"fuser -k {PORT_SELLER}/tcp {PORT_BUYER}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)
    seller_hub = _start_hub("--port", str(PORT_SELLER), "--org", "vendeur",
                            "--egress-policy", str(policy_file))
    await asyncio.sleep(1.2)
    buyer_hub = _start_hub("--port", str(PORT_BUYER), "--org", "acheteur",
                           "--peer", f"vendeur=ws://localhost:{PORT_SELLER}")
    await asyncio.sleep(1.8)

    seller = buyer = None
    try:
        async def documents(input_data, task):
            return {"chiffre_affaires": 4_200_000, "marge_reelle": 0.42}

        # L'agent n'a AUCUNE politique : tout repose sur le Hub.
        seller = InterMeshAgent(
            name="data_room", org_id="vendeur", capabilities=["due_diligence"],
            roles=["worker"], hub_url=f"ws://localhost:{PORT_SELLER}", encrypt=False,
        )
        seller.on_task(documents)
        await seller.connect()

        buyer = InterMeshAgent(name="auditeur", org_id="acheteur", roles=["admin"],
                               hub_url=f"ws://localhost:{PORT_BUYER}", encrypt=False)
        await buyer.connect()
        await asyncio.sleep(1.0)

        received = await buyer.submit_task(
            title="Pièces financières", assignee="vendeur/data_room",
            input_data={"exercice": 2025}, timeout=10.0,
        )

        assert received["chiffre_affaires"] == 4_200_000
        assert "marge_reelle" not in received, "le Hub doit filtrer au relais"
    finally:
        for agent in (seller, buyer):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()
        _stop(buyer_hub)
        _stop(seller_hub)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
