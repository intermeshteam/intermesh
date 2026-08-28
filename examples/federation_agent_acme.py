import asyncio
from intermesh import InterMeshAgent


async def main():
    # Cet agent est connecté au Hub Privé d'Acme Corp (port 8765)
    orchestrator = InterMeshAgent(
        name="lead_orchestrator",
        org_id="acme",
        capabilities=["cross_org_orchestration"],
        roles=["admin"],
        hub_url="ws://localhost:8765"
    )
    await orchestrator.connect()
    await asyncio.sleep(2)

    print("\n========================================================")
    print("   DÉBUT DU WORKFLOW INTER-ENTREPRISES (FÉDÉRATION)     ")
    print("========================================================\n")
    print("🏢 Organisation Émettrice : ACME CORP (Hub ws://localhost:8765)")
    print("🏢 Organisation Cible     : GLOBEX INC (Hub ws://localhost:8766)\n")

    # Délégation d'une tâche à travers la frontière d'organisation
    target_agent = "globex/financial_engine"
    print(f"📡 Acme délègue un calcul confidentiel à '{target_agent}' via le tunnel de fédération...")

    result = await orchestrator.submit_task(
        title="Analyse Risque Portefeuille",
        assignee=target_agent,
        input_data={"expression": "150000 * 1.08 ** 5"}
    )

    print(f"\n🎯 [Résultat obtenu de Globex Inc.] :")
    print(f"   • Valeur calculée : {result['result']:.2f} $")
    print(f"   • Exécuté par     : {result['executed_by']}")
    print("   🔒 Données chiffrées E2E à travers les deux Hubs fédérés.\n")

    print("✅ Workflow inter-entreprises validé avec succès !")


if __name__ == "__main__":
    asyncio.run(main())
