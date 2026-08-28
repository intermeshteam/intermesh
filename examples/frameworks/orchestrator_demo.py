"""
Orchestre un vrai agent LangChain (`langchain_agent.py`) et un agent InterMesh
natif (`examples/agent_b.py`, le calculateur) via `InterMeshPipeline`. Ce
script prouve la promesse du pilier « adaptateurs » : un `Runnable`
LangChain réel, sans une ligne de code spécifique à InterMesh dans sa propre
définition, se compose avec un agent natif exactement comme s'il en était
un.

Démarrage, dans trois terminaux :

    nexus hub
    python examples/agent_b.py
    python examples/frameworks/langchain_agent.py

Puis :

    python examples/frameworks/orchestrator_demo.py
"""

import asyncio
import os

from intermesh import InterMeshAgent, InterMeshPipeline

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


async def main():
    orchestrator = InterMeshAgent(name="orchestrator_demo", roles=["admin"], hub_url=HUB_URL)
    await orchestrator.connect()

    pipeline = (
        InterMeshPipeline(orchestrator)
        .step("Traduire", capabilities=["translate"])
        .step("Calculer", capabilities=["calculate"],
              input_fn=lambda prev: {"expression": prev["translated_text"].replace("calculer ", "").strip()})
    )

    print("\n--- PIPELINE : agent LangChain réel → agent InterMesh natif ---")
    result = await pipeline.run({"input": "execute double of twenty"})

    for s in result.history:
        print(f"🎯 {s.title} ({s.agent}) → {s.output}")
    print(f"\n✅ Résultat final : {result.output}")


if __name__ == "__main__":
    asyncio.run(main())
