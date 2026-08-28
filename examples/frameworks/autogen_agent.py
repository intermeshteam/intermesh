"""
Un vrai agent AutoGen (`ConversableAgent`, pas un agent Nexus fait main
qui imite une conversation), exposé sur le réseau Nexus via
`from_callable`.

Comme CrewAI, AutoGen n'a pas de mode hors ligne déterministe : un
`ConversableAgent` appelle toujours un vrai LLM. `OPENAI_API_KEY` est donc
requis pour exécuter réellement une tâche.

    pip install pyautogen
    export OPENAI_API_KEY=sk-...
    python examples/frameworks/autogen_agent.py

Une tâche Nexus `{"message": "..."}` alimente `generate_reply` : la
fonction passée à `from_callable` lit la clé `message` et la reformate en
`[{"role": "user", "content": ...}]`, la forme attendue par AutoGen.
"""

import asyncio
import os
import sys

from nexus_sdk import from_callable

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
    # on construit ce format à partir de la clé `message` du dict de tâche.
    #
    # L'appel est synchrone et bloque le temps de la réponse du LLM.
    # `asyncio.to_thread` l'écarte de la boucle, sans quoi l'agent Nexus
    # cesserait de répondre pendant toute la durée de l'inférence.
    async def run_autogen(input_data):
        messages = [{"role": "user", "content": input_data["message"]}]
        result = await asyncio.to_thread(
            lambda: autogen_agent.generate_reply(messages=messages)
        )
        return {"output": result if isinstance(result, str) else str(result)}

    agent = from_callable(
        run_autogen, name="autogen_reasoner",
        capabilities=["reasoning"], hub_url=HUB_URL,
    )
    await agent.connect()
    print(f"⏳ [autogen_reasoner] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
