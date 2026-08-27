import asyncio
import os
from nexus_sdk import NexusAgent

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


async def handle_print_task(input_data, task):
    doc_id = input_data.get("document_id", "UNKNOWN")
    customer = input_data.get("customer", "N/A")
    fmt = input_data.get("format", "PDF")

    print(f"🖨️  [acme/print_fulfillment] Réception ordre d'impression pour {doc_id} ({customer})")
    
    # Simulation du temps d'impression / génération du PDF (1.2 seconde)
    await asyncio.sleep(1.2)

    print(f"✓ [acme/print_fulfillment] Document {doc_id} généré en {fmt} & envoyé à l'imprimante.")
    return {
        "status": "PRINTED",
        "document_id": doc_id,
        "print_job_id": f"job_print_{doc_id}",
        "pages": 3
    }


async def main():
    print_agent = NexusAgent(
        name="print_fulfillment",
        org_id="acme",
        capabilities=["print_output", "pdf_generation"],
        roles=["worker"],
        hub_url=HUB_URL
    )
    print_agent.on_task(handle_print_task)
    
    await print_agent.connect()
    print("⏳ [acme/print_fulfillment] Service d'Impression 24/7 prêt...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
