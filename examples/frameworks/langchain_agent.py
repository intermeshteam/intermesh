"""
Un vrai agent LangChain (chaîne LCEL prompt | llm | parser), exposé sur le
réseau Nexus via `from_langchain` — pas d'agent Nexus fait main
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

from nexus_sdk import from_langchain

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

    # `from_langchain` privilégie `ainvoke` s'il existe, sinon retombe sur
    # `invoke`, `run`, ou l'objet lui-même s'il est appelable. Il renvoie
    # `{"output": <résultat>, "adapter": "langchain_nexus_v1"}`.
    #
    # Le dict de tâche est transmis tel quel : le prompt attend
    # `{"input": "..."}`, la forme exacte de ce que Nexus envoie. Extraire
    # la valeur donnerait une chaîne nue au `Runnable`, qui échouerait à
    # résoudre la variable du template.
    #
    # ⚠️ Si votre chaîne n'expose que `invoke` (synchrone), `from_langchain`
    # l'appelle dans la boucle asyncio et gèle l'agent le temps de
    # l'inférence. Pour une chaîne synchrone, préférez `from_callable` avec
    # un `asyncio.to_thread`, comme dans les autres exemples de ce dossier.
    agent = from_langchain(
        chain, name="langchain_translator", capabilities=["translate"],
        hub_url=HUB_URL,
    )
    await agent.connect()
    print(f"⏳ [langchain_translator] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
