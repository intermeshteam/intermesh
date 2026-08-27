"""
Un vrai moteur de requête LlamaIndex sur un mini-index documentaire,
exposé sur le réseau Nexus via `NexusLlamaIndexAdapter`.

Avec `OPENAI_API_KEY` défini, l'indexation et les réponses passent par de
vrais embeddings et un vrai LLM OpenAI. Sans clé, `MockEmbedding` et
`MockLLM` (fournis par `llama-index-core`, pas des doublures du dépôt)
permettent de construire et d'interroger un index réel hors ligne : le
plan vectoriel et le moteur de requête sont réels, seule la génération
finale est déterministe.

    pip install llama-index-core                      # suffit sans clé API
    pip install llama-index-llms-openai llama-index-embeddings-openai  # avec clé API

    python examples/frameworks/llamaindex_agent.py
"""

import asyncio
import os

from llama_index.core import Document, Settings, VectorStoreIndex

from nexus_sdk.adapters.llamaindex import NexusLlamaIndexAdapter

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")

DOCUMENTS = [
    "Le protocole Nexus chiffre chaque message de bout en bout avec RSA-OAEP et AES-256-GCM.",
    "Un agent Nexus se découvre par ses capacités déclarées, pas par son nom.",
    "La fédération relie deux Hubs de deux organisations différentes sans rompre le chiffrement.",
]


def build_query_engine():
    if os.getenv("OPENAI_API_KEY"):
        from llama_index.embeddings.openai import OpenAIEmbedding
        from llama_index.llms.openai import OpenAI
        Settings.embed_model = OpenAIEmbedding()
        Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
        print("🔑 [llamaindex_kb] OPENAI_API_KEY détectée — embeddings et LLM réels.")
    else:
        from llama_index.core.embeddings import MockEmbedding
        from llama_index.core.llms import MockLLM
        Settings.embed_model = MockEmbedding(embed_dim=8)
        Settings.llm = MockLLM()
        print("🧪 [llamaindex_kb] Pas de clé API — MockEmbedding/MockLLM (déterministe, hors ligne).")

    documents = [Document(text=t) for t in DOCUMENTS]
    index = VectorStoreIndex.from_documents(documents)
    return index.as_query_engine()


async def main():
    engine = build_query_engine()

    # `NexusLlamaIndexAdapter` extrait `input_key="query"` du dict de tâche
    # et reconstruit l'appel attendu par le moteur — voir
    # `nexus_sdk/adapters/llamaindex.py`.
    agent = NexusLlamaIndexAdapter(
        engine, name="llamaindex_kb", capabilities=["document_search", "rag"],
        hub_url=HUB_URL,
    )
    await agent.connect()
    print(f"⏳ [llamaindex_kb] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
