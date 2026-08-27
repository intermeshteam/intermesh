"""
Un vrai agent AutoGen (`ConversableAgent`, pas un agent Nexus fait main
qui imite une conversation), exposé sur le réseau Nexus via
`NexusAutoGenAdapter`.

Comme CrewAI, AutoGen n'a pas de mode hors ligne déterministe : un
`ConversableAgent` appelle toujours un vrai LLM. `OPENAI_API_KEY` est donc
requis pour exécuter réellement une tâche.

    pip install pyautogen
    export OPENAI_API_KEY=sk-...
    python examples/frameworks/autogen_agent.py

Une tâche Nexus `{"message": "..."}` alimente directement
`generate_reply` : c'est la clé par défaut de `NexusAutoGenAdapter`, donc
aucune configuration supplémentaire n'est nécessaire côté orchestrateur.
"""

import asyncio
import os
import sys

from nexus_sdk.adapters.autogen import NexusAutoGenAdapter

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


def build_agent():
    from autogen import ConversableAgent

    return ConversableAgent(
        name="reasoning_assistant",
        system_message=(
            "Tu réponds de façon concise et factuelle, en une ou deux phrases, "
            "sans jamais demander de confirmation à l'utilisateur."
        ),
        llm_config={
            "config_list": [{"model": "gpt-4o-mini", "api_key": os.getenv("OPENAI_API_KEY")}],
        },
        human_input_mode="NEVER",
    )


async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "⚠️  [autogen_reasoner] OPENAI_API_KEY absente : l'agent se "
            "connectera, mais toute tâche déléguée échouera à l'appel du LLM.",
            file=sys.stderr,
        )

    autogen_agent = build_agent()

    # `generate_reply` attend une liste de messages, pas une chaîne nue :
    # `input_adapter` construit ce format à partir de la clé `message` du
    # dict de tâche. `NexusAutoGenAdapter` définirait par défaut
    # `input_key="message"`, insuffisant ici car la méthode veut
    # `messages=[{"role": "user", "content": "..."}]`, pas la chaîne seule.
    agent = NexusAutoGenAdapter(
        autogen_agent, name="autogen_reasoner", capabilities=["reasoning"],
        hub_url=HUB_URL,
        input_adapter=lambda data: [{"role": "user", "content": data["message"]}],
        invoke_method="generate_reply",
    )
    await agent.connect()
    print(f"⏳ [autogen_reasoner] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
