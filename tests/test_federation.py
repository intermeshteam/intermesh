import asyncio
import os
import sys
import subprocess

from intermesh import InterMeshAgent


async def compute_globex_handler(input_data, task):
    expr = input_data.get("expression", "0")
    print(f"📊 [Globex Private Cloud] Calcul sécurisé : {expr}")
    await asyncio.sleep(0.5)
    return {
        "result": eval(expr, {"__builtins__": None}, {}),
        "executed_by": "Globex Inc. Private Cloud"
    }


async def main():
    print("\n========================================================")
    print("   TEST AUTOMATISÉ DE FÉDÉRATION ACME ➜ GLOBEX          ")
    print("========================================================\n")

    os.system("fuser -k 8765/tcp 8766/tcp || true")
    await asyncio.sleep(0.5)

    # 1. Démarrer Hub Globex (Port 8766)
    hub_globex = subprocess.Popen([
        sys.executable, "server/hub.py", "--port", "8766", "--org", "globex",
        "--ephemeral-state", "--ephemeral-secret"
    ])
    await asyncio.sleep(1.0)

    # 2. Démarrer Hub Acme (Port 8765) peering vers Globex
    hub_acme = subprocess.Popen([
        sys.executable, "server/hub.py", "--port", "8765", "--org", "acme", "--peer", "globex=ws://localhost:8766",
        "--ephemeral-state", "--ephemeral-secret"
    ])
    await asyncio.sleep(1.5)

    try:
        # 3. Agent Globex sur Hub 8766
        agent_globex = InterMeshAgent(
            name="financial_engine",
            org_id="globex",
            capabilities=["financial_compute"],
            roles=["worker"],
            hub_url="ws://localhost:8766"
        )
        agent_globex.on_task(compute_globex_handler)
        await agent_globex.connect()
        print("✓ Agent Globex connecté sur son Hub Privé (ws://localhost:8766)")

        # 4. Agent Acme sur Hub 8765
        agent_acme = InterMeshAgent(
            name="lead_orchestrator",
            org_id="acme",
            capabilities=["orchestration"],
            roles=["admin"],
            hub_url="ws://localhost:8765"
        )
        await agent_acme.connect()
        print("✓ Agent Acme connecté sur son Hub Privé (ws://localhost:8765)")

        await asyncio.sleep(1.0)

        # 5. Soumission de tâche fédérée avec chiffrement E2E
        print("\n📡 Acme délègue la tâche 'Calcul Risque' à 'globex/financial_engine'...")
        result = await agent_acme.submit_task(
            title="Calcul Risque",
            assignee="globex/financial_engine",
            input_data={"expression": "150000 * 1.08 ** 5"},
            timeout=10.0
        )

        print("\n🎯 [Résultat reçu par Acme de Globex Inc.] :")
        print(f"   • Valeur : {result['result']:.2f} $")
        print(f"   • Exécutant : {result['executed_by']}")
        print("   🔒 Données chiffrées E2E à travers le canal de fédération.")

        assert abs(result["result"] - 220399.21) < 1.0
        print("\n✅ TEST DE FÉDÉRATION MULTI-ORGANISATIONS VALIDÉ AVEC SUCCÈS !")

        await agent_globex.ws.close()
        await agent_acme.ws.close()

    finally:
        hub_globex.terminate()
        hub_acme.terminate()


if __name__ == "__main__":
    asyncio.run(main())
