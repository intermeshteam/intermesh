"""
Pont LangChain → Nexus.

    from langchain.agents import AgentExecutor
    from nexus_sdk.adapters.langchain import NexusLangChainAdapter

    agent = NexusLangChainAdapter(
        mon_agent_executor,
        name="analyste",
        capabilities=["market_analysis"],
    )
    await agent.connect()

Ce module n'importe pas LangChain : voir `nexus_sdk.adapters` pour la
raison. Il fonctionne avec tout objet respectant l'interface `Runnable`
(`invoke` / `ainvoke`), donc aussi bien un `AgentExecutor` qu'une chaîne
LCEL, un `RunnableSequence` ou un modèle de chat.
"""

from __future__ import annotations

from typing import Any, Iterable

from nexus_sdk.adapters.base import NexusAdapter


class NexusLangChainAdapter(NexusAdapter):
    """Expose une chaîne ou un agent LangChain sur le réseau Nexus."""

    def __init__(
        self,
        langchain_agent: Any,
        *,
        name: str,
        capabilities: Iterable[str] | None = None,
        input_key: str | None = None,
        **kwargs,
    ):
        """
        Args:
            langchain_agent: `AgentExecutor`, chaîne LCEL, `Runnable`…
            input_key:       Nom de la clé à extraire du dict de tâche. Les
                             `AgentExecutor` attendent typiquement
                             `{"input": "..."}`, auquel cas laissez None
                             et envoyez ce dict tel quel. Renseignez-le si
                             votre chaîne attend une chaîne de caractères.
        """
        super().__init__(
            langchain_agent, name=name, capabilities=capabilities,
            input_key=input_key, **kwargs,
        )
