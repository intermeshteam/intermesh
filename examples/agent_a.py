import asyncio
from nexus_sdk import NexusAgent


async def main():
    orchestrator = NexusAgent(name="agent_a", capabilities=["orchestration"], roles=["admin"])
    await orchestrator.connect()
    await asyncio.sleep(2)

    print("\n--- WORKFLOW NEXUS ---")

    # Étape 1 : Traduction
    d = await orchestrator.discover(capabilities=["translate"])
    if d["count"] == 0:
        print("❌ Traducteur introuvable"); return
    tr = d["agents"][0]["name"]
    r1 = await orchestrator.submit_task("Traduire", tr, {"text": "Execute double of twenty", "target_lang": "fr"})
    translated = r1["translated_text"]
    print(f"🎯 Traduction : '{translated}'")

    # Étape 2 : Calcul
    d2 = await orchestrator.discover(capabilities=["calculate"])
    if d2["count"] == 0:
        print("❌ Calculateur introuvable"); return
    calc = d2["agents"][0]["name"]
    expr = translated.replace("calculer ", "").strip()
    r2 = await orchestrator.submit_task("Calculer", calc, {"expression": expr})
    print(f"🎯 Résultat : {r2['result']}")

    print("\n✅ Workflow terminé !")


if __name__ == "__main__":
    asyncio.run(main())
