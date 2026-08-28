"""
Une vraie équipe CrewAI (un `Agent` et une `Task` réels, orchestrés par un
`Crew`), exposée sur le réseau Nexus via `from_callable`.

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
`{sujet}`, car la fonction passée à `from_callable` transmet le dict tel
quel à `kickoff(inputs=...)`.
"""

import asyncio
import os
import sys

from nexus_sdk import from_callable

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

    # `from_callable` appelle simplement `fn(input_data)` : c'est donc à
    # nous d'adapter la convention de CrewAI, qui attend `kickoff(inputs=...)`
    # en mot-clé et renvoie un `CrewOutput` — un objet que `json.dumps`
    # refuse. On l'aplatit en son texte via `.raw`.
    #
    # `kickoff()` est synchrone et bloque plusieurs secondes (appels LLM).
    # `asyncio.to_thread` l'écarte de la boucle : sans cela, l'agent Nexus
    # serait gelé pendant toute la durée de l'appel — plus aucune tâche
    # reçue, plus aucun message routé.
    async def run_crew(input_data):
        result = await asyncio.to_thread(lambda: crew.kickoff(inputs=input_data))
        return {"output": getattr(result, "raw", str(result))}

    agent = from_callable(
        run_crew, name="crewai_research_team",
        capabilities=["research", "synthesis"], hub_url=HUB_URL,
    )
    await agent.connect()
    print(f"⏳ [crewai_research_team] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
