import asyncio
import os
import time
from intermesh import InterMeshAgent

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


async def main():
    # Agent de saisie automatique 24/7
    intake_agent = InterMeshAgent(
        name="data_intake",
        org_id="acme",
        capabilities=["data_entry", "invoice_parsing"],
        roles=["worker"],
        hub_url=HUB_URL
    )
    await intake_agent.connect()
    await asyncio.sleep(1)

    print("📄 [acme/data_intake] Service de Saisie 24/7 démarré.")

    # Simulation de saisie de factures en boucle 24/7
    invoice_id = 1001
    while True:
        doc_id = f"INV-2026-{invoice_id}"
        print(f"\n📥 [acme/data_intake] Nouvelle facture saisie : {doc_id}")
        print(f"➡️ [acme/data_intake] Envoi de la tâche d'impression à 'acme/print_fulfillment'...")

        try:
            result = await intake_agent.submit_task(
                title=f"Print Document {doc_id}",
                assignee="acme/print_fulfillment",
                input_data={
                    "document_id": doc_id,
                    "customer": "Acme Client Corp",
                    "amount": 4200.00,
                    "format": "PDF/A"
                },
                timeout=10.0
            )
            print(f"✅ [acme/data_intake] Confirmation d'impression reçue : {result}")
        except Exception as e:
            print(f"❌ [acme/data_intake] Erreur d'impression : {e}")

        invoice_id += 1
        await asyncio.sleep(5)  # Nouvelle saisie toutes les 5 secondes


if __name__ == "__main__":
    asyncio.run(main())
