"""
Contre-pression : refuser explicitement quand le Hub est saturé.

Le garde-fou existant plafonne les soumissions par agent (60/minute). Il
protège d'un agent devenu fou, pas de la saturation : cent agents sages, à
un tiers de leur quota chacun, dépassent largement ce qu'un Hub soutient.

Ce que le banc de mesure a établi, et que ces tests supposent :

  * un Hub soutient environ 11 tâches/s, indépendamment du nombre d'agents ;
  * la zone saine va jusqu'à 8/s avec chiffrement, p50 sous la seconde ;
  * au-delà, le Hub acceptait tout, la latence explosait, et les clients
    mouraient sur un délai de ping — sans qu'aucun signal ne dise pourquoi.

Un refus explicite laisse à l'émetteur de quoi agir : attendre la durée
indiquée, réduire sa cadence, ou aller ailleurs. Une file qui gonfle en
silence ne lui laisse que l'ignorance.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid

import pytest
import websockets

from intermesh import InterMeshAgent
from intermesh.backpressure import BackpressureGate, BackpressureLimits

PORT = 8940
ORG = "charge"


def _gate(**kwargs) -> BackpressureGate:
    limits = BackpressureLimits(**{
        "max_tasks_per_sec": 10, "max_in_flight": 200,
        "max_queue_depth": 100, "enabled": True, **kwargs,
    })
    return BackpressureGate(limits, now=0.0)


# ----------------------------------------------------------------------
# Décision (unitaire, sans réseau ni horloge réelle)
# ----------------------------------------------------------------------

def test_a_quiet_hub_accepts():
    assert _gate().admit(in_flight=0, queue_depth=0, now=0.0) is None


def test_the_bucket_starts_full():
    """Un Hub qui vient de démarrer ne doit pas refuser la première rafale
    au motif qu'il n'a pas encore accumulé de jetons."""
    gate = _gate(max_tasks_per_sec=5)
    for _ in range(5):
        assert gate.admit(0, 0, now=0.0) is None
    assert gate.admit(0, 0, now=0.0) is not None


def test_the_rate_limit_refuses_beyond_the_budget():
    gate = _gate(max_tasks_per_sec=3)
    for _ in range(3):
        assert gate.admit(0, 0, now=0.0) is None

    refusal = gate.admit(0, 0, now=0.0)
    assert refusal is not None
    assert refusal.reason == "rate_limited"
    assert refusal.code == "HUB_SATURATED"


def test_tokens_come_back_with_time():
    gate = _gate(max_tasks_per_sec=10)
    for _ in range(10):
        gate.admit(0, 0, now=0.0)
    assert gate.admit(0, 0, now=0.0) is not None

    # Une demi-seconde rend cinq jetons.
    assert gate.admit(0, 0, now=0.5) is None


def test_the_in_flight_ceiling_refuses_even_with_tokens_left():
    """L'ordre des contrôles compte : un Hub déjà plein doit refuser même
    s'il lui reste du budget, sinon on accepte une tâche dont on sait
    déjà qu'elle attendra."""
    gate = _gate(max_in_flight=50)
    refusal = gate.admit(in_flight=50, queue_depth=0, now=0.0)
    assert refusal is not None
    assert refusal.reason == "in_flight_limit"


def test_a_full_queue_is_refused():
    gate = _gate(max_queue_depth=10)
    refusal = gate.admit(in_flight=10, queue_depth=10, now=0.0)
    assert refusal is not None
    assert refusal.reason == "task_queue_full"


def test_the_refusal_says_how_long_to_wait():
    """Réessayer aussitôt aggrave la saturation qu'on vient de rencontrer."""
    gate = _gate(max_tasks_per_sec=4)
    for _ in range(4):
        gate.admit(0, 0, now=0.0)
    refusal = gate.admit(0, 0, now=0.0)

    assert refusal.retry_after_ms > 0
    # Un jeton à 4/s revient en 250 ms.
    assert 200 <= refusal.retry_after_ms <= 300


def test_the_refusal_carries_the_numbers_an_operator_needs():
    gate = _gate(max_tasks_per_sec=2, max_in_flight=7, max_queue_depth=5)
    gate.admit(0, 0, now=0.0)
    gate.admit(0, 0, now=0.0)
    payload = gate.admit(in_flight=3, queue_depth=1, now=0.0).to_dict()

    assert payload["code"] == "HUB_SATURATED"
    assert payload["reason"] == "rate_limited"
    assert payload["in_flight"] == 3
    assert payload["queue_depth"] == 1
    assert payload["hub_tasks_per_sec_limit"] == 2
    assert payload["retry_after_ms"] > 0


def test_the_kill_switch_restores_the_old_behaviour():
    """`--no-backpressure` doit rendre le Hub d'avant : il accepte tout."""
    gate = _gate(enabled=False, max_tasks_per_sec=1, max_in_flight=1)
    for _ in range(50):
        assert gate.admit(in_flight=9999, queue_depth=9999, now=0.0) is None


def test_counters_are_kept_for_the_operator():
    gate = _gate(max_tasks_per_sec=2)
    gate.admit(0, 0, now=0.0)
    gate.admit(0, 0, now=0.0)
    gate.admit(0, 0, now=0.0)
    gate.admit(in_flight=999, queue_depth=0, now=0.0)

    snapshot = gate.snapshot(in_flight=3, queue_depth=1)
    assert snapshot["accepted_total"] == 2
    assert snapshot["rejected_total"] == 2
    assert snapshot["rejected_by_reason"]["rate_limited"] == 1
    assert snapshot["rejected_by_reason"]["in_flight_limit"] == 1
    assert snapshot["saturation"]["queue_depth_pct"] == 1


# ----------------------------------------------------------------------
# Réglages
# ----------------------------------------------------------------------

def test_limits_read_the_environment(monkeypatch):
    monkeypatch.setenv("INTERMESH_MAX_TASKS_PER_SEC", "42")
    monkeypatch.setenv("INTERMESH_MAX_TASKS_IN_FLIGHT", "7")
    monkeypatch.setenv("INTERMESH_BACKPRESSURE_ENABLED", "0")
    limits = BackpressureLimits.from_env()

    assert limits.max_tasks_per_sec == 42
    assert limits.max_in_flight == 7
    assert limits.enabled is False


def test_a_rubbish_setting_falls_back_rather_than_crashing(monkeypatch):
    """Un Hub ne doit pas refuser de démarrer parce qu'une variable
    d'environnement est mal écrite — il doit tourner avec le défaut mesuré."""
    monkeypatch.setenv("INTERMESH_MAX_TASKS_PER_SEC", "beaucoup")
    assert BackpressureLimits.from_env().max_tasks_per_sec == 10


# ----------------------------------------------------------------------
# Intégration : ce que reçoit l'émetteur
# ----------------------------------------------------------------------

ADMIN_KEY = "nx_live_backpressure_admin"


def _start_hub(port: int, *extra: str):
    import tempfile
    work = tempfile.mkdtemp()
    keys = os.path.join(work, "keys.json")
    with open(keys, "w") as handle:
        json.dump({ADMIN_KEY: {"org_id": ORG, "roles": ["admin", "service_account"],
                               "permissions": ["admin:*"]}}, handle)
    os.chmod(keys, 0o600)
    env = dict(os.environ)
    env["INTERMESH_API_KEYS_FILE"] = keys

    os.system(f"fuser -k {port}/tcp >/dev/null 2>&1")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", ORG,
         "--ephemeral-state", "--ephemeral-secret", *extra],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
async def test_a_saturated_hub_refuses_with_a_usable_message():
    """Le cœur du sujet : sous saturation, l'émetteur apprend pourquoi et
    quand réessayer, au lieu d'attendre son délai."""
    hub = _start_hub(PORT, "--max-tasks-per-sec", "2")
    try:
        worker = InterMeshAgent(name="lent", org_id=ORG, capabilities=["calc"],
                                roles=["worker"], hub_url=f"ws://localhost:{PORT}",
                                encrypt=False)
        worker.on_task(lambda data, task: {"ok": True})
        await worker.connect()

        lead = InterMeshAgent(name="chef", org_id=ORG, roles=["admin"],
                              hub_url=f"ws://localhost:{PORT}", encrypt=False)
        await lead.connect()
        await asyncio.sleep(0.5)

        # Bien au-delà du budget de 2/s, d'un coup.
        outcomes = await asyncio.gather(*[
            lead.submit_task(f"t{i}", f"{ORG}/lent", {"n": i}, timeout=8)
            for i in range(12)
        ], return_exceptions=True)

        refusals = [str(o) for o in outcomes if isinstance(o, Exception)
                    and "HUB_SATURATED" in str(o)]
        assert refusals, "le Hub doit refuser explicitement au-delà de son budget"

        # Le message doit porter de quoi agir, pas seulement « non ».
        assert any("retry_after_ms" in r or "rate_limited" in r for r in refusals)

        await worker.ws.close()
        await lead.ws.close()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_light_load_is_untouched():
    """Sous la zone saine, ni la latence ni la sémantique ne changent."""
    hub = _start_hub(PORT + 1)
    try:
        worker = InterMeshAgent(name="calc", org_id=ORG, capabilities=["calc"],
                                roles=["worker"], hub_url=f"ws://localhost:{PORT + 1}",
                                encrypt=False)
        worker.on_task(lambda data, task: {"somme": data["a"] + data["b"]})
        await worker.connect()

        lead = InterMeshAgent(name="chef2", org_id=ORG, roles=["admin"],
                              hub_url=f"ws://localhost:{PORT + 1}", encrypt=False)
        await lead.connect()
        await asyncio.sleep(0.5)

        for _ in range(5):
            result = await lead.submit_task("Addition", f"{ORG}/calc",
                                            {"a": 20, "b": 22}, timeout=15)
            assert result == {"somme": 42}
            await asyncio.sleep(0.2)

        await worker.ws.close()
        await lead.ws.close()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_the_operator_can_see_the_load():
    """Sans ce chiffre, la saturation ne se constate qu'au moment où les
    clients tombent."""
    hub = _start_hub(PORT + 2)
    try:
        async with websockets.connect(f"ws://localhost:{PORT + 2}") as ws:
            await ws.send(json.dumps({
                "id": str(uuid.uuid4()), "version": "intermesh/v1", "type": "register",
                "sender": "console", "content": {"name": "console", "api_key": ADMIN_KEY,
                                                 "roles": ["admin"], "capabilities": []},
            }))
            token = qname = None
            for _ in range(4):
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if m.get("type") == "registered":
                    token = m["content"]["token"]
                    qname = m["content"]["qualified_name"]
                    break

            await ws.send(json.dumps({
                "id": str(uuid.uuid4()), "version": "intermesh/v1",
                "type": "admin_request", "sender": qname, "token": token,
                "content": {"command": "hub.info", "params": {}},
            }))
            for _ in range(4):
                r = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert r.get("type") != "error", f"commande refusée : {r.get('content')}"
                if r.get("type") == "admin_result":
                    load = r["content"]["load"]
                    assert load["enabled"] is True
                    assert "in_flight" in load and "queue_depth" in load
                    assert load["limits"]["tasks_per_sec"] > 0
                    assert "saturation" in load
                    return
            pytest.fail("hub.info n'a pas répondu")
    finally:
        _stop(hub)
