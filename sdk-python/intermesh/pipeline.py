"""
Orchestration déclarative de plusieurs agents.

`discover()` et `submit_task()` suffisent à composer un workflow, comme le
montre `examples/agent_a.py` : mais chaque enchaînement y est réécrit à la
main — chercher l'agent, soumettre, extraire le résultat, recommencer.
`InterMeshPipeline` capture ce patron une fois pour toutes, et `fan_out`
capture le cas symétrique : plusieurs agents interrogés en parallèle.

    from intermesh import InterMeshPipeline

    pipeline = (
        InterMeshPipeline(orchestrator)
        .step("Traduire", capabilities=["translate"],
              input_fn=lambda _: {"text": "Compute forty two", "target_lang": "fr"})
        .step("Calculer", capabilities=["calculate"],
              input_fn=lambda prev: {"expression": prev["translated_text"]})
    )
    result = await pipeline.run()
    print(result.output)

Ni `InterMeshPipeline` ni `fan_out` ne parlent au Hub directement : ils
délèguent à l'agent orchestrateur qui les instancie, donc à la même
identité, au même jeton, au même chiffrement que le reste du SDK.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional


class PipelineError(Exception):
    """Une étape n'a trouvé aucun agent, ou son exécution a échoué."""


@dataclass
class StepResult:
    """Trace d'une étape exécutée : utile pour déboguer un pipeline échoué."""
    title: str
    agent: str
    output: Any


@dataclass
class PipelineResult:
    """Sortie de la dernière étape, avec l'historique complet du parcours."""
    output: Any
    history: list[StepResult] = field(default_factory=list)


class _Step:
    def __init__(
        self,
        title: str,
        *,
        agent: Optional[str] = None,
        capabilities: Optional[Iterable[str]] = None,
        roles: Optional[Iterable[str]] = None,
        metadata: Optional[dict] = None,
        input_fn: Optional[Callable[[Any], Any]] = None,
        timeout: float = 15.0,
    ):
        if agent is None and not capabilities and not roles:
            raise PipelineError(
                f"Étape '{title}' : précisez `agent=` ou un critère de "
                f"découverte (`capabilities=`/`roles=`)."
            )
        self.title = title
        self.agent = agent
        self.capabilities = list(capabilities or [])
        self.roles = list(roles or [])
        self.metadata = metadata or {}
        self.input_fn = input_fn
        self.timeout = timeout


class InterMeshPipeline:
    """
    Enchaîne des tâches sur plusieurs agents, chacun trouvé par capacité
    ou nommé explicitement. La sortie d'une étape est l'entrée de la
    suivante, via `input_fn` si la forme doit changer.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._steps: list[_Step] = []

    def step(
        self,
        title: str,
        *,
        agent: Optional[str] = None,
        capabilities: Optional[Iterable[str]] = None,
        roles: Optional[Iterable[str]] = None,
        metadata: Optional[dict] = None,
        input_fn: Optional[Callable[[Any], Any]] = None,
        timeout: float = 15.0,
    ) -> "InterMeshPipeline":
        """
        Ajoute une étape et retourne le pipeline, pour enchaîner les appels.

        Args:
            title:        Titre de la tâche InterMesh, visible dans le dashboard.
            agent:        Nom exact de l'agent visé. Omis, l'agent est
                          recherché par `capabilities`/`roles` au moment de
                          l'exécution — pas à la déclaration, donc un
                          agent qui rejoint le réseau entre-temps compte.
            capabilities: Critère de découverte, toutes requises.
            roles:        Critère de découverte, un seul suffit.
            input_fn:     Reçoit la sortie de l'étape précédente (ou
                          l'entrée initiale pour la première étape) et
                          produit l'entrée de celle-ci. Par défaut, la
                          sortie précédente est transmise telle quelle.
            timeout:      Délai d'attente de cette étape, en secondes.
        """
        self._steps.append(_Step(
            title, agent=agent, capabilities=capabilities, roles=roles,
            metadata=metadata, input_fn=input_fn, timeout=timeout,
        ))
        return self

    async def _resolve_agent(self, step: _Step) -> str:
        if step.agent:
            return step.agent
        found = await self.orchestrator.discover(
            capabilities=step.capabilities, roles=step.roles, metadata=step.metadata,
        )
        if found.get("count", 0) == 0:
            raise PipelineError(
                f"Étape '{step.title}' : aucun agent disponible pour "
                f"capabilities={step.capabilities} roles={step.roles}."
            )
        return found["agents"][0]["name"]

    async def run(self, initial_input: Any = None) -> PipelineResult:
        """
        Exécute les étapes dans l'ordre déclaré, en série.

        Raises:
            PipelineError: une étape n'a trouvé aucun agent.
            TimeoutError, RuntimeError: propagées telles quelles depuis
                `submit_task` — une étape en échec interrompt le pipeline
                sans exécuter les suivantes, plutôt que de continuer sur
                une sortie invalide.
        """
        if not self._steps:
            raise PipelineError("Le pipeline n'a aucune étape.")

        result = initial_input
        history: list[StepResult] = []

        for step in self._steps:
            target = await self._resolve_agent(step)
            payload = step.input_fn(result) if step.input_fn else result
            result = await self.orchestrator.submit_task(
                step.title, target, payload, timeout=step.timeout,
            )
            history.append(StepResult(title=step.title, agent=target, output=result))

        return PipelineResult(output=result, history=history)


async def fan_out(
    orchestrator,
    branches: Iterable[tuple[str, Any]],
    *,
    capabilities: Optional[dict[str, Iterable[str]]] = None,
    agents: Optional[dict[str, str]] = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Soumet plusieurs tâches en parallèle et attend toutes les réponses.

    Le pendant du pipeline séquentiel : là où `InterMeshPipeline` enchaîne,
    `fan_out` interroge plusieurs agents à la fois — utile pour agréger
    plusieurs avis avant de trancher, ou pour paralléliser un travail
    indépendant par nature.

        results = await fan_out(
            orchestrator,
            [("marché_fr", {"region": "FR"}), ("marché_de", {"region": "DE"})],
            capabilities={"marché_fr": ["market_analysis"], "marché_de": ["market_analysis"]},
        )
        results["marché_fr"]  # sortie de la branche, ou l'exception levée

    Args:
        branches:     Paires `(clé, entrée)`. La clé identifie la branche
                      dans le résultat ; elle n'est pas envoyée à l'agent.
        capabilities: Critère de découverte par clé de branche.
        agents:       Nom d'agent exact par clé de branche. Prime sur
                      `capabilities` pour cette branche.
        timeout:      Délai d'attente, commun à toutes les branches.

    Returns:
        Un dict clé → résultat. Une branche en échec y figure comme
        l'exception levée (jamais levée elle-même) : les branches saines
        restent exploitables même si une autre a échoué.
    """
    agents = agents or {}
    capabilities = capabilities or {}

    async def _run_branch(key: str, payload: Any) -> Any:
        target = agents.get(key)
        if target is None:
            found = await orchestrator.discover(capabilities=capabilities.get(key, []))
            if found.get("count", 0) == 0:
                raise PipelineError(f"Branche '{key}' : aucun agent disponible.")
            target = found["agents"][0]["name"]
        return await orchestrator.submit_task(key, target, payload, timeout=timeout)

    keys = [k for k, _ in branches]
    results = await asyncio.gather(
        *(_run_branch(k, payload) for k, payload in branches),
        return_exceptions=True,
    )
    return dict(zip(keys, results))
