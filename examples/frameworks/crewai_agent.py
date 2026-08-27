"""
Une vraie équipe CrewAI (un `Agent` et une `Task` réels, orchestrés par un
`Crew`), exposée sur le réseau Nexus via `NexusCrewAIAdapter`.

Contrairement aux exemples LangChain/LlamaIndex de ce dossier, CrewAI n'a
pas de mode hors ligne déterministe intégré : un `Agent` appelle toujours
un vrai LLM pour raisonner. `OPENAI_API_KEY` est donc requis pour exécuter
réellement une tâche — sans clé, l'agent se connecte et se déclare tel
quel, mais toute tâche déléguée échouera à l'appel du LLM.

    pip install crewai
    export OPENAI_API_KEY=sk-...
    python examples/frameworks/crewai_agent.py

Le dict d'entrée d'une tâche Nexus alimente directement les `{placeholders}`
de la description CrewAI : `submit_task(..., {"sujet": "..."})` remplit
`{sujet}` sans code intermédiaire — voir `NexusCrewAIAdapter`.
"""

import asyncio
import os
import sys

from nexus_sdk.adapters.crewai import NexusCrewAIAdapter

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


def build_crew():
    from crewai import Agent, Crew, Task

    researcher = Agent(
        role="Analyste de protocoles d'agents IA",
        goal="Produire une synthèse factuelle et concise sur {sujet}",
        backstory=(
            "Tu es un analyste technique spécialisé dans les protocoles de "
            "coordination multi-agents. Tu écris des synthèses courtes, "
            "sans emphase ni remplissage."
        ),
        verbose=False,
    )

    task = Task(
        description="Rédige une synthèse en trois phrases sur {sujet}.",
        expected_output="Trois phrases factuelles, sans introduction ni conclusion.",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[task], verbose=False)


async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "⚠️  [crewai_research_team] OPENAI_API_KEY absente : l'agent se "
            "connectera, mais toute tâche déléguée échouera à l'appel du LLM.",
            file=sys.stderr,
        )

    crew = build_crew()

    # `NexusCrewAIAdapter` détecte `kickoff(inputs=...)` et aplatit le
    # `CrewOutput` (objet non sérialisable) en son texte via `.raw` — voir
    # `nexus_sdk/adapters/crewai.py` et `adapters/base.py::_jsonable`.
    agent = NexusCrewAIAdapter(
        crew, name="crewai_research_team", capabilities=["research", "synthesis"],
        hub_url=HUB_URL,
    )
    await agent.connect()
    print(f"⏳ [crewai_research_team] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
