"""Cœur des adaptateurs : détection de la convention d'appel et pontage."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Callable, Iterable

from nexus_sdk.agent import NexusAgent


class AdapterError(Exception):
    """L'objet fourni n'expose aucune manière reconnaissable d'être appelé."""


# Méthodes d'invocation connues, par ordre de préférence. Les variantes
# asynchrones passent d'abord : si le framework en propose une, l'utiliser
# évite de mobiliser un thread pour rien.
#
#   "single"     -> methode(entrée)
#   "inputs_kw"  -> methode(inputs=entrée)      (CrewAI Crew.kickoff)
_INVOKERS: tuple[tuple[str, bool, str], ...] = (
    ("ainvoke",        True,  "single"),     # LangChain Runnable
    ("kickoff_async",  True,  "inputs_kw"),  # CrewAI Crew
    ("arun",           True,  "single"),     # LangChain historique
    ("a_run",          True,  "single"),     # AutoGen
    ("acall",          True,  "single"),
    ("aquery",         True,  "single"),     # LlamaIndex
    ("achat",          True,  "single"),
    ("invoke",         False, "single"),     # LangChain Runnable
    ("kickoff",        False, "inputs_kw"),  # CrewAI Crew
    ("run",            False, "single"),     # AutoGen, LangChain historique
    ("execute_task",   False, "single"),     # CrewAI Agent
    ("generate_reply", False, "single"),     # AutoGen ConversableAgent
    ("query",          False, "single"),     # LlamaIndex
    ("chat",           False, "single"),
    ("predict",        False, "single"),
)

# Attributs où les frameworks rangent le texte utile de leur objet de
# sortie, quand celui-ci n'est pas directement sérialisable.
_OUTPUT_ATTRS = ("raw", "content", "output", "text", "result", "response", "answer")


def detect_invoker(obj: Any, prefer: str | None = None) -> tuple[Callable, bool, str]:
    """
    Trouve comment appeler `obj`.

    Args:
        obj:    Agent, chaîne, équipe ou simple fonction.
        prefer: Nom de méthode à privilégier, si la détection se trompe.

    Returns:
        (appelable, est_asynchrone, style)

    Raises:
        AdapterError: aucune méthode reconnue et l'objet n'est pas appelable.
    """
    if prefer:
        fn = getattr(obj, prefer, None)
        if not callable(fn):
            raise AdapterError(f"'{prefer}' n'existe pas ou n'est pas appelable sur {type(obj).__name__}.")
        style = next((s for n, _, s in _INVOKERS if n == prefer), "single")
        return fn, inspect.iscoroutinefunction(fn), style

    for name, is_async, style in _INVOKERS:
        fn = getattr(obj, name, None)
        if callable(fn):
            # `inspect` fait autorité : un framework peut exposer `invoke`
            # en asynchrone, ou l'inverse.
            return fn, inspect.iscoroutinefunction(fn), style

    if callable(obj):
        return obj, inspect.iscoroutinefunction(obj), "single"

    raise AdapterError(
        f"{type(obj).__name__} n'expose aucune méthode d'invocation connue "
        f"({', '.join(n for n, _, _ in _INVOKERS)}) et n'est pas appelable. "
        f"Précisez-la avec invoke_method='...'."
    )


def _jsonable(value: Any) -> Any:
    """
    Ramène une sortie de framework à quelque chose qui passe sur le fil.

    Les résultats sont souvent des objets riches — `AIMessage`, `CrewOutput`,
    `Response` — que `json.dumps` refuse. Plutôt que d'échouer, on cherche
    l'attribut porteur du texte, puis on se rabat sur `str()`.
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        pass

    for attr in _OUTPUT_ATTRS:
        if hasattr(value, attr):
            inner = getattr(value, attr)
            if not callable(inner):
                return _jsonable(inner)

    if hasattr(value, "model_dump"):          # Pydantic v2
        try:
            return _jsonable(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "dict") and callable(getattr(value, "dict")):   # Pydantic v1
        try:
            return _jsonable(value.dict())
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]

    return str(value)


class NexusAdapter(NexusAgent):
    """
    Un `NexusAgent` dont le travail est délégué à un agent étranger.

    S'utilise exactement comme un agent Nexus natif : il se connecte,
    se fait découvrir par ses capacités, reçoit des tâches et des
    requêtes, et rend ses résultats chiffrés de bout en bout.
    """

    def __init__(
        self,
        wrapped: Any,
        *,
        name: str,
        capabilities: Iterable[str] | None = None,
        input_key: str | None = None,
        input_adapter: Callable[[Any], Any] | None = None,
        output_adapter: Callable[[Any], Any] | None = None,
        invoke_method: str | None = None,
        run_in_thread: bool = True,
        **agent_kwargs,
    ):
        """
        Args:
            wrapped:        L'agent existant à exposer.
            name:           Nom de l'agent sur le réseau Nexus.
            capabilities:   Ce qu'il sait faire — c'est par là qu'on le
                            découvrira.
            input_key:      Extrait une seule valeur du dict de la tâche
                            avant l'appel. Utile pour les agents qui
                            attendent une chaîne, pas un dict.
            input_adapter:  Transformation complète de l'entrée. Prime sur
                            `input_key`.
            output_adapter: Transformation de la sortie avant renvoi.
            invoke_method:  Force la méthode d'invocation si la détection
                            se trompe.
            run_in_thread:  Exécute les méthodes synchrones dans un thread.
                            À laisser vrai : voir `_call`.
            **agent_kwargs: Passés tels quels à `NexusAgent` (hub_url,
                            api_key, roles, org_id, encrypt…).
        """
        super().__init__(name=name, capabilities=list(capabilities or []), **agent_kwargs)

        self.wrapped = wrapped
        self.input_key = input_key
        self.input_adapter = input_adapter
        self.output_adapter = output_adapter
        self.run_in_thread = run_in_thread

        self._fn, self._is_async, self._style = detect_invoker(wrapped, invoke_method)
        self.invoke_method = getattr(self._fn, "__name__", repr(self._fn))

        # Le même pont sert aux tâches déléguées et aux requêtes directes.
        self.on_task(self._handle_task)
        self.on_request(self._handle_request)

    # ------------------------------------------------------------------

    def _prepare(self, data: Any) -> Any:
        if self.input_adapter:
            return self.input_adapter(data)
        if self.input_key and isinstance(data, dict):
            return data.get(self.input_key)
        return data

    def _finalize(self, result: Any) -> Any:
        if self.output_adapter:
            result = self.output_adapter(result)
        return _jsonable(result)

    async def _call(self, payload: Any) -> Any:
        """
        Invoque l'agent enveloppé.

        Les méthodes synchrones partent dans un thread. C'est le point le
        plus important de ce module : `invoke()` d'un agent LLM bloque
        plusieurs secondes, parfois des dizaines. Appelée directement dans
        la boucle asyncio, elle gèlerait tout l'agent Nexus — plus aucune
        autre tâche reçue, plus aucun message routé, connexion figée le
        temps de l'appel.
        """
        if self._style == "inputs_kw":
            call = lambda: self._fn(inputs=payload)          # noqa: E731
        else:
            call = lambda: self._fn(payload)                 # noqa: E731

        if self._is_async:
            return await call()
        if self.run_in_thread:
            return await asyncio.to_thread(call)
        return call()

    async def _handle_task(self, input_data: Any, task) -> Any:
        return self._finalize(await self._call(self._prepare(input_data)))

    async def _handle_request(self, msg) -> Any:
        return self._finalize(await self._call(self._prepare(msg.content)))

    def __repr__(self) -> str:
        return (f"<NexusAdapter {self.name} → {type(self.wrapped).__name__}"
                f".{self.invoke_method}()>")


def adapt(wrapped: Any, *, name: str, capabilities: Iterable[str] | None = None,
          **kwargs) -> NexusAdapter:
    """
    Expose un agent existant sur le réseau Nexus.

        from nexus_sdk.adapters import adapt

        agent = adapt(ma_chaine_langchain, name="analyste",
                      capabilities=["market_analysis"])
        await agent.connect()

    L'agent devient découvrable par ses capacités et reçoit des tâches
    comme n'importe quel agent Nexus natif.
    """
    return NexusAdapter(wrapped, name=name, capabilities=capabilities, **kwargs)
