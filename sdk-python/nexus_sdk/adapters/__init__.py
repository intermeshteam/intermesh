"""
Ponts vers les frameworks d'agents existants.

Un développeur ne réécrira pas ses agents pour essayer un protocole. Ces
adaptateurs branchent un agent LangChain, CrewAI, AutoGen ou LlamaIndex
déjà écrit sur le réseau Nexus, sans en changer une ligne.

    from nexus_sdk.adapters import adapt

    agent = adapt(mon_agent_existant, name="analyste",
                  capabilities=["market_analysis"])
    await agent.connect()

POURQUOI AUCUN IMPORT DE FRAMEWORK
----------------------------------
Ce module n'importe ni LangChain, ni CrewAI, ni aucun autre. Il détecte
la convention d'appel de l'objet qu'on lui confie.

Trois raisons, dans l'ordre d'importance :

1. `nexus-mesh` n'acquiert aucune dépendance. Installer le SDK ne doit
   pas tirer LangChain et ses cent paquets transitifs.
2. Ces frameworks cassent leurs API entre versions majeures. Un import
   dur contre `langchain.agents.AgentExecutor` se briserait à la
   prochaine. Le duck-typing survit aux ruptures.
3. Un framework que nous ne connaissons pas fonctionne quand même, s'il
   expose une méthode d'invocation reconnaissable ou s'il est appelable.
"""

from nexus_sdk.adapters.base import (
    AdapterError,
    NexusAdapter,
    adapt,
    detect_invoker,
)

__all__ = ["adapt", "NexusAdapter", "AdapterError", "detect_invoker"]
