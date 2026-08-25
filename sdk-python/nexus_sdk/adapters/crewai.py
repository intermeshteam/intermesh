"""
Pont CrewAI → Nexus.

    from crewai import Crew
    from nexus_sdk.adapters.crewai import NexusCrewAIAdapter

    agent = NexusCrewAIAdapter(
        mon_crew,
        name="equipe_recherche",
        capabilities=["research", "synthesis"],
    )
    await agent.connect()

Un `Crew` s'invoque par `kickoff(inputs={...})` — un mot-clé, pas un
argument positionnel. La détection le sait et l'appelle correctement.

Ce module n'importe pas CrewAI : voir `nexus_sdk.adapters`.
"""

from __future__ import annotations

from typing import Any, Iterable

from nexus_sdk.adapters.base import NexusAdapter


class NexusCrewAIAdapter(NexusAdapter):
    """Expose une équipe (`Crew`) ou un agent CrewAI sur le réseau Nexus."""

    def __init__(
        self,
        crew: Any,
        *,
        name: str,
        capabilities: Iterable[str] | None = None,
        **kwargs,
    ):
        """
        Args:
            crew: Un `Crew` (invoqué par `kickoff`) ou un `Agent`
                  (invoqué par `execute_task`).

        Le dict d'entrée d'une tâche Nexus devient les `inputs` du Crew :
        les variables `{placeholders}` de vos tâches CrewAI sont donc
        remplies directement par l'orchestrateur distant.
        """
        super().__init__(crew, name=name, capabilities=capabilities, **kwargs)
