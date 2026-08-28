# Exemples avec de vrais frameworks

Contrairement à `examples/agent_a.py`/`agent_b.py`/`agent_c.py` (des agents InterMesh
faits main qui simulent un LLM), les scripts de ce dossier enveloppent de vrais
objets de framework — un `Runnable` LangChain, un moteur de requête LlamaIndex,
un `Crew` CrewAI, un `ConversableAgent` AutoGen — via les adaptateurs de
`intermesh.adapters`, sans une ligne de code Nexus dans leur définition.

| Script | Framework | Fonctionne sans clé API |
|---|---|---|
| `langchain_agent.py` | LangChain (chaîne LCEL) | ✅ `FakeListChatModel` |
| `llamaindex_agent.py` | LlamaIndex (index vectoriel) | ✅ `MockLLM` / `MockEmbedding` |
| `crewai_agent.py` | CrewAI (`Agent` + `Crew`) | ❌ nécessite `OPENAI_API_KEY` |
| `autogen_agent.py` | AutoGen (`ConversableAgent`) | ❌ nécessite `OPENAI_API_KEY` |
| `orchestrator_demo.py` | — | pipeline reliant `langchain_agent.py` à `examples/agent_b.py` |

LangChain et LlamaIndex fournissent chacun un LLM/embedding factice déterministe
dans leur propre package (`FakeListChatModel`, `MockLLM`, `MockEmbedding`) : les
deux premiers exemples tournent donc réellement, hors ligne, sans coût — seule
la génération de texte est scriptée, tout le reste (le `Runnable`, l'index
vectoriel, le pont Nexus, le chiffrement de bout en bout) est le code réel du
framework. Fournissez `OPENAI_API_KEY` pour basculer sur un vrai LLM sans
changer une ligne de l'exemple.

CrewAI et AutoGen n'ont pas d'équivalent hors ligne : un `Agent`/`ConversableAgent`
appelle toujours un LLM pour raisonner. Ces deux exemples nécessitent donc une
clé API valide pour exécuter réellement une tâche ; sans clé, l'agent se
connecte et se déclare quand même, ce qui suffit à vérifier le pontage, mais
toute tâche déléguée échouera à l'appel du LLM.

## Installer les dépendances

Chaque script n'importe son framework qu'à l'intérieur de sa fonction
`build_...()` — voir `intermesh/adapters/__init__.py` pour la raison. N'installez
que ce dont vous avez besoin :

```bash
pip install langchain-core                 # langchain_agent.py, mode hors ligne
pip install langchain-core langchain-openai # langchain_agent.py, mode LLM réel

pip install llama-index-core                                       # llamaindex_agent.py, mode hors ligne
pip install llama-index-core llama-index-llms-openai llama-index-embeddings-openai  # mode LLM réel

pip install crewai      # crewai_agent.py — nécessite OPENAI_API_KEY pour exécuter une tâche
pip install pyautogen   # autogen_agent.py — nécessite OPENAI_API_KEY pour exécuter une tâche
```

## Lancer la démo d'orchestration

Dans quatre terminaux, à la racine du dépôt :

```bash
nexus hub
```
```bash
python examples/agent_b.py
```
```bash
python examples/frameworks/langchain_agent.py
```
```bash
python examples/frameworks/orchestrator_demo.py
```

Le dernier terminal affiche le résultat d'un `InterMeshPipeline` à deux étapes : la
première confiée au vrai `Runnable` LangChain (traduction), la seconde à l'agent
natif `agent_b` (calcul) — le tout chiffré de bout en bout entre les trois
processus, exactement comme documenté dans
[`docs/AGENT-INTEGRATION.md`](../../docs/AGENT-INTEGRATION.md).
