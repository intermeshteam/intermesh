import asyncio
import inspect
from typing import Callable, Any, Optional, List


def from_callable(
    fn: Callable[[Any], Any],
    name: str,
    capabilities: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
    org_id: str = "default",
    hub_url: str = "ws://localhost:8765",
    encrypt: bool = True
):
    """
    Transforme N'IMPORTE QUELLE fonction Python existante en un Agent Nexus complet
    en 1 seule ligne de code.
    """
    from nexus_sdk.agent import NexusAgent

    agent = NexusAgent(
        name=name,
        org_id=org_id,
        capabilities=capabilities or ["compute"],
        roles=roles or ["worker"],
        permissions=permissions or [],
        hub_url=hub_url,
        encrypt=encrypt
    )

    async def adapter_task_handler(input_data: Any, task: Any):
        if inspect.iscoroutinefunction(fn):
            return await fn(input_data)
        else:
            return fn(input_data)

    agent.on_task(adapter_task_handler)
    return agent


def from_langchain(
    chain_or_runnable: Any,
    name: str,
    capabilities: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    hub_url: str = "ws://localhost:8765",
    encrypt: bool = True
):
    """
    Adapte un Runnable / Chain LangChain ou une équipe CrewAI en un Agent Nexus en 1 ligne.
    """
    from nexus_sdk.agent import NexusAgent

    agent = NexusAgent(
        name=name,
        capabilities=capabilities or ["langchain_chain"],
        roles=roles or ["worker"],
        hub_url=hub_url,
        encrypt=encrypt
    )

    async def langchain_handler(input_data: Any, task: Any):
        if hasattr(chain_or_runnable, "ainvoke"):
            res = await chain_or_runnable.ainvoke(input_data)
        elif hasattr(chain_or_runnable, "invoke"):
            res = chain_or_runnable.invoke(input_data)
        elif hasattr(chain_or_runnable, "run"):
            res = chain_or_runnable.run(input_data)
        elif callable(chain_or_runnable):
            res = chain_or_runnable(input_data)
        else:
            raise TypeError("L'objet fourni n'est pas un Runnable/Chain LangChain valide.")

        return {"output": res, "adapter": "langchain_nexus_v1"}

    agent.on_task(langchain_handler)
    return agent


def nexus_service(
    name: str,
    capabilities: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    hub_url: str = "ws://localhost:8765",
    encrypt: bool = True
):
    """
    Décorateur 1-Ligne pour transformer n'importe quelle fonction en service Nexus.
    """
    def decorator(fn: Callable[[Any], Any]):
        return from_callable(
            fn=fn,
            name=name,
            capabilities=capabilities,
            roles=roles,
            hub_url=hub_url,
            encrypt=encrypt
        )
    return decorator
