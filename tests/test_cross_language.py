import asyncio
import json
import os
import subprocess
import sys
import pytest

from nexus_sdk.agent import NexusAgent


@pytest.mark.asyncio
async def test_python_to_nodejs_e2e_encrypted_workflow():
    """
    Valide le cycle complet d'orchestration chiffrée de bout en bout
    entre un orchestrateur Python et un exécutant Node.js.
    """
    port = 8850
    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    # 1. Démarrage du Hub central
    hub_proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port),
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    await asyncio.sleep(1.5)

    # 2. Démarrage de l'agent Node.js en sous-processus
    node_env = os.environ.copy()
    node_env["NEXUS_HUB_PORT"] = str(port)

    node_proc = subprocess.Popen(
        ["node", "tests/fixtures/node_worker.js"],
        env=node_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    await asyncio.sleep(1.5)

    try:
        # 3. Démarrage de l'orchestrateur Python avec chiffrement E2E activé
        orchestrator = NexusAgent(
            name="py_orchestrator",
            hub_url=f"ws://localhost:{port}",
            roles=["admin"],
            encrypt=True
        )
        await orchestrator.connect()
        await asyncio.sleep(0.5)

        # 4. Découverte de l'agent Node.js par ses capacités
        discovery = await orchestrator.discover(capabilities=["text_processing"], timeout=5.0)
        assert discovery["count"] >= 1
        discovered_agent = discovery["agents"][0]
        assert discovered_agent["name"] == "node_processor"
        assert discovered_agent["public_key"] is not None

        # 5. Requête synchrone Request/Response chiffrée
        ping_res = await orchestrator.ask("node_processor", {"ping": "hello_from_python"}, timeout=5.0)
        assert ping_res.get("pong") is True
        assert "Node.js" in ping_res.get("runtime", "")

        # 6. Délégation d'une tâche chiffrée avec charge utile internationale UTF-8
        test_payload = {
            "text": "Nexus Mesh: Interopérabilité Internationale 🌍 — 日本語, Español, Français !"
        }
        task_result = await orchestrator.submit_task(
            title="Traitement International Multi-Langages",
            assignee="node_processor",
            input_data=test_payload,
            timeout=10.0
        )

        assert task_result["status"] == "SUCCESS"
        assert task_result["original"] == test_payload["text"]
        # Vérification du résultat inversé calculé par Node.js et déchiffré par Python
        assert task_result["reversed"] == test_payload["text"][::-1]

        await orchestrator.ws.close()

    finally:
        node_proc.terminate()
        hub_proc.terminate()
        node_proc.wait()
        hub_proc.wait()
