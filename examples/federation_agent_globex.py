import asyncio
from intermesh import InterMeshAgent


async def compute_handler(input_data, task):
    expr = input_data.get("expression", "0")
    print(f"📊 [globex/financial_engine] Traitement de calcul distant : {expr}")
    await asyncio.sleep(1)
    return {"result": eval(expr, {"__builtins__": None}, {}), "executed_by": "Globex Inc. Private Cloud"}


async def main():
    # Cet agent est connecté au Hub Privé de Globex (port 8766)
    agent = InterMeshAgent(
        name="financial_engine",
        org_id="globex",
        capabilities=["financial_compute"],
        roles=["worker"],
        hub_url="ws://localhost:8766"
    )
    agent.on_task(compute_handler)
    await agent.connect()
    print("⏳ [globex/financial_engine] Prêt sur le Hub Privé Globex...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
