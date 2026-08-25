"""
Pont LlamaIndex → Nexus.

    from nexus_sdk.adapters.llamaindex import NexusLlamaIndexAdapter

    agent = NexusLlamaIndexAdapter(
        index.as_query_engine(),
        name="base_documentaire",
        capabilities=["document_search", "rag"],
    )
    await agent.connect()

Un moteur de requête attend une chaîne : `input_key` vaut `"query"` par
défaut, de sorte qu'une tâche `{"query": "..."}` fonctionne directement.

Ce module n'importe pas LlamaIndex : voir `nexus_sdk.adapters`.
"""

from __future__ import annotations

from typing import Any, Iterable

from nexus_sdk.adapters.base import NexusAdapter


class NexusLlamaIndexAdapter(NexusAdapter):
    """Expose un moteur de requête ou de chat LlamaIndex sur le réseau Nexus."""

    def __init__(
        self,
        engine: Any,
        *,
        name: str,
        capabilities: Iterable[str] | None = None,
        input_key: str | None = "query",
        **kwargs,
    ):
        """
        Args:
            engine:    Résultat de `index.as_query_engine()`,
                       `as_chat_engine()`, ou un agent LlamaIndex.
            input_key: Clé extraite du dict de tâche, `"query"` par défaut.
        """
        super().__init__(
            engine, name=name, capabilities=capabilities,
            input_key=input_key, **kwargs,
        )
