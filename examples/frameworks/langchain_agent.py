"""
Un vrai agent LangChain (chaîne LCEL prompt | llm | parser), exposé sur le
réseau Nexus via `NexusLangChainAdapter` — pas d'agent Nexus fait main
imitant un LLM, un `Runnable` LangChain réel.

Avec `OPENAI_API_KEY` défini, la chaîne appelle un vrai modèle OpenAI.
Sans clé, elle utilise `FakeListChatModel` (fourni par `langchain-core`,
pas une doublure du dépôt) pour que la démo tourne hors ligne et sans
coût : le `Runnable`, le prompt et le pont Nexus restent réels, seule la
génération de texte est déterministe.

    pip install langchain-core                 # suffit sans clé API
    pip install langchain-openai                # avec clé API

    python examples/frameworks/langchain_agent.py
"""

import asyncio
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from nexus_sdk.adapters.langchain import NexusLangChainAdapter

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


def build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Tu traduis un texte anglais vers le français, sans commentaire."),
        ("human", "{input}"),
    ])

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        print("🔑 [langchain_translator] OPENAI_API_KEY détectée — LLM réel.")
    else:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        llm = FakeListChatModel(responses=[
            "calculer 2 * 20", "calculer 5 * 5", "calculer 21 * 2",
        ])
        print("🧪 [langchain_translator] Pas de clé API — FakeListChatModel (déterministe, hors ligne).")

    return prompt | llm | StrOutputParser()


async def main():
    chain = build_chain()

    # `NexusLangChainAdapter` détecte `ainvoke`/`invoke` sur la chaîne, exécute
    # les appels synchrones hors de la boucle asyncio, et aplatit toute sortie
    # non sérialisable — voir `nexus_sdk/adapters/base.py`.
    #
    # `input_key` reste à None : le prompt attend `{"input": "..."}`, la
    # forme exacte du dict de tâche Nexus. L'extraire donnerait une chaîne
    # nue au `Runnable`, qui échouerait à résoudre la variable du template.
    agent = NexusLangChainAdapter(
        chain, name="langchain_translator", capabilities=["translate"],
        hub_url=HUB_URL,
        output_adapter=lambda text: {"translated_text": text.strip()},
    )
    await agent.connect()
    print(f"⏳ [langchain_translator] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
