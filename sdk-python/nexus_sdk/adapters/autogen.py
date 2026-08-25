"""
Pont AutoGen → Nexus.

    from nexus_sdk.adapters.autogen import NexusAutoGenAdapter

    agent = NexusAutoGenAdapter(
        mon_assistant,
        name="assistant",
        capabilities=["reasoning"],
        input_key="message",
    )
    await agent.connect()

AutoGen attend généralement une chaîne, pas un dict. Renseignez
`input_key` pour extraire la bonne valeur de la tâche Nexus, ou passez
un `input_adapter` pour une transformation sur mesure.

Ce module n'importe pas AutoGen : voir `nexus_sdk.adapters`.
"""

from __future__ import annotations

from typing import Any, Iterable

from nexus_sdk.adapters.base import NexusAdapter


class NexusAutoGenAdapter(NexusAdapter):
    """Expose un agent AutoGen sur le réseau Nexus."""

    def __init__(
        self,
        autogen_agent: Any,
        *,
        name: str,
        capabilities: Iterable[str] | None = None,
        input_key: str | None = "message",
        **kwargs,
    ):
        """
        Args:
            autogen_agent: `ConversableAgent`, `AssistantAgent`, équipe…
            input_key:     Clé extraite du dict de tâche, `"message"` par
                           défaut. Mettez `None` pour transmettre le dict
                           entier.
        """
        super().__init__(
            autogen_agent, name=name, capabilities=capabilities,
            input_key=input_key, **kwargs,
        )
